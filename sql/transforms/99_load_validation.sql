-- CHECK 1: Row counts (expect non-zero in both raw & marts after pipeline runs)
SELECT
  (SELECT COUNT(*) FROM TELCO_RA.RAW.FACT_USAGE)   AS raw_usage,
  (SELECT COUNT(*) FROM TELCO_RA.MARTS.FACT_USAGE)  AS marts_usage,
  (SELECT COUNT(*) FROM TELCO_RA.RAW.FACT_BILLING)  AS raw_billing,
  (SELECT COUNT(*) FROM TELCO_RA.MARTS.FACT_BILLING) AS marts_billing;

-- CHECK 2: Orphan usage rows missing customer or plan (expect 0)
SELECT COUNT(*) AS orphan_usage
FROM TELCO_RA.RAW.FACT_USAGE u
LEFT JOIN TELCO_RA.MARTS.DIM_CUSTOMER c ON c.customer_id = u.customer_id
LEFT JOIN TELCO_RA.MARTS.DIM_PLAN p ON p.plan_id = u.plan_id
WHERE c.customer_key IS NULL OR p.plan_key IS NULL;

-- CHECK 3: Dimension uniqueness (expect dup_keys = 0 for all)
SELECT 'DIM_CUSTOMER' AS dim, COUNT(*) AS rows_count, COUNT(DISTINCT customer_id) AS distinct_keys, COUNT(*) - COUNT(DISTINCT customer_id) AS dup_keys FROM TELCO_RA.MARTS.DIM_CUSTOMER
UNION ALL
SELECT 'DIM_PLAN', COUNT(*), COUNT(DISTINCT plan_id), COUNT(*) - COUNT(DISTINCT plan_id) FROM TELCO_RA.MARTS.DIM_PLAN
UNION ALL
SELECT 'DIM_DATE', COUNT(*), COUNT(DISTINCT "DATE"), COUNT(*) - COUNT(DISTINCT "DATE") FROM TELCO_RA.MARTS.DIM_DATE;

-- CHECK 4: DIM_DATE grain — one row per day, one month_start per month (expect distinct_days = total_days)
SELECT COUNT(*) AS total_days, COUNT(DISTINCT "DATE") AS distinct_days, COUNT(DISTINCT month_start) AS distinct_months
FROM TELCO_RA.MARTS.DIM_DATE;

-- CHECK 5: Billing→DIM_DATE fan-out — joining on month_start should match 1 row (expect 0 rows returned)
SELECT b.bill_id, b.bill_month, COUNT(*) AS date_matches
FROM TELCO_RA.STAGING.FACT_BILLING b
JOIN TELCO_RA.MARTS.DIM_DATE d ON d.month_start = b.bill_month
GROUP BY 1, 2 HAVING COUNT(*) > 1
LIMIT 20;

-- CHECK 6: bill_month always 1st of month (expect on_first_of_month = total, no exceptions)
SELECT COUNT(DISTINCT bill_month) AS distinct_bill_months,
       SUM(CASE WHEN bill_month = DATE_TRUNC('month', bill_month) THEN 1 ELSE 0 END) AS on_first_of_month,
       COUNT(*) AS total
FROM TELCO_RA.STAGING.FACT_BILLING;

-- CHECK 7: Usage↔Billing reconciliation (expect large non-zero count)
WITH exp AS (
  SELECT customer_key, DATE_TRUNC('month', usage_date) m, SUM(expected_charge) e
  FROM TELCO_RA.MARTS.FACT_USAGE GROUP BY 1, 2
), bil AS (
  SELECT customer_key, bill_month m, SUM(billed_amount) b
  FROM TELCO_RA.MARTS.FACT_BILLING WHERE charge_type = 'Usage' GROUP BY 1, 2
)  
SELECT COUNT(*) AS matched_customer_months FROM exp JOIN bil USING (customer_key, m);