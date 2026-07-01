CREATE OR REPLACE TABLE TELCO_RA.MARTS.FACT_USAGE AS
SELECT
  u.usage_id,
  c.customer_key,
  p.plan_key,
  d.date_key,
  u.customer_id,            
  u.usage_date,
  u.event_type,
  u.units,
  u.expected_charge
FROM TELCO_RA.STAGING.FACT_USAGE u
JOIN TELCO_RA.MARTS.DIM_CUSTOMER c ON c.customer_id = u.customer_id
JOIN TELCO_RA.MARTS.DIM_PLAN     p ON p.plan_id     = u.plan_id
JOIN TELCO_RA.MARTS.DIM_DATE     d ON d."DATE"      = u.usage_date;

CREATE OR REPLACE TABLE TELCO_RA.MARTS.FACT_BILLING AS
SELECT
  b.bill_id,
  c.customer_key,
  p.plan_key,
  d.date_key AS bill_month_key,
  b.customer_id,
  b.bill_month,
  b.charge_type,
  b.billed_amount,
  b.bill_line_hash
FROM TELCO_RA.STAGING.FACT_BILLING b
JOIN TELCO_RA.MARTS.DIM_CUSTOMER c ON c.customer_id = b.customer_id
JOIN TELCO_RA.MARTS.DIM_PLAN     p ON p.plan_id     = b.plan_id
JOIN TELCO_RA.MARTS.DIM_DATE     d ON d.month_start = b.bill_month;