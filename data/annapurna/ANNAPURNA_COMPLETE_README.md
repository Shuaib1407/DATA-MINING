# Annapurna Stores Data Engineering Project

## 1. Project Overview

The Annapurna Stores data platform demonstrates a complete analytical workflow using:

- Docker
- MinIO object storage
- DuckDB
- PostgreSQL
- SQL-based data processing
- Star-schema modelling
- Revenue analysis and finance reconciliation

The workflow covers sales ingestion, data cleaning, duplicate handling, product and price matching, dimensional modelling, analytical queries, and reconciliation with monthly finance records.

---

## 2. Project Structure

```text
annapurna/
├── raw/
├── partitioned/
├── curated/
├── duckdb/
├── billing_notes.md
├── masters.sql
└── README.md
```

---

## 3. Start DuckDB

Open PowerShell in the project directory:

```powershell
cd "C:\Users\ub02-glab-052\Downloads\data_2\data\annapurna"
```

Start DuckDB:

```powershell
duckdb .\duckdb\annapurna.duckdb
```

---

## 4. Connect PostgreSQL

Run inside DuckDB:

```sql
INSTALL postgres;
LOAD postgres;

ATTACH
'host=localhost port=5432 dbname=annapurna user=admin password=admin123'
AS pg (TYPE POSTGRES, READ_ONLY);
```

PostgreSQL master data can be accessed using:

```sql
pg.public.stores
pg.public.products
pg.public.product_categories
pg.public.price_revisions
```

---

## 5. Connect DuckDB to MinIO

```sql
CREATE OR REPLACE SECRET minio_secret (
    TYPE S3,
    KEY_ID 'minioadmin',
    SECRET 'minioadmin123',
    REGION 'us-east-1',
    ENDPOINT 'localhost:9000',
    URL_STYLE 'path',
    USE_SSL false
);
```

List objects in the MinIO bucket:

```sql
SELECT *
FROM glob('s3://annapurna/sales/**/*');
```

---

## 6. Read Sales Files

Example sales ingestion query:

```sql
CREATE OR REPLACE TABLE raw_s01 AS
SELECT *
FROM read_csv_auto(
    's3://annapurna/sales/SALES_S01_*.csv',
    header = true,
    union_by_name = true,
    filename = true
);
```

Inspect the raw data:

```sql
SELECT *
FROM raw_s01
LIMIT 20;
```

Count the ingested rows:

```sql
SELECT COUNT(*) AS total_rows
FROM raw_s01;
```

---

## 7. Duplicate Detection and Deduplication

The business key for a sales line is:

```text
(bill_no, line_no)
```

A preliminary deduplication query is:

```sql
CREATE OR REPLACE TABLE clean_s01 AS
SELECT *
FROM (
    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY bill_no, line_no
            ORDER BY filename
        ) AS rn
    FROM raw_s01
)
WHERE rn = 1;
```

Verify duplicate counts:

```sql
SELECT
    bill_no,
    line_no,
    COUNT(*) AS duplicate_count
FROM raw_s01
GROUP BY bill_no, line_no
HAVING COUNT(*) > 1
ORDER BY duplicate_count DESC;
```

> In a production ingestion pipeline, resend files must be checked for completeness. Selecting a file only by filename order is not sufficient when a resend can be incomplete.

---

## 8. Revenue Rules

| Line type | Meaning | Treatment |
|---|---|---|
| `SALE` | Normal item sale | Included |
| `RETURN` | Returned item | Included as negative revenue |
| `DISCOUNT` | Discount amount | Included as a negative amount |
| `VOID` | Cancellation mirror line | Used to identify cancelled bills |
| `TAX` | GST/tax amount | Excluded |
| `TENDER` | Payment total | Excluded |

Important rules:

- `TAX` must not be treated as revenue.
- `TENDER` must not be included because it can double-count the bill value.
- If a bill contains a `VOID` line, the cancellation rule must be applied consistently to the complete bill.
- Discount lines must not be accidentally removed.
- The business date should be derived from the filename rather than blindly using the transaction timestamp when the source notes require this.

---

## 9. Product Matching

Product codes can be reused over time. Therefore, product matching must use both the product code and the business-date validity range.

```sql
CREATE OR REPLACE TABLE s01_products_matched AS
SELECT
    s.bill_no,
    s.line_no,
    s.product_code,
    s.qty,
    s.unit_price,
    s.line_type,
    s.business_date,
    p.product_sk,
    p.product_name,
    p.category_id
FROM final_revenue_s01 s
LEFT JOIN pg.public.products p
    ON s.product_code <> 'DISC'
    AND s.product_code = p.product_code
    AND s.business_date >= p.valid_from
    AND (
        p.valid_to IS NULL
        OR s.business_date <= p.valid_to
    );
```

The `valid_to` boundary is treated as inclusive.

---

## 10. Historical Price Matching and Revenue Calculation

Authoritative selling prices are obtained from the price-revision table using:

- `product_sk`
- `effective_from`
- `effective_to`

```sql
CREATE OR REPLACE TABLE s01_final_revenue AS
SELECT
    s.bill_no,
    s.line_no,
    s.product_code,
    s.product_sk,
    s.product_name,
    s.category_id,
    s.qty,
    s.line_type,
    s.business_date,
    CASE
        WHEN s.line_type = 'DISCOUNT'
            THEN s.qty * s.unit_price
        ELSE s.qty * pr.selling_price
    END AS line_revenue,
    pr.selling_price AS authoritative_price
FROM s01_products_matched s
LEFT JOIN pg.public.price_revisions pr
    ON s.product_sk = pr.product_sk
    AND s.business_date >= pr.effective_from
    AND s.business_date <= pr.effective_to
WHERE s.line_type IN ('SALE', 'RETURN', 'DISCOUNT');
```

Check the calculated revenue:

```sql
SELECT
    ROUND(SUM(line_revenue), 2) AS total_revenue
FROM s01_final_revenue;
```

Check price coverage:

```sql
SELECT
    line_type,
    COUNT(*) AS total_rows,
    COUNT(authoritative_price) AS priced_rows
FROM s01_final_revenue
GROUP BY line_type;
```

---

## 11. Star Schema

The analytical model uses a central fact table connected to dimension tables.

```text
                 dim_date
                    |
                    |
dim_store ---- fact_sales ---- dim_product
                    |
                    |
               dim_category
```

### Create the dimensions

#### Store dimension

```sql
CREATE OR REPLACE TABLE dim_store AS
SELECT *
FROM pg.public.stores;
```

#### Product dimension

```sql
CREATE OR REPLACE TABLE dim_product AS
SELECT
    product_sk,
    product_code,
    product_name,
    category_id,
    brand,
    pack_size,
    uom,
    valid_from,
    valid_to,
    is_current
FROM pg.public.products;
```

#### Category dimension

```sql
CREATE OR REPLACE TABLE dim_category AS
SELECT
    category_id,
    category_name,
    department,
    gst_rate
FROM pg.public.product_categories;
```

#### Date dimension

```sql
CREATE OR REPLACE TABLE dim_date AS
SELECT
    date_value AS date_key,
    EXTRACT(YEAR FROM date_value)::INTEGER AS year,
    EXTRACT(MONTH FROM date_value)::INTEGER AS month_number,
    strftime(date_value, '%B') AS month_name,
    EXTRACT(QUARTER FROM date_value)::INTEGER AS quarter,
    EXTRACT(DAY FROM date_value)::INTEGER AS day_of_month,
    strftime(date_value, '%A') AS day_name,
    EXTRACT(ISODOW FROM date_value)::INTEGER AS day_of_week
FROM generate_series(
    DATE '2024-01-01',
    DATE '2024-12-31',
    INTERVAL '1 day'
) AS t(date_value);
```

---

## 12. Create the Fact Table

```sql
CREATE OR REPLACE TABLE fact_sales AS
SELECT
    bill_no,
    line_no,
    business_date AS date_key,
    product_sk,
    category_id,
    qty,
    authoritative_price,
    line_revenue,
    'S01' AS store_id
FROM s01_final_revenue;
```

The fact table is designed with a `store_id` field so that additional store-level data can be appended using the same structure.

Verify the fact table:

```sql
SELECT *
FROM fact_sales
LIMIT 10;
```

```sql
SELECT
    store_id,
    COUNT(*) AS total_rows,
    ROUND(SUM(line_revenue), 2) AS total_revenue
FROM fact_sales
GROUP BY store_id;
```

---

## 13. Analytical Queries

### Revenue by category

```sql
SELECT
    c.category_name,
    ROUND(SUM(f.line_revenue), 2) AS total_revenue
FROM fact_sales f
JOIN dim_category c
    ON f.category_id = c.category_id
GROUP BY c.category_name
ORDER BY total_revenue DESC;
```

### Revenue by store

```sql
SELECT
    s.store_id,
    s.store_name,
    s.city,
    ROUND(SUM(f.line_revenue), 2) AS total_revenue
FROM fact_sales f
JOIN dim_store s
    ON f.store_id = s.store_id
GROUP BY
    s.store_id,
    s.store_name,
    s.city
ORDER BY total_revenue DESC;
```

### Revenue by month

```sql
SELECT
    d.year,
    d.month_number,
    d.month_name,
    ROUND(SUM(f.line_revenue), 2) AS total_revenue
FROM fact_sales f
JOIN dim_date d
    ON f.date_key = d.date_key
GROUP BY
    d.year,
    d.month_number,
    d.month_name
ORDER BY
    d.year,
    d.month_number;
```

### Revenue by day of the week

```sql
SELECT
    d.day_of_week,
    d.day_name,
    ROUND(SUM(f.line_revenue), 2) AS total_revenue
FROM fact_sales f
JOIN dim_date d
    ON f.date_key = d.date_key
GROUP BY
    d.day_of_week,
    d.day_name
ORDER BY d.day_of_week;
```

---

## 14. Cross-System Query

The fact table can be joined with PostgreSQL dimensions:

```sql
SELECT
    s.store_id,
    s.store_name,
    s.city,
    ROUND(SUM(f.line_revenue), 2) AS total_revenue
FROM fact_sales f
JOIN pg.public.stores s
    ON f.store_id = s.store_id
GROUP BY
    s.store_id,
    s.store_name,
    s.city
ORDER BY total_revenue DESC;
```

Inspect the execution plan:

```sql
EXPLAIN
SELECT
    s.store_id,
    s.store_name,
    s.city,
    ROUND(SUM(f.line_revenue), 2) AS total_revenue
FROM fact_sales f
JOIN pg.public.stores s
    ON f.store_id = s.store_id
GROUP BY
    s.store_id,
    s.store_name,
    s.city;
```

---

## 15. Finance File Loading

First locate the finance file in PowerShell:

```powershell
Get-ChildItem `
    -Path "C:\Users\ub02-glab-052\Downloads\data_2" `
    -Recurse `
    -File |
Where-Object {
    $_.Name -like "finance_monthly*"
} |
Select-Object FullName
```

Use the exact path returned by PowerShell.

Example:

```sql
CREATE OR REPLACE TABLE finance_monthly AS
SELECT *
FROM read_csv_auto(
    'C:/Users/ub02-glab-052/Downloads/data_2/data/annapurna/finance_monthly.csv',
    header = true
);
```

Verify:

```sql
SELECT *
FROM finance_monthly;
```

---

## 16. Monthly Revenue and Reconciliation

Check the available date range:

```sql
SELECT
    MIN(date_key) AS first_date,
    MAX(date_key) AS last_date,
    COUNT(*) AS total_rows
FROM fact_sales;
```

Create monthly revenue:

```sql
CREATE OR REPLACE TABLE monthly_revenue AS
SELECT
    strftime(date_key, '%Y-%m') AS month,
    ROUND(SUM(line_revenue), 2) AS calculated_revenue
FROM fact_sales
GROUP BY month
ORDER BY month;
```

Compare against the finance file:

```sql
SELECT
    f.month,
    f.revenue_inr AS finance_revenue,
    COALESCE(m.calculated_revenue, 0) AS calculated_revenue,
    ROUND(
        f.revenue_inr - COALESCE(m.calculated_revenue, 0),
        2
    ) AS difference
FROM finance_monthly f
LEFT JOIN monthly_revenue m
    ON f.month = m.month
ORDER BY f.month;
```

> A complete reconciliation must use the same store coverage, revenue definition, date range, and cancellation rules as the finance reference.

---

## 17. Diagnostic Checks

### Monthly revenue and bill counts

```sql
SELECT
    strftime(date_key, '%Y-%m') AS month,
    COUNT(DISTINCT bill_no) AS bill_count,
    ROUND(SUM(line_revenue), 2) AS revenue
FROM fact_sales
GROUP BY month
ORDER BY month;
```

### Unmatched products

```sql
SELECT
    product_code,
    COUNT(*) AS unmatched_rows
FROM s01_products_matched
WHERE product_sk IS NULL
  AND product_code <> 'DISC'
GROUP BY product_code
ORDER BY unmatched_rows DESC;
```

### Missing authoritative prices

```sql
SELECT
    line_type,
    COUNT(*) AS total_rows,
    COUNT(authoritative_price) AS priced_rows
FROM s01_final_revenue
GROUP BY line_type;
```

---

## 18. Known Data Issues

The following issues must be considered during the final implementation and report:

1. Resend files can create duplicate business lines.
2. Some resend files may be incomplete.
3. Product codes can be reused after the product-master cleanup.
4. Product matching must use date validity.
5. The `valid_to` date is treated as inclusive.
6. `TAX` and `TENDER` lines must be excluded from revenue.
7. Discount lines must be retained.
8. Cancelled bills must be handled at bill level.
9. The filename date may be the correct business date when timestamps cross midnight.
10. S07 has a known three-day export gap in July 2024.
11. Finance totals may use definitions or source coverage that differ from the analytical calculation.

---

## 19. Evidence Checklist

Capture screenshots of:

1. MinIO bucket and object structure.
2. DuckDB-to-MinIO connection.
3. Raw ingestion and row counts.
4. Duplicate detection.
5. Deduplication output.
6. Revenue-rule filtering.
7. Product validity matching.
8. Historical price matching.
9. Dimension tables.
10. Fact table.
11. Star-schema analytical queries.
12. Cross-system query output.
13. `EXPLAIN` output.
14. Finance table.
15. Monthly reconciliation.
16. Diagnostic checks.

---

## 20. Conclusion

The Annapurna data platform combines object storage, analytical SQL processing, relational master data, and dimensional modelling. The workflow supports cleaned sales data, historical price handling, star-schema reporting, cross-system queries, and finance reconciliation.

The final report should explain the ingestion decisions, revenue definitions, duplicate-handling strategy, partitioning approach, dimensional model, execution evidence, and any differences discovered during reconciliation.
