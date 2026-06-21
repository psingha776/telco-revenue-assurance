# data_generation/04_inject_anomalies.py
"""Inject revenue-leakage anomalies into clean billing.
   Writes fact_billing.parquet (final) and anomaly_ledger.parquet (answer key).
   Records amount_impact (billed - clean) for every change."""
import numpy as np
import pandas as pd
from config import (SEED, DUP_CHARGE_RATE, UNBILLED_USAGE_RATE,
                    RATING_ERROR_RATE, DOWNGRADE_PRE_CHURN)

rng = np.random.default_rng(SEED + 2)
_ledger = []  # collect dicts -> DataFrame at the end


def inject_duplicates(billing: pd.DataFrame) -> pd.DataFrame:
    # Filter to USAGE lines only
    usage_mask = billing['charge_type'] == 'USAGE'
    usage_lines = billing[usage_mask]
    
    if len(usage_lines) == 0:
        return billing
    
    # Sample DUP_CHARGE_RATE fraction of USAGE lines
    num_duplicates = max(1, int(len(usage_lines) * DUP_CHARGE_RATE))
    dup_indices = rng.choice(usage_lines.index, size=num_duplicates, replace=False)
    duplicates = billing.loc[dup_indices].copy()
    
    # Log each duplicate to _ledger before reassigning bill_id
    for _, row in duplicates.iterrows():
        _ledger.append({
            'bill_id': row['bill_id'],
            'customer_id': row['customer_id'],
            'bill_month': row['bill_month'],
            'charge_type': row['charge_type'],
            'anomaly_type': 'OVER_BILLING_DUPLICATE',
            'amount_impact': row['billed_amount'],
            'detail': 'Duplicate charge'
        })
    
    # Reset bill_id for duplicates to be sequential
    max_bill_id = billing['bill_id'].max()
    duplicates['bill_id'] = range(max_bill_id + 1, max_bill_id + 1 + len(duplicates))
    
    # Append duplicates to billing
    billing = pd.concat([billing, duplicates], ignore_index=True)
    
    return billing


def inject_unbilled(billing: pd.DataFrame) -> pd.DataFrame:
    """Sample UNBILLED_USAGE_RATE of USAGE lines; reduce billed_amount.
    Log UNBILLED_USAGE_LEAKAGE, amount_impact = new - old (negative)."""
    
    # Filter to USAGE lines only
    usage_mask = billing['charge_type'] == 'USAGE'
    usage_lines = billing[usage_mask]
    
    if len(usage_lines) == 0:
        return billing
    
    # Sample UNBILLED_USAGE_RATE fraction of USAGE lines
    num_unbilled = max(1, int(len(usage_lines) * UNBILLED_USAGE_RATE))
    unbilled_indices = rng.choice(usage_lines.index, size=num_unbilled, replace=False)
    
    # Log each unbilled line before modification
    for idx in unbilled_indices:
        row = billing.loc[idx]
        old_amount = row['billed_amount']
        new_amount = 0.0  # Unbilled = no charge
        amount_impact = new_amount - old_amount  # negative
        
        _ledger.append({
            'bill_id': row['bill_id'],
            'customer_id': row['customer_id'],
            'bill_month': row['bill_month'],
            'charge_type': row['charge_type'],
            'anomaly_type': 'UNBILLED_USAGE_LEAKAGE',
            'amount_impact': amount_impact,
            'detail': f'Unbilled usage; removed {old_amount:.2f}'
        })
        
        # Update the billed_amount in billing
        billing.loc[idx, 'billed_amount'] = new_amount
    
    return billing


def inject_rating_errors(billing: pd.DataFrame, plans: pd.DataFrame) -> pd.DataFrame:
    """Sample RATING_ERROR_RATE of USAGE lines; rescale billed_amount by
    (neighbour_rate / original_rate). Log RATING_ERROR with a detail string."""
    
    # Filter to USAGE lines only
    usage_mask = billing['charge_type'] == 'USAGE'
    usage_lines = billing[usage_mask]
    
    if len(usage_lines) == 0:
        return billing
    
    # Sample RATING_ERROR_RATE fraction of USAGE lines
    num_errors = max(1, int(len(usage_lines) * RATING_ERROR_RATE))
    error_indices = rng.choice(usage_lines.index, size=num_errors, replace=False)
    
    for idx in error_indices:
        row = billing.loc[idx]
        original_plan_id = row['plan_id']
        
        # Find a neighbour plan (different from current)
        other_plans = plans[plans['plan_id'] != original_plan_id]
        if len(other_plans) == 0:
            continue
        
        # Pick random neighbour plan
        neighbour_idx = rng.choice(len(other_plans))
        neighbour_plan_id = other_plans.iloc[neighbour_idx]['plan_id']
        
        # Derive rates: aggregate of the 3 different types of rates (per_min, per_gb, per_sms)
        original_plan = plans[plans['plan_id'] == original_plan_id].iloc[0]
        neighbour_plan = plans[plans['plan_id'] == neighbour_plan_id].iloc[0]
        original_rate = original_plan['per_min_rate'] + original_plan['per_gb_rate'] + original_plan['per_sms_rate']
        neighbour_rate = neighbour_plan['per_min_rate'] + neighbour_plan['per_gb_rate'] + neighbour_plan['per_sms_rate']
        
        # Calculate rescaled amount and impact
        old_amount = row['billed_amount']
        rate_factor = neighbour_rate / original_rate if original_rate != 0 else 1.0
        new_amount = old_amount * rate_factor
        amount_impact = new_amount - old_amount
        
        # Log the rating error
        _ledger.append({
            'bill_id': row['bill_id'],
            'customer_id': row['customer_id'],
            'bill_month': row['bill_month'],
            'charge_type': row['charge_type'],
            'anomaly_type': 'RATING_ERROR',
            'amount_impact': amount_impact,
            'detail': f'Rated at plan {neighbour_plan_id} instead of {original_plan_id}; factor {rate_factor:.3f}'
        })
        
        # Update billing amount
        billing.loc[idx, 'billed_amount'] = new_amount
    
    return billing


def inject_downgrades(billing: pd.DataFrame, customers: pd.DataFrame,
                      plans: pd.DataFrame) -> pd.DataFrame:
    """For DOWNGRADE_PRE_CHURN of churners, last 1-2 active months:
    switch RENTAL plan_id to next-cheaper same-type plan, lower rental.
    Log PRE_CHURN_DOWNGRADE (amount_impact = rental delta)."""
    
    # Filter to RENTAL lines only
    rental_mask = billing['charge_type'] == 'RENTAL'
    
    # Filter to churners only
    churners = customers[customers['churn_flag'] == True].copy()
    
    if len(churners) == 0:
        return billing
    
    # Sample DOWNGRADE_PRE_CHURN rate of churners
    num_downgrades = max(1, int(len(churners) * DOWNGRADE_PRE_CHURN))
    downgrade_indices = rng.choice(len(churners), size=num_downgrades, replace=False)
    churners_to_downgrade = churners.iloc[downgrade_indices]
    
    # Sort plans by monthly_rental for easy "next-cheaper" lookup
    plans_sorted = plans.sort_values('monthly_rental')
    
    # For each churner to downgrade
    for _, churner in churners_to_downgrade.iterrows():
        customer_id = churner['customer_id']
        churn_date = churner['churn_date']
        
        # Get customer's RENTAL billing lines (in temporal order)
        customer_rentals = billing[(billing['customer_id'] == customer_id) & 
                                    (billing['charge_type'] == 'RENTAL')].copy()
        
        if len(customer_rentals) == 0:
            continue
        
        # Sort by bill_month to find last 1-2 months
        customer_rentals = customer_rentals.sort_values('bill_month')
        
        # Randomly pick last 1 or 2 months to downgrade
        num_months = rng.choice([1, 2])
        last_months = customer_rentals.tail(num_months)
        
        for idx, row in last_months.iterrows():
            old_plan_id = row['plan_id']
            old_rental = row['billed_amount']
            bill_month = row['bill_month']
            
            # Get current plan's type
            plan_info = plans[plans['plan_id'] == old_plan_id]
            if len(plan_info) == 0:
                continue
            
            plan_type = plan_info.iloc[0]['plan_type']
            
            # Find all plans of same type, sorted by rental
            same_type_plans = plans_sorted[plans_sorted['plan_type'] == plan_type]
            
            # Find next-cheaper plan (highest rental less than current)
            cheaper_plans = same_type_plans[same_type_plans['monthly_rental'] < old_rental]
            
            if len(cheaper_plans) == 0:
                continue
            
            # Pick the most expensive of the cheaper plans (next-cheaper step down)
            new_plan = cheaper_plans.iloc[-1]
            new_plan_id = new_plan['plan_id']
            new_rental = new_plan['monthly_rental']
            
            amount_impact = new_rental - old_rental  # negative (downgrade)
            
            # Log the downgrade (matching schema from decisions.md)
            _ledger.append({
                'customer_id': customer_id,
                'bill_month': bill_month,
                'charge_type': 'RENTAL',
                'anomaly_type': 'PRE_CHURN_DOWNGRADE',
                'amount_impact': amount_impact,
                'detail': f'Downgrade from {old_plan_id} to {new_plan_id}'
            })
            
            # Update billing: change plan_id and rental amount
            billing.loc[idx, 'plan_id'] = new_plan_id
            billing.loc[idx, 'billed_amount'] = new_rental
    
    return billing


if __name__ == "__main__":
    billing   = pd.read_parquet("data/raw/fact_billing_clean.parquet")
    customers = pd.read_parquet("data/raw/dim_customer.parquet")
    plans     = pd.read_parquet("data/raw/dim_plan.parquet")

    billing = inject_duplicates(billing)
    billing = inject_unbilled(billing)
    billing = inject_rating_errors(billing, plans)
    billing = inject_downgrades(billing, customers, plans)

    billing.to_parquet("data/raw/fact_billing.parquet", index=False)
    pd.DataFrame(_ledger).to_parquet("data/raw/anomaly_ledger.parquet", index=False)
    print(f"final billing rows: {len(billing):,} | ledger rows: {len(_ledger):,}")