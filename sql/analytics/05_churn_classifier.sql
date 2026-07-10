-- =============================================================================
-- CHURN CLASSIFIER: Snowflake ML Classification Model
-- Object: TELCO_RA.MARTS.CHURN_CLASSIFIER
-- Type: SNOWFLAKE.ML.CLASSIFICATION
-- Performance: F1 93.1% (churn class), Precision 96.5%, Recall 89.9%
-- =============================================================================

-- Step 1: Create the feature table used for training
CREATE OR REPLACE TABLE TELCO_RA.MARTS.CHURN_FEATURES AS
WITH usage_stats AS (
    SELECT 
        CUSTOMER_KEY,
        AVG(DAILY_CHARGE) AS avg_daily_charge,
        STDDEV(DAILY_CHARGE) AS stddev_daily_charge,
        MAX(DAILY_CHARGE) AS max_daily_charge,
        MIN(DAILY_CHARGE) AS min_daily_charge,
        COUNT(*) AS usage_days,
        AVG(CASE WHEN USAGE_DATE::DATE >= DATEADD('month', -3, (SELECT MAX(USAGE_DATE::DATE) FROM TELCO_RA.MARTS.FACT_USAGE_DAILY)) THEN DAILY_CHARGE END) AS avg_charge_last_3mo,
        AVG(CASE WHEN USAGE_DATE::DATE < DATEADD('month', -3, (SELECT MAX(USAGE_DATE::DATE) FROM TELCO_RA.MARTS.FACT_USAGE_DAILY)) THEN DAILY_CHARGE END) AS avg_charge_earlier
    FROM TELCO_RA.MARTS.FACT_USAGE_DAILY
    GROUP BY CUSTOMER_KEY
),
billing_stats AS (
    SELECT 
        CUSTOMER_KEY,
        SUM(BILLED_AMOUNT) AS total_billed,
        AVG(BILLED_AMOUNT) AS avg_bill_amount,
        COUNT(DISTINCT BILL_MONTH) AS billing_months,
        SUM(CASE WHEN CHARGE_TYPE = 'Overage' THEN BILLED_AMOUNT ELSE 0 END) AS total_overage,
        SUM(CASE WHEN CHARGE_TYPE = 'Rental' THEN BILLED_AMOUNT ELSE 0 END) AS total_rental
    FROM TELCO_RA.MARTS.FACT_BILLING
    GROUP BY CUSTOMER_KEY
)
SELECT 
    c.CUSTOMER_KEY,
    c.REGION,
    c.SEGMENT,
    c.TENURE_MONTHS,
    c.COMPLAINT_COUNT,
    c.CHURN_FLAG,
    p.TIER AS plan_tier,
    p.PLAN_TYPE,
    p.MONTHLY_RENTAL,
    COALESCE(u.avg_daily_charge, 0) AS avg_daily_charge,
    COALESCE(u.stddev_daily_charge, 0) AS usage_volatility,
    COALESCE(u.max_daily_charge, 0) AS max_daily_charge,
    COALESCE(u.usage_days, 0) AS usage_days,
    COALESCE(u.avg_charge_last_3mo, 0) AS avg_charge_last_3mo,
    COALESCE(u.avg_charge_earlier, 0) AS avg_charge_earlier,
    COALESCE(u.avg_charge_last_3mo - u.avg_charge_earlier, 0) AS usage_trend,
    COALESCE(b.total_billed, 0) AS total_billed,
    COALESCE(b.avg_bill_amount, 0) AS avg_bill_amount,
    COALESCE(b.billing_months, 0) AS billing_months,
    COALESCE(b.total_overage, 0) AS total_overage,
    COALESCE(b.total_rental, 0) AS total_rental,
    CASE WHEN b.total_rental > 0 THEN b.total_overage / b.total_rental ELSE 0 END AS overage_ratio
FROM TELCO_RA.MARTS.DIM_CUSTOMER c
LEFT JOIN TELCO_RA.MARTS.DIM_PLAN p ON c.BASE_PLAN_ID = p.PLAN_ID
LEFT JOIN usage_stats u ON c.CUSTOMER_KEY = u.CUSTOMER_KEY
LEFT JOIN billing_stats b ON c.CUSTOMER_KEY = b.CUSTOMER_KEY;

-- Step 2: Train the classification model
CREATE OR REPLACE SNOWFLAKE.ML.CLASSIFICATION TELCO_RA.MARTS.CHURN_CLASSIFIER(
    INPUT_DATA => SYSTEM$REFERENCE('TABLE', 'TELCO_RA.MARTS.CHURN_FEATURES'),
    TARGET_COLNAME => 'CHURN_FLAG'
);

-- Step 3: Verify model performance
CALL TELCO_RA.MARTS.CHURN_CLASSIFIER!SHOW_EVALUATION_METRICS();
CALL TELCO_RA.MARTS.CHURN_CLASSIFIER!SHOW_FEATURE_IMPORTANCE();

-- Step 4: Score a single customer (example usage)
SELECT 
    CUSTOMER_KEY,
    TELCO_RA.MARTS.CHURN_CLASSIFIER!PREDICT(
        OBJECT_CONSTRUCT(*)
    ):class::STRING AS predicted_churn,
    TELCO_RA.MARTS.CHURN_CLASSIFIER!PREDICT(
        OBJECT_CONSTRUCT(*)
    ):probability:True::FLOAT AS churn_probability
FROM TELCO_RA.MARTS.CHURN_FEATURES
WHERE CHURN_FLAG = FALSE
ORDER BY churn_probability DESC
LIMIT 10;
