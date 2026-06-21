from datetime import date

SCALE_TEST = False
N_CUSTOMERS = 1_000 if SCALE_TEST else 100_000
MONTHS      = 3     if SCALE_TEST else 18
SEED        = 42  # reproducibility
START_DATE  = date(2022, 1, 1)  # first day of the first month in the dim_date window
EVENTS_PER_CUST_MONTH = 2  # mean events per customer-month (Poisson lambda)

PLANS = {            # plan_id: (monthly_rental, incl_minutes, incl_gb, per_min, per_gb)
    # PREPAID plans: S/M/L tiers × Metro/North/South/East/West regions (15 total)
    "PREPAID_S_Metro":  (149,  200,   1,  0.80, 12.0),
    "PREPAID_S_North":  (139,  200,   1,  0.80, 12.0),
    "PREPAID_S_South":  (139,  200,   1,  0.80, 12.0),
    "PREPAID_S_East":   (149,  200,   1,  0.80, 12.0),
    "PREPAID_S_West":   (149,  200,   1,  0.80, 12.0),
    "PREPAID_M_Metro":  (299,  500,   3,  0.60, 10.0),
    "PREPAID_M_North":  (279,  500,   3,  0.60, 10.0),
    "PREPAID_M_South":  (279,  500,   3,  0.60, 10.0),
    "PREPAID_M_East":   (299,  500,   3,  0.60, 10.0),
    "PREPAID_M_West":   (299,  500,   3,  0.60, 10.0),
    "PREPAID_L_Metro":  (499, 1000,   5,  0.50,  9.0),
    "PREPAID_L_North":  (479, 1000,   5,  0.50,  9.0),
    "PREPAID_L_South":  (479, 1000,   5,  0.50,  9.0),
    "PREPAID_L_East":   (499, 1000,   5,  0.50,  9.0),
    "PREPAID_L_West":   (499, 1000,   5,  0.50,  9.0),
    # POSTPAID plans: S/M/L tiers × (3 major regions - no regional variance) (9 total)
    "POSTPAID_S":  (199,  400,   2,  0.75, 11.0),
    "POSTPAID_M":  (399,  900,   8,  0.50,  9.0),
    "POSTPAID_L":  (599, 1500,  15,  0.40,  8.0),
}

# --- hypothetical anamolies ---
DUP_CHARGE_RATE      = 0.015   # 1.5% of bill lines duplicated  -> over-billing
UNBILLED_USAGE_RATE  = 0.020   # 2.0% of usage never makes it to a bill -> leakage
RATING_ERROR_RATE    = 0.010   # 1.0% of bill lines mis-rated (wrong tariff applied)
DOWNGRADE_PRE_CHURN  = 0.60    # 60% of churners downgrade 1-2 months before leaving
TOLERANCE_INR        = 5.0     # reconciliation tolerance band