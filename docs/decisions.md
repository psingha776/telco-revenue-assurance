# Architecture Decision Records

## ADR-001: Snowflake over a local DB
Date: 2026-06-05
Options: PostgreSQL (local), Snowflake (cloud trial), DuckDB.
Snowflake over the rest because of previous affinity as well as cloud-warehouse exp gain. 30 day trial expiry is a challenge (needs a workaround).

## ADR-002: Hypothetical data selction rates
Date: 2026-06-15
DUP_CHARGE_RATE, UNBILLED_USAGE_RATE, RATING_ERROR_RATE: 1–3% revenue leakage is the industry benchmark for billing errors. I split it across over-billing and under-billing so both directions show up in the reconciliation

## ADR-003: Data model and grain
Date: 2026-06-16
| Table | Grain | ~Rows (default) | Purpose |
|---|---|---|---|
| `dim_customer` | one row per customer | 100,000 | tenure, region, segment, churn flag/date |
| `dim_plan` | one row per plan | ~24 | monthly rental, included minutes/GB, per-unit rates |
| `dim_date` | one row per day, 18 months | ~548 | calendar for time intelligence |
| `fact_usage` | one row per usage event (CDR) | ~2.7M | call/SMS/data events with derived expected charge |
| `fact_billing` | one row per bill line item / customer-month | ~2.0M | what was actually billed |

## ADR-004: raw file columns
Date: 2026-06-16
### `dim_plan.parquet` — ~24 rows *(file 01)*
| column | type | meaning |
|---|---|---|
| `plan_key` | int | surrogate, 1..N |
| `plan_id` | str | natural key, e.g. `PREPAID_S` |
| `plan_name` | str | display name |
| `plan_type` | str | `PREPAID` \| `POSTPAID` |
| `tier` | str | `S` \| `M` \| `L` |
| `monthly_rental` | float | fixed monthly fee |
| `incl_minutes` | int | descriptive only |
| `incl_gb` | float | descriptive only |
| `incl_sms` | int | descriptive only |
| `per_min_rate` | float | ₹/minute (voice rating) |
| `per_gb_rate` | float | ₹/GB (data rating) |
| `per_sms_rate` | float | ₹/SMS |
 
### `dim_customer.parquet` — 100,000 rows *(file 01)*
| column | type | meaning |
|---|---|---|
| `customer_key` | int | surrogate, 1..N |
| `customer_id` | str | natural key, `CUST00000001` |
| `region` | str | telecom circle, e.g. Metro/North/South/East/West |
| `segment` | str | `Consumer` \| `SME` \| `Enterprise` |
| `signup_date` | date | first day on network |
| `base_plan_id` | str | their standing plan (FK → dim_plan) |
| `tenure_months` | int | months from signup to churn (or to period end) |
| `churn_flag` | bool | ~18% true |
| `churn_date` | date | nullable; set iff churned |
| `complaint_count` | int | period total; higher for churners *(simplification — see note)* |
 
> **`complaint_count` note:** in a real model complaints are their own event fact. Here it's a period total on the customer so the churn features have something to bite on. One line in `decisions.md` covers you.
 
### `dim_date.parquet` — ~548 rows *(file 01)*
| column | type | meaning |
|---|---|---|
| `date_key` | int | `YYYYMMDD` |
| `date` | date | the day |
| `year` / `month` / `quarter` | int | calendar parts |
| `month_name` | str | `Jan`… |
| `day_of_week` | int | 0=Mon |
| `is_weekend` | bool | Sat/Sun |
| `month_start` | date | first of that month — **the join key to billing** |
 
### `fact_usage.parquet` — ~2.5–3M rows *(file 02)*
| column | type | meaning |
|---|---|---|
| `usage_id` | int | unique event id |
| `customer_id` | str | FK → dim_customer |
| `usage_date` | date | event date (within an active month) |
| `event_type` | str | `VOICE` \| `DATA` \| `SMS` |
| `units` | float | minutes (voice) \| GB (data) \| count (sms) |
| `plan_id` | str | plan in effect (FK → dim_plan) |
| `expected_charge` | float | `units × per_unit_rate`, 2 dp — **source of truth** |
 
### `fact_billing_clean.parquet` — ~2M rows *(file 03)*
| column | type | meaning |
|---|---|---|
| `bill_id` | int | unique line id |
| `customer_id` | str | FK → dim_customer |
| `bill_month` | date | month start — joins to usage month |
| `charge_type` | str | `RENTAL` \| `USAGE` |
| `plan_id` | str | plan billed that month |
| `billed_amount` | float | RENTAL = rental; USAGE = Σ expected_charge that month |
| `bill_line_hash` | str | sha1 of the line's identity — for duplicate detection |
 
### `fact_billing.parquet` — ~2M rows *(file 04, the one you load)*
Same schema as `fact_billing_clean`, but with anomalies injected. **No anomaly columns** — the truth lives only in the ledger, so your SQL has to *earn* the detection.
 
### `anomaly_ledger.parquet` — your answer key *(file 04)*
| column | type | meaning |
|---|---|---|
| `ledger_id` | int | row id |
| `customer_id` | str | who |
| `bill_month` | date | when |
| `charge_type` | str | affected line type (nullable) |
| `anomaly_type` | str | `OVER_BILLING_DUPLICATE` \| `UNBILLED_USAGE_LEAKAGE` \| `RATING_ERROR` \| `PRE_CHURN_DOWNGRADE` |
| `amount_impact` | float | billed − clean (₹). + = over-billed, − = under-billed |
| `detail` | str | human note, e.g. `rate from PREPAID_M applied to PREPAID_S` |

## ADR-005: .parquet over .xlsx or .csv
Date: 2026-06-16
Parquet files are better than Excel or CSV because they are designed for machine efficiency and big data, whereas Excel and CSV are designed for human readability and small datasets.

## ADR-006: Hypothetical data selction rates
Date: 2026-06-20
**`bill_line_hash`** - a deterministic fingerprint so exact duplicates are detectable in SQL:
sha1(f"{customer_id}|{bill_month}|{charge_type}|{plan_id}|{round(billed_amount,2)}")

## ADR-007: The four anomalies, precisely:
Date: 2026-06-16 
| anomaly | inject method | direction | reconciliation sees |
|---|---|---|---|
| **OVER_BILLING_DUPLICATE** | sample `DUP_CHARGE_RATE` of **USAGE** lines, append exact copies (same hash) | billed ↑ | `dup_lines > 0 AND gap > 0` |
| **UNBILLED_USAGE_LEAKAGE** | sample `UNBILLED_USAGE_RATE` of customer-months with usage; reduce the USAGE `billed_amount` (zero it, or drop 20–100%) | billed ↓ | `gap < -tolerance` |
| **RATING_ERROR** | sample `RATING_ERROR_RATE` of USAGE lines; recompute as if a **neighbouring plan's** per-unit rate applied | ↑ or ↓ | falls to the `RATING_VARIANCE` branch |
| **PRE_CHURN_DOWNGRADE** | for `DOWNGRADE_PRE_CHURN` of churners, in the last 1–2 active months set the RENTAL `plan_id` to the next-cheaper plan and lower the rental | rental ↓ | *not* a leakage — a **churn signal** via `LAG(plan_id)` |
 

