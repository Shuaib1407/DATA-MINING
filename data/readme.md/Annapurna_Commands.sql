-- ANNAPURNA DATA PLATFORM - EXAM COMMAND SCRIPT
-- Stack: MinIO + PostgreSQL + DuckDB
-- NOTE: Run these commands in DuckDB unless marked otherwise.
-- Each section has a 3-word heading for screenshot naming.

-- ============================================================
-- TASK 1: STAND PLATFORM
-- ============================================================

-- 1. Check Raw Files
SELECT COUNT(*)
FROM glob('s3://annapurna-sales/raw/**/*.csv');

-- 2. Check S01 October
SELECT COUNT(*)
FROM glob('s3://annapurna-sales/raw/year=2024/month=10/store=S01/*.csv');

-- 3. Inspect S01 Data
SELECT *
FROM read_csv_auto(
    's3://annapurna-sales/raw/year=2024/month=10/store=S01/SALES_S01_20241001.csv'
)
LIMIT 5;

-- 4. Inspect S06 Data
SELECT *
FROM read_csv(
    's3://annapurna-sales/raw/year=2024/month=10/store=S06/SALES_S06_20241001.csv',
    delim=';'
)
LIMIT 5;

-- 5. Inspect S10 Data
SELECT *
FROM read_csv_auto(
    's3://annapurna-sales/raw/year=2024/month=10/store=S10/SALES_S10_20241001.csv'
)
LIMIT 5;


-- ============================================================
-- TASK 2: SAFE REPEATED LOADING
-- ============================================================

-- 6. Find Duplicate Keys
SELECT COUNT(*) AS duplicate_keys
FROM (
    SELECT bill_no, line_no
    FROM normalized_sales
    GROUP BY bill_no, line_no
    HAVING COUNT(*) > 1
);

-- 7. Check Duplicate Conflicts
SELECT COUNT(*) AS conflicting_keys
FROM (
    SELECT
        bill_no,
        line_no
    FROM normalized_sales_data
    GROUP BY bill_no, line_no
    HAVING COUNT(DISTINCT concat_ws('|',
        store_id,
        business_date,
        product_code,
        qty,
        unit_price,
        line_type,
        ts
    )) > 1
);

-- 8. Build Clean Sales
CREATE OR REPLACE TABLE clean_sales AS
SELECT
    store_id,
    business_date,
    bill_no,
    line_no,
    product_code,
    qty,
    unit_price,
    line_type,
    ts,
    source_file
FROM (
    SELECT
        store_id,
        business_date,
        bill_no,
        line_no,
        product_code,
        qty,
        unit_price,
        line_type,
        ts,
        source_file,
        ROW_NUMBER() OVER (
            PARTITION BY bill_no, line_no
            ORDER BY source_file
        ) AS rn
    FROM normalized_sales_data
)
WHERE rn = 1;

-- 9. Check Clean Count
SELECT COUNT(*) AS row_count
FROM clean_sales;

-- 10. Clean Data Checksum
SELECT
    COUNT(*) AS row_count,
    md5(
        string_agg(
            md5(
                concat_ws('|',
                    store_id,
                    business_date,
                    bill_no,
                    line_no,
                    product_code,
                    qty,
                    unit_price,
                    line_type,
                    ts,
                    source_file
                )
            ),
            '' ORDER BY
                store_id,
                business_date,
                bill_no,
                line_no,
                source_file
        )
    ) AS checksum
FROM clean_sales;

-- 11. Second Clean Load
CREATE OR REPLACE TABLE clean_sales AS
SELECT
    store_id,
    business_date,
    bill_no,
    line_no,
    product_code,
    qty,
    unit_price,
    line_type,
    ts,
    source_file
FROM (
    SELECT
        store_id,
        business_date,
        bill_no,
        line_no,
        product_code,
        qty,
        unit_price,
        line_type,
        ts,
        source_file,
        ROW_NUMBER() OVER (
            PARTITION BY bill_no, line_no
            ORDER BY source_file
        ) AS rn
    FROM normalized_sales_data
)
WHERE rn = 1;

-- 12. Second Load Check
SELECT
    COUNT(*) AS row_count,
    md5(
        string_agg(
            md5(
                concat_ws('|',
                    store_id,
                    business_date,
                    bill_no,
                    line_no,
                    product_code,
                    qty,
                    unit_price,
                    line_type,
                    ts,
                    source_file
                )
            ),
            '' ORDER BY
                store_id,
                business_date,
                bill_no,
                line_no,
                source_file
        )
    ) AS checksum
FROM clean_sales;


-- ============================================================
-- TASK 3: DASHBOARD / STAR SCHEMA
-- ============================================================

-- 13. Check Store Dimension
SELECT COUNT(*) AS stores
FROM dim_store;

-- 14. Check Category Dimension
SELECT COUNT(*) AS categories
FROM dim_category;

-- 15. Check Product Dimension
SELECT COUNT(*) AS products
FROM dim_product;

-- 16. Check Date Dimension
SELECT COUNT(*) AS dates
FROM dim_date;

-- 17. Check Product Matches
SELECT COUNT(*) AS unmatched_sales
FROM clean_sales s
LEFT JOIN dim_product p
    ON s.product_code = p.product_code
   AND s.business_date BETWEEN p.valid_from AND p.valid_to
WHERE p.product_sk IS NULL;

-- 18. Inspect Unmatched Codes
SELECT
    product_code,
    COUNT(*) AS rows
FROM clean_sales s
LEFT JOIN dim_product p
    ON s.product_code = p.product_code
   AND s.business_date BETWEEN p.valid_from AND p.valid_to
WHERE p.product_sk IS NULL
GROUP BY product_code
ORDER BY rows DESC;

-- 19. Check Sales Line Types
SELECT
    line_type,
    COUNT(*) AS rows
FROM clean_sales
GROUP BY line_type
ORDER BY line_type;

-- 20. Check Void Bills
SELECT COUNT(DISTINCT bill_no) AS void_bills
FROM clean_sales
WHERE line_type = 'VOID';

-- 21. Check Void Details
SELECT
    COUNT(DISTINCT bill_no) AS void_bills,
    COUNT(DISTINCT CASE
        WHEN line_type = 'SALE' THEN bill_no
    END) AS void_bills_with_sale
FROM clean_sales
WHERE bill_no IN (
    SELECT DISTINCT bill_no
    FROM clean_sales
    WHERE line_type = 'VOID'
);

-- 22. Build Fact Sales
CREATE OR REPLACE TABLE fact_sales AS
WITH void_bills AS (
    SELECT DISTINCT bill_no
    FROM clean_sales
    WHERE line_type = 'VOID'
),
sales_lines AS (
    SELECT
        s.store_id,
        s.business_date,
        s.bill_no,
        s.line_no,
        p.product_sk,
        p.category_id,
        s.qty,
        s.unit_price,
        s.line_type,
        s.ts,
        s.source_file,
        CASE
            WHEN s.line_type = 'SALE'
                THEN s.qty * s.unit_price
            WHEN s.line_type IN ('RETURN', 'DISCOUNT')
                THEN -(s.qty * s.unit_price)
        END AS revenue
    FROM clean_sales s
    INNER JOIN dim_product p
        ON s.product_code = p.product_code
       AND s.business_date BETWEEN p.valid_from AND p.valid_to
    WHERE s.line_type IN ('SALE', 'RETURN', 'DISCOUNT')
      AND s.bill_no NOT IN (SELECT bill_no FROM void_bills)
)
SELECT
    store_id,
    business_date,
    bill_no,
    line_no,
    product_sk,
    category_id,
    qty,
    unit_price,
    line_type,
    revenue,
    ts,
    source_file
FROM sales_lines;

-- 23. Fix Return Revenue
UPDATE fact_sales
SET revenue = -ABS(revenue)
WHERE line_type = 'RETURN';

-- 24. Check Fact Sales
SELECT COUNT(*) AS fact_rows
FROM fact_sales;

-- 25. Check Fact Revenue
SELECT
    line_type,
    COUNT(*) AS rows,
    ROUND(SUM(revenue), 2) AS revenue
FROM fact_sales
GROUP BY line_type
ORDER BY line_type;

-- 26. Check Fact Dimensions
SELECT
    COUNT(*) AS fact_rows,
    COUNT(DISTINCT store_id) AS fact_stores,
    COUNT(DISTINCT category_id) AS fact_categories,
    COUNT(DISTINCT business_date) AS fact_dates
FROM fact_sales;

-- 27. Revenue By Store
SELECT
    store_id,
    ROUND(SUM(revenue), 2) AS revenue
FROM fact_sales
GROUP BY store_id
ORDER BY store_id;

-- 28. Revenue By Category
SELECT
    category_id,
    ROUND(SUM(revenue), 2) AS revenue
FROM fact_sales
GROUP BY category_id
ORDER BY category_id;

-- 29. Revenue By Weekday
SELECT
    d.day_of_week,
    ROUND(SUM(f.revenue), 2) AS revenue
FROM fact_sales f
JOIN dim_date d
    ON f.business_date = d.date_key
GROUP BY d.day_of_week_num, d.day_of_week
ORDER BY d.day_of_week_num;

-- 30. Revenue By Month
SELECT
    d.year,
    d.month,
    d.month_name,
    ROUND(SUM(f.revenue), 2) AS revenue
FROM fact_sales f
JOIN dim_date d
    ON f.business_date = d.date_key
GROUP BY d.year, d.month, d.month_name
ORDER BY d.year, d.month;

-- 31. Verify Star Schema
SELECT
    (SELECT COUNT(*) FROM dim_store) AS stores,
    (SELECT COUNT(*) FROM dim_category) AS categories,
    (SELECT COUNT(*) FROM dim_product) AS products,
    (SELECT COUNT(*) FROM dim_date) AS dates,
    (SELECT COUNT(*) FROM fact_sales) AS fact_rows,
    (SELECT COUNT(DISTINCT store_id) FROM fact_sales) AS fact_stores,
    (SELECT COUNT(DISTINCT category_id) FROM fact_sales) AS fact_categories,
    (SELECT COUNT(DISTINCT business_date) FROM fact_sales) AS fact_dates;


-- ============================================================
-- TASK 4: HISTORICAL PRICES
-- ============================================================

-- 32. Inspect Price Revisions
SELECT *
FROM pg.public.price_revisions
ORDER BY product_sk, effective_from
LIMIT 50;

-- 33. Find Price Changes
SELECT
    p.product_sk,
    p.product_code,
    p.product_name,
    COUNT(*) AS revision_count
FROM dim_product p
JOIN pg.public.price_revisions r
    ON p.product_sk = r.product_sk
GROUP BY
    p.product_sk,
    p.product_code,
    p.product_name
HAVING COUNT(*) > 1
ORDER BY revision_count DESC
LIMIT 20;

-- 34. March Historical Price
SELECT
    p.product_sk,
    p.product_code,
    p.product_name,
    DATE '2024-03-01' AS reporting_date,
    r.selling_price AS historical_price
FROM dim_product p
JOIN pg.public.price_revisions r
    ON p.product_sk = r.product_sk
WHERE p.product_sk = 1118
  AND DATE '2024-03-01'
      BETWEEN r.effective_from AND r.effective_to;

-- 35. October Historical Price
SELECT
    p.product_sk,
    p.product_code,
    p.product_name,
    DATE '2024-10-01' AS reporting_date,
    r.selling_price AS historical_price
FROM dim_product p
JOIN pg.public.price_revisions r
    ON p.product_sk = r.product_sk
WHERE p.product_sk = 1118
  AND DATE '2024-10-01'
      BETWEEN r.effective_from AND r.effective_to;


-- ============================================================
-- TASK 5: CROSS-SYSTEM QUERY
-- ============================================================

-- 36. Direct Minio Join
SELECT
    s.store_id,
    st.store_name,
    p.category_id,
    c.category_name,
    SUM(
        CASE
            WHEN s.line_type = 'SALE'
                THEN s.qty * s.unit_price
            WHEN s.line_type IN ('RETURN', 'DISCOUNT')
                THEN -ABS(s.qty * s.unit_price)
            ELSE 0
        END
    ) AS revenue
FROM read_parquet(
    's3://annapurna-sales/curated/sales/**/*.parquet',
    hive_partitioning = true
) s
JOIN pg.public.stores st
    ON s.store_id = st.store_id
JOIN pg.public.products p
    ON s.product_code = p.product_code
   AND s.business_date BETWEEN p.valid_from AND p.valid_to
JOIN pg.public.product_categories c
    ON p.category_id = c.category_id
WHERE s.line_type IN ('SALE', 'RETURN', 'DISCOUNT')
GROUP BY
    s.store_id,
    st.store_name,
    p.category_id,
    c.category_name
ORDER BY
    s.store_id,
    p.category_id;

-- 37. Explain Minio Join
EXPLAIN
SELECT
    s.store_id,
    st.store_name,
    p.category_id,
    c.category_name,
    SUM(
        CASE
            WHEN s.line_type = 'SALE'
                THEN s.qty * s.unit_price
            WHEN s.line_type IN ('RETURN', 'DISCOUNT')
                THEN -ABS(s.qty * s.unit_price)
            ELSE 0
        END
    ) AS revenue
FROM read_parquet(
    's3://annapurna-sales/curated/sales/**/*.parquet',
    hive_partitioning = true
) s
JOIN pg.public.stores st
    ON s.store_id = st.store_id
JOIN pg.public.products p
    ON s.product_code = p.product_code
   AND s.business_date BETWEEN p.valid_from AND p.valid_to
JOIN pg.public.product_categories c
    ON p.category_id = c.category_id
WHERE s.line_type IN ('SALE', 'RETURN', 'DISCOUNT')
GROUP BY
    s.store_id,
    st.store_name,
    p.category_id,
    c.category_name
ORDER BY
    s.store_id,
    p.category_id;


-- ============================================================
-- TASK 6: FINANCE RECONCILIATION
-- ============================================================

-- 38. Read Finance Data
SELECT *
FROM read_csv_auto('finance_monthly.csv');

-- 39. Calculate Monthly Revenue
SELECT
    strftime(business_date, '%Y-%m') AS month,
    ROUND(SUM(revenue), 2) AS pipeline_revenue
FROM fact_sales
GROUP BY month
ORDER BY month;

-- 40. Compare Finance Revenue
WITH finance AS (
    SELECT
        month,
        revenue_inr AS finance_revenue
    FROM read_csv_auto('finance_monthly.csv')
),
pipeline AS (
    SELECT
        strftime(business_date, '%Y-%m') AS month,
        ROUND(SUM(revenue), 2) AS pipeline_revenue
    FROM fact_sales
    GROUP BY month
)
SELECT
    f.month,
    ROUND(f.finance_revenue, 2) AS finance_revenue,
    p.pipeline_revenue,
    ROUND(p.pipeline_revenue - f.finance_revenue, 2) AS difference,
    ROUND(
        100.0 * (p.pipeline_revenue - f.finance_revenue)
        / f.finance_revenue,
        2
    ) AS difference_pct
FROM finance f
JOIN pipeline p
    ON f.month = p.month
ORDER BY f.month;

-- 41. Check July Stores
SELECT
    store_id,
    ROUND(SUM(revenue), 2) AS july_pipeline_revenue
FROM fact_sales
WHERE business_date >= DATE '2024-07-01'
  AND business_date < DATE '2024-08-01'
GROUP BY store_id
ORDER BY store_id;

-- 42. Check S07 July Files
SELECT
    business_date,
    COUNT(*) AS rows
FROM clean_sales
WHERE store_id = 'S07'
  AND business_date >= DATE '2024-07-01'
  AND business_date < DATE '2024-08-01'
GROUP BY business_date
ORDER BY business_date;

-- 43. Estimate S07 Gap
SELECT
    business_date,
    ROUND(SUM(revenue), 2) AS revenue
FROM fact_sales
WHERE store_id = 'S07'
  AND business_date BETWEEN DATE '2024-07-01' AND DATE '2024-07-31'
GROUP BY business_date
ORDER BY business_date;

-- 44. Check Finance July
SELECT
    f.revenue_inr AS finance_july,
    p.pipeline_revenue AS pipeline_july,
    ROUND(p.pipeline_revenue - f.revenue_inr, 2) AS difference
FROM read_csv_auto('finance_monthly.csv') f
JOIN (
    SELECT ROUND(SUM(revenue), 2) AS pipeline_revenue
    FROM fact_sales
    WHERE business_date >= DATE '2024-07-01'
      AND business_date < DATE '2024-08-01'
) p
ON f.month = '2024-07';


-- ============================================================
-- FINAL VERIFICATION
-- ============================================================

-- 45. Final Platform Check
SELECT
    'clean_sales' AS component,
    COUNT(*) AS rows
FROM clean_sales

UNION ALL

SELECT
    'fact_sales',
    COUNT(*)
FROM fact_sales

UNION ALL

SELECT
    'dim_store',
    COUNT(*)
FROM dim_store

UNION ALL

SELECT
    'dim_category',
    COUNT(*)
FROM dim_category

UNION ALL

SELECT
    'dim_product',
    COUNT(*)
FROM dim_product

UNION ALL

SELECT
    'dim_date',
    COUNT(*)
FROM dim_date;


-- ============================================================
-- END OF ANNAPURNA EXAM COMMANDS
-- ============================================================
