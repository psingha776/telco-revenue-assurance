WITH expected AS (          -- what usage says they owe
  SELECT customer_id, DATE_TRUNC('month', usage_date) AS m,
         SUM(expected_charge) AS expected_amt
  FROM TELCO_RA.MARTS.FACT_USAGE GROUP BY 1,2
),
billed AS (                 -- what we actually charged
  SELECT customer_id, DATE_TRUNC('month', bill_date) AS m,
         SUM(billed_amount) AS billed_amt,
         COUNT(*) AS line_count,
         COUNT(*) - COUNT(DISTINCT bill_line_hash) AS dup_lines
  FROM TELCO_RA.MARTS.FACT_BILLING GROUP BY 1,2
),
recon AS (
  SELECT e.customer_id, e.m,
         e.expected_amt, b.billed_amt,
         b.billed_amt - e.expected_amt AS gap,
         b.dup_lines
  FROM expected e LEFT JOIN billed b USING (customer_id, m)
)
SELECT *,
  CASE
    WHEN dup_lines > 0 AND gap > 0           THEN 'OVER_BILLING_DUPLICATE'
    WHEN gap < -:tolerance                   THEN 'UNBILLED_USAGE_LEAKAGE'
    WHEN ABS(gap) <= :tolerance              THEN 'CLEAN'
    ELSE 'RATING_VARIANCE'
  END AS leakage_category
FROM recon;