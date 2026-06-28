from dotenv import load_dotenv
load_dotenv()

import os
import snowflake.connector

totp = input("Snowflake MFA code: ")

conn = snowflake.connector.connect(
    account         = os.environ["SF_ACCOUNT"],
    user            = os.environ["SF_USER"],
    password        = os.environ["SF_PASSWORD"],
    passcode        = totp,
    role            = "ACCOUNTADMIN",
    warehouse       = "COMPUTE_WH",
    database        = "TELCO_RA",
    schema          = "RAW",
)
cur = conn.cursor()

FILES = {   # RAW table : local parquet
    "DIM_PLAN":       "data/raw/dim_plan.parquet",
    "DIM_CUSTOMER":   "data/raw/dim_customer.parquet",
    "DIM_DATE":       "data/raw/dim_date.parquet",
    "FACT_USAGE":     "data/raw/fact_usage.parquet",
    "FACT_BILLING":   "data/raw/fact_billing.parquet",
    "ANOMALY_LEDGER": "data/raw/anomaly_ledger.parquet",
}

for table, path in FILES.items():
    abspath = os.path.abspath(path).replace("\\", "/")            # forward slashes for the file:// URI
    cur.execute(f"PUT 'file://{abspath}' @TELCO_RA.RAW.LANDING/{table}/ "
                f"OVERWRITE=TRUE AUTO_COMPRESS=FALSE")            # parquet is already compressed
    cur.execute(f"""
        COPY INTO TELCO_RA.RAW.{table}
        FROM @TELCO_RA.RAW.LANDING/{table}/
        FILE_FORMAT = (TYPE = PARQUET)
        MATCH_BY_COLUMN_NAME = CASE_INSENSITIVE
    """)
    cur.execute(f"SELECT COUNT(*) FROM TELCO_RA.RAW.{table}")
    row = cur.fetchone()
    n = row[0] if row else 0
    print(f"{table:16} {n:>10,} rows")

cur.close(); conn.close()