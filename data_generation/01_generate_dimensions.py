# data_generation/01_generate_dimensions.py
"""Generate the three dimensions as Parquet in data/raw/:
   dim_plan (~24), dim_customer (100k), dim_date (~548 days, 18 months)."""
import hashlib
from datetime import date
import numpy as np
import pandas as pd
from config import (N_CUSTOMERS, MONTHS, PLANS, SEED, START_DATE)

rng = np.random.default_rng(SEED)


def make_plans() -> pd.DataFrame:
    records = []
    # sensible defaults for included SMS by tier (descriptive only)
    incl_sms_by_tier = {"S": 100, "M": 300, "L": 1000}

    for i, (plan_id, vals) in enumerate(PLANS.items(), start=1):
        monthly_rental, incl_minutes, incl_gb, per_min_rate, per_gb_rate = vals

        parts = plan_id.split("_")
        plan_type = parts[0] if parts else ""
        tier = parts[1] if len(parts) > 1 else ""

        # human-friendly display name from the id
        plan_name = (plan_type.title() + " " + tier) if tier else plan_type.title()

        incl_sms = incl_sms_by_tier.get(tier, 0)

        # Derive an SMS rate from the voice rate (simple heuristic)
        per_sms_rate = round(per_min_rate * 0.5, 2)

        records.append({
            "plan_key": int(i),
            "plan_id": plan_id,
            "plan_name": plan_name,
            "plan_type": plan_type,
            "tier": tier,
            "monthly_rental": float(monthly_rental),
            "incl_minutes": int(incl_minutes),
            "incl_gb": float(incl_gb),
            "incl_sms": int(incl_sms),
            "per_min_rate": float(per_min_rate),
            "per_gb_rate": float(per_gb_rate),
            "per_sms_rate": float(per_sms_rate),
        })

    df = pd.DataFrame.from_records(records, columns=[
        "plan_key",
        "plan_id",
        "plan_name",
        "plan_type",
        "tier",
        "monthly_rental",
        "incl_minutes",
        "incl_gb",
        "incl_sms",
        "per_min_rate",
        "per_gb_rate",
        "per_sms_rate",
    ])

    return df


def make_customers(n: int) -> pd.DataFrame:
    plan_ids = np.array(list(PLANS.keys()), dtype=str)
    plan_rentals = np.array([vals[0] for vals in PLANS.values()], dtype=float)
    plan_types = np.array([pid.split("_")[0] for pid in plan_ids], dtype=str)
    plan_tiers = np.array([pid.split("_")[1] if "_" in pid else "" for pid in plan_ids], dtype=str)

    region_choices = np.array(["Metro", "North", "South", "East", "West"], dtype=str)
    region_weights = np.array([0.28, 0.20, 0.20, 0.16, 0.16], dtype=float)
    segment_choices = np.array(["Consumer", "SME", "Enterprise"], dtype=str)
    segment_weights = np.array([0.80, 0.15, 0.05], dtype=float)

    period_start = np.datetime64(f"{START_DATE.year:04d}-{START_DATE.month:02d}")
    signup_window_start = period_start + np.timedelta64(MONTHS - 24, "M")
    signup_offsets = rng.integers(0, 24, size=n)
    signup_months = signup_window_start + signup_offsets.astype("timedelta64[M]")
    signup_dates = signup_months.astype("datetime64[D]")

    period_end = period_start + np.timedelta64(MONTHS, "M")
    months_to_period_end = ((period_end - signup_months) / np.timedelta64(1, "M")).astype(int)
    churn_probs = np.where(
        months_to_period_end < 6, 0.32,
        np.where(months_to_period_end < 18, 0.20, 0.10)
    )
    churn_flag = rng.random(size=n) < churn_probs

    plan_weights = 1.0 / (plan_rentals + 1.0)
    plan_weights *= np.where(plan_types == "PREPAID", 4.0, 1.0)
    plan_weights *= np.where(plan_tiers == "S", 3.0, np.where(plan_tiers == "M", 2.0, 1.0))
    plan_weights /= plan_weights.sum()
    base_plan_id = rng.choice(plan_ids, size=n, p=plan_weights)

    relative_signup_month = ((signup_months - period_start) / np.timedelta64(1, "M")).astype(int)
    relative_signup_month = np.maximum(0, relative_signup_month)
    churn_offsets = rng.integers(low=relative_signup_month, high=MONTHS, size=n)
    churn_months = period_start + churn_offsets.astype("timedelta64[M]")
    churn_dates = churn_months.astype("datetime64[D]")
    churn_dates = np.where(churn_flag, churn_dates, np.datetime64("NaT"))

    tenure_months = np.where(
        churn_flag,
        ((churn_months - signup_months) / np.timedelta64(1, "M")).astype(int),
        months_to_period_end,
    ).astype(int)

    complaint_rate = 0.4 + 1.5 * churn_flag.astype(float)
    complaint_count = rng.poisson(complaint_rate, size=n).astype(int)

    df = pd.DataFrame({
        "customer_key": np.arange(1, n + 1, dtype=int),
        "customer_id": [f"CUST{i:08d}" for i in range(1, n + 1)],
        "region": rng.choice(region_choices, size=n, p=region_weights),
        "segment": rng.choice(segment_choices, size=n, p=segment_weights),
        "signup_date": pd.to_datetime(signup_dates),
        "base_plan_id": base_plan_id,
        "tenure_months": tenure_months,
        "churn_flag": churn_flag,
        "churn_date": pd.to_datetime(churn_dates),
        "complaint_count": complaint_count,
    })

    return df


def make_date_dim() -> pd.DataFrame:
    """One row per day for `MONTHS` months from `START_DATE`.
    date_key=YYYYMMDD, calendar parts, is_weekend, month_start."""
    start_ts = pd.Timestamp(START_DATE)
    end_ts = start_ts + pd.DateOffset(months=MONTHS) - pd.Timedelta(days=1)
    dates = pd.date_range(start=start_ts, end=end_ts, freq="D")

    df = pd.DataFrame({
        "date": dates,
        "date_key": dates.strftime("%Y%m%d").astype(int),
        "year": dates.year,
        "month": dates.month,
        "quarter": dates.quarter,
        "month_name": dates.strftime("%b"),
        "day_of_week": dates.weekday,
        "is_weekend": dates.weekday >= 5,
        "month_start": dates.to_period("M").to_timestamp().date,
    })

    # Ensure column order matches ADR-004
    df = df[[
        "date_key",
        "date",
        "year",
        "month",
        "quarter",
        "month_name",
        "day_of_week",
        "is_weekend",
        "month_start",
    ]]

    return df


if __name__ == "__main__":
    make_plans().to_parquet("data/raw/dim_plan.parquet", index=False)
    make_customers(N_CUSTOMERS).to_parquet("data/raw/dim_customer.parquet", index=False)
    make_date_dim().to_parquet("data/raw/dim_date.parquet", index=False)
    print("dims written")