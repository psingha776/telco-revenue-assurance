CREATE OR REPLACE TABLE TELCO_RA.RAW.DIM_PLAN (
  plan_key       NUMBER(38,0),  plan_id      VARCHAR,     plan_name    VARCHAR,
  plan_type      VARCHAR,        tier         VARCHAR,
  monthly_rental NUMBER(12,2),   incl_minutes NUMBER(38,0), incl_gb     NUMBER(10,3),
  incl_sms       NUMBER(38,0),
  per_min_rate   NUMBER(8,4),    per_gb_rate  NUMBER(8,4), per_sms_rate NUMBER(8,4)
);

CREATE OR REPLACE TABLE TELCO_RA.RAW.DIM_CUSTOMER (
  customer_key  NUMBER(38,0), customer_id VARCHAR,      region    VARCHAR,
  segment       VARCHAR,      signup_date DATE,         base_plan_id VARCHAR,
  tenure_months NUMBER(38,0), churn_flag  BOOLEAN,      churn_date DATE,
  complaint_count NUMBER(38,0)
);

CREATE OR REPLACE TABLE TELCO_RA.RAW.DIM_DATE (
  date_key NUMBER(38,0), "DATE" DATE, year NUMBER(38,0), month NUMBER(38,0),
  quarter NUMBER(38,0),  month_name VARCHAR, day_of_week NUMBER(38,0),
  is_weekend BOOLEAN,    month_start DATE
);

CREATE OR REPLACE TABLE TELCO_RA.RAW.FACT_USAGE (
  usage_id NUMBER(38,0), customer_id VARCHAR, usage_date DATE, event_type VARCHAR,
  units NUMBER(10,3),    plan_id VARCHAR,     expected_charge NUMBER(12,2)
);

CREATE OR REPLACE TABLE TELCO_RA.RAW.FACT_BILLING (
  bill_id NUMBER(38,0), customer_id VARCHAR, bill_month DATE, charge_type VARCHAR,
  plan_id VARCHAR,      billed_amount NUMBER(12,2), bill_line_hash VARCHAR(40)
);

CREATE OR REPLACE TABLE TELCO_RA.RAW.ANOMALY_LEDGER (
  ledger_id NUMBER(38,0), customer_id VARCHAR, bill_month DATE, charge_type VARCHAR,
  anomaly_type VARCHAR,   amount_impact NUMBER(12,2), detail VARCHAR
);