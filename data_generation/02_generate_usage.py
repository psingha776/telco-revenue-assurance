# data_generation/02_generate_usage.py
"""Event-level usage (CDRs) -> data/raw/fact_usage.parquet.
   Each event carries expected_charge (linear: units * per-unit rate)."""
import numpy as np
import pandas as pd
from config import SEED, EVENTS_PER_CUST_MONTH 

rng = np.random.default_rng(SEED + 1)  # offset the seed per file for independence


def active_months(customers: pd.DataFrame, date_dim: pd.DataFrame) -> pd.DataFrame:
    # Ensure consistent datetime types
    customers = customers.copy()
    date_dim = date_dim.copy()
    customers['signup_date'] = pd.to_datetime(customers['signup_date'])
    customers['churn_date'] = pd.to_datetime(customers['churn_date'])
    date_dim['month_start'] = pd.to_datetime(date_dim['month_start'])
    
    # Get unique month_start values sorted chronologically
    months_df = date_dim[['month_start']].drop_duplicates().sort_values('month_start').reset_index(drop=True)
    max_month = months_df['month_start'].max()
    
    # Prepare customers: extract relevant columns (include plan & segment)
    cust = customers[['customer_id', 'signup_date', 'churn_date', 'base_plan_id', 'segment']].copy()
    
    # Convert signup_date to the first day of its month
    cust['signup_month'] = pd.to_datetime(cust['signup_date']).dt.to_period('M').dt.to_timestamp()
    
    # Convert churn_date to the first day of its month (or max_month if NULL)
    cust['churn_month'] = pd.to_datetime(cust['churn_date']).dt.to_period('M').dt.to_timestamp()
    cust['churn_month'] = cust['churn_month'].fillna(max_month)
    
    # Cross join: each customer with each month (vectorized via merge with key)
    cust['_key'] = 1
    months_df['_key'] = 1
    active = pd.merge(cust, months_df, on='_key').drop('_key', axis=1)
    
    # Filter: keep only months where month_start is within [signup_month, churn_month]
    active = active[
        (active['month_start'] >= active['signup_month']) &
        (active['month_start'] <= active['churn_month'])
    ]
    
    # Return customer_id, month_start and attributes needed for event generation
    return active[['customer_id', 'month_start', 'base_plan_id', 'segment']].reset_index(drop=True)


def generate_events(active: pd.DataFrame, plans: pd.DataFrame) -> pd.DataFrame:
    # → build per-type arrays with numpy and np.concatenate; avoid row loops.
    active = active.copy()
    # ensure month_start is datetime
    active['month_start'] = pd.to_datetime(active['month_start'])

    # Draw number of events per active customer-month
    counts = rng.poisson(EVENTS_PER_CUST_MONTH, size=len(active))
    total_events = int(counts.sum())
    if total_events == 0:
        return pd.DataFrame(
            columns=['usage_id', 'customer_id', 'usage_date', 'event_type', 'units', 'plan_id', 'expected_charge']
        )

    # Expand rows by repeating each active row index by its event count
    row_idx = np.repeat(np.arange(len(active)), counts)

    # Gather per-event arrays
    customer_ids = active['customer_id'].to_numpy()[row_idx]
    plan_ids = active['base_plan_id'].to_numpy()[row_idx]
    segments = active['segment'].to_numpy()[row_idx]
    month_starts = active['month_start'].to_numpy()[row_idx]

    # Event type selection probabilities by segment (rows correspond to events)
    # Default base probabilities: [VOICE, DATA, SMS]
    base_probs = np.array([0.5, 0.4, 0.1])
    seg_map = {
        'Consumer': np.array([0.5, 0.45, 0.05]),
        'SME':      np.array([0.4, 0.5, 0.1]),
        'Enterprise': np.array([0.3, 0.6, 0.1])
    }
    probs = np.vstack([seg_map.get(s, base_probs) for s in segments])
    # sample by inverse-CDF using a uniform draw per event
    u = rng.random(size=total_events)
    cum = probs.cumsum(axis=1)
    event_type_idx = (u[:, None] < cum).argmax(axis=1)
    event_types = np.array(['VOICE', 'DATA', 'SMS'])[event_type_idx]

    # Draw units per event using type-appropriate distributions
    units = np.empty(total_events, dtype=float)
    is_voice = event_type_idx == 0
    is_data = event_type_idx == 1
    is_sms = event_type_idx == 2

    if is_voice.any():
        units[is_voice] = rng.exponential(scale=3.0, size=is_voice.sum())
    if is_data.any():
        units[is_data] = rng.exponential(scale=0.2, size=is_data.sum())
    if is_sms.any():
        # SMS count: small Poisson, ensure at least 1
        sms_vals = rng.poisson(1.0, size=is_sms.sum()).astype(float)
        sms_vals = np.where(sms_vals < 1.0, 1.0, sms_vals)
        units[is_sms] = sms_vals

    # Place usage_date uniformly within the active month
    month_starts_pd = pd.to_datetime(month_starts)
    month_ends = (month_starts_pd + pd.offsets.MonthEnd(0))
    # compute days in month per event as integer array
    days_in_month = month_ends.day.to_numpy()
    # offsets: uniform integer in [0, days_in_month-1] per event (use random*days to support per-element highs)
    offsets = (rng.random(size=total_events) * days_in_month).astype(int)
    usage_dates = (month_starts_pd + pd.to_timedelta(offsets, unit='D')).normalize()

    # Build events DataFrame and attach plan rates
    events = pd.DataFrame({
        'customer_id': customer_ids,
        'usage_date': usage_dates,
        'event_type': event_types,
        'units': units,
        'plan_id': plan_ids
    })

    events["usage_date"] = events["usage_date"].dt.date

    # Ensure plans contains expected rate columns and join
    rate_cols = ['plan_id', 'per_min_rate', 'per_gb_rate', 'per_sms_rate']
    if not set(['plan_id']).issubset(plans.columns):
        raise ValueError('plans DataFrame must contain a `plan_id` column')
    # safe-guard missing rate columns by filling zeros
    for c in ['per_min_rate', 'per_gb_rate', 'per_sms_rate']:
        if c not in plans.columns:
            plans[c] = 0.0

    events = events.merge(plans[rate_cols], on='plan_id', how='left')

    # Select per-event rate using vectorized where and compute expected charge using np.multiply
    per_rate = np.where(
        events['event_type'].to_numpy() == 'VOICE',
        events['per_min_rate'].to_numpy(),
        np.where(
            events['event_type'].to_numpy() == 'DATA',
            events['per_gb_rate'].to_numpy(),
            events['per_sms_rate'].to_numpy()
        )
    )

    expected_charge = np.round(np.multiply(events['units'].to_numpy(), per_rate), 2)
    events['expected_charge'] = expected_charge

    events = events[['customer_id', 'usage_date', 'event_type', 'units', 'plan_id', 'expected_charge']]

    # Assign usage_id sequentially
    events.insert(0, 'usage_id', np.arange(1, len(events) + 1))
    return events


if __name__ == "__main__":
    customers = pd.read_parquet("data/raw/dim_customer.parquet")
    plans     = pd.read_parquet("data/raw/dim_plan.parquet")
    dates     = pd.read_parquet("data/raw/dim_date.parquet")
    active    = active_months(customers, dates)
    usage     = generate_events(active, plans)
    usage.to_parquet("data/raw/fact_usage.parquet", index=False)
    print(f"usage rows: {len(usage):,}")