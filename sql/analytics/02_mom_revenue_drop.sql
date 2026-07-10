WITH monthly AS (
  SELECT customer_id, DATE_TRUNC('month', bill_date) AS bill_month,
         SUM(billed_amount) AS revenue
  FROM TELCO_RA.MARTS.FACT_BILLING
  GROUP BY 1, 2
)
SELECT *,
  LAG(revenue) OVER (PARTITION BY customer_id ORDER BY bill_month) AS prev_revenue,
  revenue - LAG(revenue) OVER (PARTITION BY customer_id ORDER BY bill_month) AS mom_delta
FROM monthly
QUALIFY mom_delta < -0.30 * prev_revenue;   -- flag >30% drops