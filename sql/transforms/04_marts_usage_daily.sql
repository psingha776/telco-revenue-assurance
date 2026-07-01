CREATE OR REPLACE TABLE TELCO_RA.MARTS.FACT_USAGE_DAILY AS
SELECT
  c.customer_key,
  u.customer_id,
  u.usage_date,
  SUM(u.expected_charge) AS daily_charge
FROM TELCO_RA.STAGING.FACT_USAGE u
JOIN TELCO_RA.MARTS.DIM_CUSTOMER c ON c.customer_id = u.customer_id
GROUP BY 1, 2, 3;