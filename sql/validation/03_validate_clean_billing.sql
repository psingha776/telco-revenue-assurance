-- Both columns must come back 0 for the clean billing file to pass.
SELECT
  (
    SELECT COUNT(*) - COUNT(DISTINCT bill_line_hash)
    FROM read_parquet('data/raw/fact_billing_clean.parquet')
  ) AS dup_hashes,
  (
    SELECT COUNT(*)
    FROM read_parquet('data/raw/fact_billing_clean.parquet') b
    JOIN read_parquet('data/raw/dim_customer.parquet') c USING (customer_id)
    WHERE c.churn_flag
      AND b.bill_month > DATE_TRUNC('month', c.churn_date)
  ) AS rows_after_churn;