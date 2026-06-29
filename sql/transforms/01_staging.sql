CREATE OR REPLACE VIEW TELCO_RA.STAGING.DIM_CUSTOMER AS
SELECT
  customer_key,
  customer_id,
  INITCAP(TRIM(region))  AS region,
  INITCAP(TRIM(segment)) AS segment,
  signup_date,
  base_plan_id,
  tenure_months,
  churn_flag,
  churn_date,
  complaint_count
FROM TELCO_RA.RAW.DIM_CUSTOMER;

CREATE OR REPLACE VIEW TELCO_RA.STAGING.DIM_PLAN AS
SELECT
  plan_key,
  plan_id,
  INITCAP(TRIM(plan_name)) AS plan_name,
  INITCAP(TRIM(plan_type)) AS plan_type,
  INITCAP(TRIM(tier))      AS tier,
  monthly_rental,
  incl_minutes,
  incl_gb,
  incl_sms,
  per_min_rate,
  per_gb_rate,
  per_sms_rate
FROM TELCO_RA.RAW.DIM_PLAN;

CREATE OR REPLACE VIEW TELCO_RA.STAGING.DIM_DATE AS
SELECT
  date_key,
  "DATE",
  year,
  month,
  quarter,
  INITCAP(TRIM(month_name)) AS month_name,
  day_of_week,
  is_weekend,
  month_start
FROM TELCO_RA.RAW.DIM_DATE;

CREATE OR REPLACE VIEW TELCO_RA.STAGING.FACT_USAGE AS
SELECT
  usage_id,
  customer_id,
  usage_date,
  INITCAP(TRIM(event_type)) AS event_type,
  units,
  plan_id,
  expected_charge
FROM TELCO_RA.RAW.FACT_USAGE;

CREATE OR REPLACE VIEW TELCO_RA.STAGING.FACT_BILLING AS
SELECT
  bill_id,
  customer_id,
  bill_month,
  INITCAP(TRIM(charge_type)) AS charge_type,
  plan_id,
  billed_amount,
  bill_line_hash
FROM TELCO_RA.RAW.FACT_BILLING;