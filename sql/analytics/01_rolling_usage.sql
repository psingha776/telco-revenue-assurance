SELECT
  customer_id,
  usage_date,
  daily_charge,
  SUM(daily_charge) OVER (
    PARTITION BY customer_id ORDER BY usage_date
    ROWS BETWEEN 89 PRECEDING AND CURRENT ROW
  ) AS rolling_90d_charge
FROM TELCO_RA.MARTS.FACT_USAGE_DAILY;