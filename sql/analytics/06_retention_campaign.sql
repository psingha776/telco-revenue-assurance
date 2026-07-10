-- =============================================================================
-- RETENTION CAMPAIGN: High-Risk Customer Targeting Table
-- Object: TELCO_RA.MARTS.RETENTION_CAMPAIGN_HIGH_RISK
-- Type: TABLE
-- Description: 465 active Consumer S-tier customers scored by churn model,
--              with assigned retention offers, priority levels, and channels.
-- Dependencies: TELCO_RA.MARTS.CHURN_CLASSIFIER, TELCO_RA.MARTS.CHURN_FEATURES
-- =============================================================================

CREATE OR REPLACE TABLE TELCO_RA.MARTS.RETENTION_CAMPAIGN_HIGH_RISK AS
WITH scored_customers AS (
    SELECT 
        f.*,
        TELCO_RA.MARTS.CHURN_CLASSIFIER!PREDICT(
            OBJECT_CONSTRUCT(*)
        ):probability:True::FLOAT AS churn_probability
    FROM TELCO_RA.MARTS.CHURN_FEATURES f
    WHERE f.CHURN_FLAG = FALSE
      AND f.SEGMENT = 'Consumer'
      AND f.PLAN_TIER = 'S'
)
SELECT 
    s.CUSTOMER_KEY,
    d.CUSTOMER_ID,
    s.REGION,
    s.TENURE_MONTHS,
    s.COMPLAINT_COUNT,
    s.churn_probability,
    s.avg_daily_charge,
    s.total_billed AS lifetime_value_to_date,
    s.MONTHLY_RENTAL AS current_monthly_rental,
    -- Risk tier assignment
    CASE 
        WHEN s.churn_probability >= 0.80 THEN 'CRITICAL'
        WHEN s.churn_probability >= 0.50 THEN 'HIGH'
        ELSE 'MEDIUM'
    END AS risk_tier,
    -- Retention offer logic (complaint-triggered escalation)
    CASE 
        WHEN s.churn_probability >= 0.80 AND s.COMPLAINT_COUNT >= 2 THEN 'Immediate callback + 2-month free upgrade to M-tier'
        WHEN s.churn_probability >= 0.80 THEN 'Priority callback + 1-month credit ($50)'
        WHEN s.churn_probability >= 0.50 AND s.COMPLAINT_COUNT >= 3 THEN 'Escalated case review + 20% discount for 3 months'
        WHEN s.churn_probability >= 0.50 THEN 'Proactive outreach + plan optimization consultation'
        WHEN s.COMPLAINT_COUNT >= 2 THEN 'Automated apology + $25 credit + satisfaction survey'
        ELSE 'Personalized email + loyalty reward points'
    END AS retention_offer,
    -- Intervention priority (1 = most urgent)
    CASE 
        WHEN s.churn_probability >= 0.80 THEN 1
        WHEN s.churn_probability >= 0.50 AND s.COMPLAINT_COUNT >= 3 THEN 2
        WHEN s.churn_probability >= 0.50 THEN 3
        ELSE 4
    END AS intervention_priority,
    -- Channel assignment
    CASE 
        WHEN s.churn_probability >= 0.80 THEN 'Retention specialist (phone)'
        WHEN s.churn_probability >= 0.50 THEN 'Senior CSR (phone/chat)'
        ELSE 'Automated + follow-up if no response'
    END AS channel,
    CURRENT_TIMESTAMP() AS scored_at
FROM scored_customers s
JOIN TELCO_RA.MARTS.DIM_CUSTOMER d ON s.CUSTOMER_KEY = d.CUSTOMER_KEY
WHERE s.churn_probability >= 0.30
ORDER BY s.churn_probability DESC;

-- =============================================================================
-- Campaign Summary Queries
-- =============================================================================

-- View campaign breakdown by tier
SELECT 
    risk_tier,
    retention_offer,
    channel,
    COUNT(*) AS customers,
    ROUND(AVG(churn_probability), 3) AS avg_churn_prob,
    ROUND(AVG(COMPLAINT_COUNT), 1) AS avg_complaints,
    ROUND(SUM(lifetime_value_to_date), 0) AS total_ltv_at_risk
FROM TELCO_RA.MARTS.RETENTION_CAMPAIGN_HIGH_RISK
GROUP BY risk_tier, retention_offer, channel
ORDER BY avg_churn_prob DESC;

-- Export for CRM integration
SELECT 
    CUSTOMER_ID,
    risk_tier,
    retention_offer,
    channel,
    intervention_priority,
    churn_probability,
    COMPLAINT_COUNT,
    lifetime_value_to_date
FROM TELCO_RA.MARTS.RETENTION_CAMPAIGN_HIGH_RISK
ORDER BY intervention_priority, churn_probability DESC;
