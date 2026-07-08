# data_generation/03_generate_billing.py
import hashlib
import numpy as np
import pandas as pd


def roll_usage_to_month(usage: pd.DataFrame) -> pd.DataFrame:
    df = usage.copy()
    df['month_start'] = df['usage_date'].apply(lambda d: d.replace(day=1))
    return df.groupby(['customer_id', 'month_start']).agg(
        usage_amt=('expected_charge', 'sum')
    ).reset_index()


def build_clean_billing(usage_monthly: pd.DataFrame,
                        customers: pd.DataFrame,
                        plans: pd.DataFrame) -> pd.DataFrame:
    # → vectorised; build the two line-types as frames and concat.
    
    # Merge usage_monthly with customers to get base_plan_id
    usage_with_plan = usage_monthly.merge(
        customers[['customer_id', 'base_plan_id']],
        on='customer_id',
        how='left'
    )
    
    # Merge with plans to get monthly_rental
    usage_with_rental = usage_with_plan.merge(
        plans[['plan_id', 'monthly_rental']],
        left_on='base_plan_id',
        right_on='plan_id',
        how='left'
    )
    
    # Build RENTAL lines (one per active customer-month)
    rental = usage_with_rental[['customer_id', 'month_start', 'plan_id', 'monthly_rental']].copy()
    rental.rename(columns={'month_start': 'bill_month', 'monthly_rental': 'billed_amount'}, inplace=True)
    rental['charge_type'] = 'RENTAL'
    rental = rental[['customer_id', 'bill_month', 'charge_type', 'plan_id', 'billed_amount']]
    
    # Build USAGE lines (only for customer-months with usage > 0)
    usage_rows = usage_with_plan[usage_with_plan['usage_amt'] > 0].copy()
    usage = usage_rows[['customer_id', 'month_start', 'base_plan_id', 'usage_amt']].copy()
    usage.rename(columns={'month_start': 'bill_month', 'base_plan_id': 'plan_id', 'usage_amt': 'billed_amount'}, inplace=True)
    usage['charge_type'] = 'USAGE'
    usage = usage[['customer_id', 'bill_month', 'charge_type', 'plan_id', 'billed_amount']]
    
    # Concatenate RENTAL and USAGE frames
    billing = pd.concat([rental, usage], ignore_index=True)
    
    # Add bill_line_hash
    billing['bill_line_hash'] = add_hash(billing)
    
    # Add bill_id as sequential integer
    billing['bill_id'] = range(1, len(billing) + 1)
    
    # Reorder columns to match schema contract
    billing = billing[['bill_id', 'customer_id', 'bill_month', 'charge_type', 'plan_id', 'billed_amount', 'bill_line_hash']]
    
    return billing


def add_hash(df: pd.DataFrame) -> pd.Series:
    hash_input = (
        df['customer_id'].astype(str) + '|' +
        df['bill_month'].astype(str) + '|' +
        df['charge_type'].astype(str) + '|' +
        df['plan_id'].astype(str) + '|' +
        df['billed_amount'].round(2).astype(str)
    )
    return hash_input.apply(lambda x: hashlib.sha1(x.encode()).hexdigest())
    

if __name__ == "__main__":
    usage     = pd.read_parquet("data/raw/fact_usage.parquet")
    customers = pd.read_parquet("data/raw/dim_customer.parquet")
    plans     = pd.read_parquet("data/raw/dim_plan.parquet")
    billing   = build_clean_billing(roll_usage_to_month(usage), customers, plans)
    billing.to_parquet("data/raw/fact_billing_clean.parquet", index=False)
    print(f"clean billing rows: {len(billing):,}")