-- Annapurna all-store, rerunnable DuckDB pipeline.
-- Run from data/annapurna with:
--   duckdb duckdb/annapurna.duckdb < sql/01_all_store_pipeline.sql
-- Prerequisite: docker compose up -d, then PostgreSQL has been initialized
-- from masters.sql.  The object-store secret may be adjusted for deployment.

INSTALL httpfs;
LOAD httpfs;
INSTALL postgres;
LOAD postgres;

CREATE OR REPLACE SECRET minio_secret (
  TYPE s3, KEY_ID 'admin', SECRET 'minioadmin123', REGION 'us-east-1',
  ENDPOINT 'localhost:9000', URL_STYLE 'path', USE_SSL false
);

ATTACH 'host=localhost port=5432 dbname=annapurna user=annapurna password=annapurna123'
  AS pg (TYPE POSTGRES, READ_ONLY);

-- The filename, not the till timestamp, defines business_date.  The three
-- unions normalize the three vendor dialects before any business processing.
CREATE OR REPLACE TABLE raw_sales AS
SELECT regexp_extract(filename, 'SALES_(S[0-9]{2})_', 1) AS store_id,
       strptime(regexp_extract(filename, 'SALES_S[0-9]{2}_([0-9]{8})', 1), '%Y%m%d')::DATE AS business_date,
       bill_no::VARCHAR AS bill_no, line_no::INTEGER AS line_no,
       product_code::VARCHAR AS product_code, qty::DECIMAL(18,3) AS qty,
       unit_price::DECIMAL(18,2) AS printed_price, upper(line_type)::VARCHAR AS line_type,
       ts::VARCHAR AS source_ts, filename AS source_file
FROM read_csv_auto(['../sales/SALES_S01_*.csv','../sales/SALES_S02_*.csv','../sales/SALES_S03_*.csv','../sales/SALES_S04_*.csv','../sales/SALES_S05_*.csv'], filename=true, union_by_name=true)
UNION ALL
SELECT regexp_extract(filename, 'SALES_(S[0-9]{2})_', 1),
       strptime(regexp_extract(filename, 'SALES_S[0-9]{2}_([0-9]{8})', 1), '%Y%m%d')::DATE,
       bill_no::VARCHAR, line_no::INTEGER, item_code::VARCHAR, quantity::DECIMAL(18,3),
       rate::DECIMAL(18,2), upper(type)::VARCHAR, txn_time::VARCHAR, filename
FROM read_csv_auto(['../sales/SALES_S06_*.csv','../sales/SALES_S07_*.csv','../sales/SALES_S08_*.csv','../sales/SALES_S09_*.csv'], delim=';', filename=true, union_by_name=true)
UNION ALL
SELECT regexp_extract(filename, 'SALES_(S[0-9]{2})_', 1),
       strptime(regexp_extract(filename, 'SALES_S[0-9]{2}_([0-9]{8})', 1), '%Y%m%d')::DATE,
       bill_no::VARCHAR, line_no::INTEGER, product_code::VARCHAR, qty::DECIMAL(18,3),
       unit_price::DECIMAL(18,2), upper(line_type)::VARCHAR, ts::VARCHAR, filename
FROM read_csv_auto(['../sales/SALES_S10_*.csv','../sales/SALES_S11_*.csv','../sales/SALES_S12_*.csv'], filename=true, union_by_name=true);

-- The immutable business-line key makes resend handling idempotent.  Keeping
-- the lexicographically first source is deterministic; unioning files first
-- means an incomplete resend cannot replace a complete original.
CREATE OR REPLACE TABLE deduplicated_sales AS
SELECT * EXCLUDE(rn)
FROM (
  SELECT *, row_number() OVER (PARTITION BY bill_no, line_no ORDER BY source_file) AS rn
  FROM raw_sales
) WHERE rn = 1;

-- A void cancels the whole bill.  Do not simply discard VOID rows: that leaves
-- the original sale and overstates revenue.
CREATE OR REPLACE TABLE bill_lines AS
SELECT s.*
FROM deduplicated_sales s
WHERE NOT EXISTS (
  SELECT 1 FROM deduplicated_sales v
  WHERE v.bill_no = s.bill_no AND v.line_type = 'VOID'
);

-- Product codes are time-dependent.  Price is also time-dependent, so the
-- authoritative price-revision join makes March use March's price.
CREATE OR REPLACE TABLE enriched_sales AS
SELECT s.store_id, s.business_date, s.bill_no, s.line_no, s.product_code,
       s.qty, s.printed_price, s.line_type, p.product_sk, p.category_id,
       CASE WHEN s.line_type = 'DISCOUNT' THEN s.qty * s.printed_price
            ELSE s.qty * pr.selling_price END AS line_revenue
FROM bill_lines s
LEFT JOIN pg.public.products p
  ON s.product_code = p.product_code
 AND s.business_date BETWEEN p.valid_from AND p.valid_to
LEFT JOIN pg.public.price_revisions pr
  ON p.product_sk = pr.product_sk
 AND s.business_date BETWEEN pr.effective_from AND pr.effective_to
WHERE s.line_type IN ('SALE', 'RETURN', 'DISCOUNT');

CREATE OR REPLACE TABLE fact_sales AS
SELECT *, year(business_date) AS year, month(business_date) AS month,
       date_trunc('week', business_date)::DATE AS week_start
FROM enriched_sales;

-- Object-store layout supports predicate pruning for a store/month dashboard
-- filter: store_id=S01/year=2024/month=10/*.parquet only.
COPY (SELECT * FROM fact_sales)
TO 's3://annapurna/curated/fact_sales'
(FORMAT parquet, PARTITION_BY (store_id, year, month), OVERWRITE_OR_IGNORE);

-- Idempotency evidence.  Save this output after three identical executions;
-- row_count and checksum must not change.
SELECT count(*) AS row_count,
       md5(string_agg(concat_ws('|', bill_no, line_no, store_id, business_date, line_revenue), '' ORDER BY bill_no, line_no)) AS fact_checksum
FROM fact_sales;

-- Required dashboard grains.  Store and product/category names remain in the
-- PostgreSQL masters, avoiding repeated attributes on sales lines.
CREATE OR REPLACE VIEW dashboard_revenue AS
SELECT f.business_date, f.week_start, date_trunc('month', f.business_date)::DATE AS month_start,
       f.store_id, f.product_sk, f.category_id, sum(f.line_revenue) AS revenue
FROM fact_sales f GROUP BY ALL;

-- Same price query; change only the reporting period to show historical price.
SELECT p.product_name, pr.selling_price, DATE '2024-03-01' AS reporting_period
FROM pg.public.products p JOIN pg.public.price_revisions pr USING(product_sk)
WHERE p.product_code = 'P100005' AND DATE '2024-03-01' BETWEEN pr.effective_from AND pr.effective_to;
SELECT p.product_name, pr.selling_price, DATE '2024-10-01' AS reporting_period
FROM pg.public.products p JOIN pg.public.price_revisions pr USING(product_sk)
WHERE p.product_code = 'P100005' AND DATE '2024-10-01' BETWEEN pr.effective_from AND pr.effective_to;

-- Cross-system query: sales remain Parquet in MinIO; dimensions remain in
-- PostgreSQL.  EXPLAIN ANALYZE is the evidence of DuckDB scan/join execution.
EXPLAIN ANALYZE
SELECT st.store_name, c.category_name, sum(f.line_revenue) AS revenue
FROM read_parquet('s3://annapurna/curated/fact_sales/store_id=S01/year=2024/month=10/*.parquet', hive_partitioning=true) f
JOIN pg.public.stores st ON st.store_id = f.store_id
JOIN pg.public.product_categories c ON c.category_id = f.category_id
GROUP BY ALL;

CREATE OR REPLACE TABLE finance_monthly AS
SELECT * FROM read_csv_auto('../finance_monthly.csv');
CREATE OR REPLACE TABLE monthly_reconciliation AS
WITH sales AS (
 SELECT strftime(business_date, '%Y-%m') AS month, round(sum(line_revenue), 2) AS pipeline_revenue
 FROM fact_sales GROUP BY 1
)
SELECT f.month, f.revenue_inr AS finance_revenue, coalesce(s.pipeline_revenue, 0) AS pipeline_revenue,
       round(f.revenue_inr - coalesce(s.pipeline_revenue, 0), 2) AS difference
FROM finance_monthly f LEFT JOIN sales s USING(month) ORDER BY month;
SELECT * FROM monthly_reconciliation;
