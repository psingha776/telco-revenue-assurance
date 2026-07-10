-- =============================================================================
-- WEEKLY CHURN RISK MONITOR: Early Warning System
-- Object: TELCO_RA.MARTS.V_WEEKLY_CHURN_RISK_MONITOR
-- Type: VIEW
-- Description: Live-scoring view that identifies active customers meeting
--              early-warning criteria (tenure <= 6 months AND complaints >= 2),
--              scores them with the churn model, and assigns recommended actions.
-- Dependencies: TELCO_RA.MARTS.CHURN_CLASSIFIER
-- Schedule: Run weekly (or attach to a Snowflake Task for automation)
-- =============================================================================

CREATE OR REPLACE VIEW TELCO_RA.MARTS.V_WEEKLY_CHURN_RISK_MONITOR AS
WITH current_at_risk AS (
    SELECT 
        c.CUSTOMER_KEY,
        c.CUSTOMER_ID,
        c.REGION,
        c.SEGMENT,
        c.SIGNUP_DATE::DATE AS signup_date,
        c.TENURE_MONTHS,
        c.COMPLAINT_COUNT,
        p.TIER AS plan_tier,
        p.PLAN_NAME,
        p.MONTHLY_RENTAL,
        -- Score with churn model
        TELCO_RA.MARTS.CHURN_CLASSIFIER!PREDICT(
            OBJECT_CONSTRUCT(
                'CUSTOMER_KEY', c.CUSTOMER_KEY,
                'REGION', c.REGION,
                'SEGMENT', c.SEGMENT,
                'TENURE_MONTHS', c.TENURE_MONTHS,
                'COMPLAINT_COUNT', c.COMPLAINT_COUNT,
                'PLAN_TIER', p.TIER,
                'PLAN_TYPE', p.PLAN_TYPE,
                'MONTHLY_RENTAL', p.MONTHLY_RENTAL,
                'AVG_DAILY_CHARGE', COALESCE(u.avg_daily_charge, 0),
                'USAGE_VOLATILITY', COALESCE(u.stddev_charge, 0),
                'MAX_DAILY_CHARGE', COALESCE(u.max_charge, 0),
                'USAGE_DAYS', COALESCE(u.usage_days, 0),
                'AVG_CHARGE_LAST_3MO', COALESCE(u.avg_charge_last_3mo, 0),
                'AVG_CHARGE_EARLIER', COALESCE(u.avg_charge_earlier, 0),
                'USAGE_TREND', COALESCE(u.avg_charge_last_3mo - u.avg_charge_earlier, 0),
                'TOTAL_BILLED', COALESCE(b.total_billed, 0),
                'AVG_BILL_AMOUNT', COALESCE(b.avg_bill_amount, 0),
                'BILLING_MONTHS', COALESCE(b.billing_months, 0),
                'TOTAL_OVERAGE', COALESCE(b.total_overage, 0),
                'TOTAL_RENTAL', COALESCE(b.total_rental, 0),
                'OVERAGE_RATIO', CASE WHEN COALESCE(b.total_rental, 0) > 0 
                                      THEN b.total_overage / b.total_rental ELSE 0 END
            )
        ):probability:True::FLOAT AS churn_probability
    FROM TELCO_RA.MARTS.DIM_CUSTOMER c
    JOIN TELCO_RA.MARTS.DIM_PLAN p ON c.BASE_PLAN_ID = p.PLAN_ID
    LEFT JOIN (
        SELECT CUSTOMER_KEY,
            AVG(DAILY_CHARGE) AS avg_daily_charge,
            STDDEV(DAILY_CHARGE) AS stddev_charge,
            MAX(DAILY_CHARGE) AS max_charge,
            COUNT(*) AS usage_days,
            AVG(CASE WHEN USAGE_DATE::DATE >= DATEADD('month', -3, CURRENT_DATE()) 
                     THEN DAILY_CHARGE END) AS avg_charge_last_3mo,
            AVG(CASE WHEN USAGE_DATE::DATE < DATEADD('month', -3, CURRENT_DATE()) 
                     THEN DAILY_CHARGE END) AS avg_charge_earlier
        FROM TELCO_RA.MARTS.FACT_USAGE_DAILY
        GROUP BY CUSTOMER_KEY
    ) u ON c.CUSTOMER_KEY = u.CUSTOMER_KEY
    LEFT JOIN (
        SELECT CUSTOMER_KEY,
            SUM(BILLED_AMOUNT) AS total_billed,
            AVG(BILLED_AMOUNT) AS avg_bill_amount,
            COUNT(DISTINCT BILL_MONTH) AS billing_months,
            SUM(CASE WHEN CHARGE_TYPE = 'Overage' THEN BILLED_AMOUNT ELSE 0 END) AS total_overage,
            SUM(CASE WHEN CHARGE_TYPE = 'Rental' THEN BILLED_AMOUNT ELSE 0 END) AS total_rental
        FROM TELCO_RA.MARTS.FACT_BILLING
        GROUP BY CUSTOMER_KEY
    ) b ON c.CUSTOMER_KEY = b.CUSTOMER_KEY
    WHERE c.CHURN_FLAG = FALSE          -- only active customers
      AND c.TENURE_MONTHS <= 6          -- early tenure (high risk window)
      AND c.COMPLAINT_COUNT >= 2        -- 2+ complaints (churn trigger)
)
SELECT 
    *,
    CASE 
        WHEN churn_probability >= 0.8 THEN 'CRITICAL - Immediate intervention'
        WHEN churn_probability >= 0.5 THEN 'HIGH - Escalate to retention team'
        WHEN churn_probability >= 0.3 THEN 'MEDIUM - Proactive outreach'
        ELSE 'WATCH - Monitor next week'
    END AS recommended_action,
    CURRENT_DATE() AS report_date
FROM current_at_risk
ORDER BY churn_probability DESC;

-- =============================================================================
-- Usage: Run weekly or schedule as a Task
-- =============================================================================

-- Quick check: how many customers are at-risk right now?
SELECT 
    recommended_action,
    COUNT(*) AS customers,
    ROUND(AVG(churn_probability), 3) AS avg_prob,
    ROUND(AVG(COMPLAINT_COUNT), 1) AS avg_complaints
FROM TELCO_RA.MARTS.V_WEEKLY_CHURN_RISK_MONITOR
GROUP BY recommended_action
ORDER BY avg_prob DESC;

-- =============================================================================
-- Optional: Automate with a Snowflake Task (sends alert on new CRITICAL cases)
-- =============================================================================
/*
CREATE OR REPLACE TASK TELCO_RA.MARTS.TASK_WEEKLY_CHURN_ALERT
  WAREHOUSE = COMPUTE_WH
  SCHEDULE = 'USING CRON 0 9 * * MON America/New_York'  -- Every Monday 9am ET
AS
  INSERT INTO TELCO_RA.MARTS.CHURN_ALERT_LOG (alert_date, critical_count, high_count)
  SELECT 
      CURRENT_DATE(),
      COUNT(CASE WHEN churn_probability >= 0.8 THEN 1 END),
      COUNT(CASE WHEN churn_probability >= 0.5 AND churn_probability < 0.8 THEN 1 END)
  FROM TELCO_RA.MARTS.V_WEEKLY_CHURN_RISK_MONITOR;

ALTER TASK TELCO_RA.MARTS.TASK_WEEKLY_CHURN_ALERT RESUME;
*/
