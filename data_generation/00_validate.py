# data_generation/00_validate.py — sanity gate before Snowflake load
import pandas as pd

usage   = pd.read_parquet("data/raw/fact_usage.parquet")
clean   = pd.read_parquet("data/raw/fact_billing_clean.parquet")
final   = pd.read_parquet("data/raw/fact_billing.parquet")
ledger  = pd.read_parquet("data/raw/anomaly_ledger.parquet")

usage_total = round(usage["expected_charge"].sum(), 2)
clean_usage = round(clean.loc[clean.charge_type.eq("USAGE"), "billed_amount"].sum(), 2)
assert abs(usage_total - clean_usage) < 1.0, "clean billing must tie to usage"

impact = round(ledger["amount_impact"].sum(), 2)
assert abs((final.billed_amount.sum() - clean.billed_amount.sum()) - impact) < 1.0, \
    "every rupee of deviation must be in the ledger"

print("OK — usage ties to clean billing; all deviation is ledgered")
print(f"rows  usage={len(usage):,}  billing={len(final):,}  ledger={len(ledger):,}")
print(ledger["anomaly_type"].value_counts())