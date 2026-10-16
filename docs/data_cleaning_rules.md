# NYC Yellow Taxi Data Cleaning & Wrangling Specification
**Project:** STADVDB MCO1  
**Module:** Member 2 — ETL Pipeline Data Quality Specification  
**Version:** 1.0.0  

---

## 1. Overview & Objectives

The raw NYC TLC Yellow Taxi dataset contains dozens of millions of trip records collected from distinct taximeter technology providers (Creative Mobile Technologies, LLC and VeriFone Inc.). Due to sensor anomalies, meter transmission retries, and legacy clock synchronization issues, raw data contains noisy, invalid, and corrupted records.

The objectives of the wrangling pipeline in `etl/transform.py` are:
1. **Sanitize Data Integrity**: Eliminate records with logically impossible timestamps, inverted trip durations, or negative financials.
2. **Surrogate Key Harmonization**: Ensure 100% referential integrity with the dimensional warehouse (`nyc_taxi_warehouse`) without triggering MySQL foreign key constraint violations (`Error 1452`).
3. **Type Harmonization**: Resolve discrepancies between source and target schemas (e.g. `passenger_count` `DECIMAL(6,2)` in source &rarr; `INT` in warehouse).
4. **Deterministic Datetime Surrogate Generation**: Generate integer surrogate keys that fit safely inside standard 32-bit signed `INT` ($< 2.14\text{B}$) columns.

---

## 2. Attribute-by-Attribute Cleaning Rules Catalog

| Field Name | Raw Type / Condition | Validation Rule | Action Taken | Business Rationale |
| :--- | :--- | :--- | :--- | :--- |
| `tpep_pickup_datetime` | String / Datetime; empty / invalid | Must be a valid datetime in calendar year 2025 | Drop record | Non-2025 records represent meter clock reset bugs (e.g., 2008, 1970). Trips must align with project scope. |
| `tpep_dropoff_datetime` | String / Datetime; empty / invalid | Must be valid datetime, strictly after pickup datetime, duration $\le 24$ hours | Drop record | Negative or zero duration violates physical causality. Trips $> 24$ hours represent forgotten meter runs. |
| `passenger_count` | `DECIMAL(6, 2)`, NULL, or 0 | Integer within $[0, 9]$ | If NULL &rarr; 1; if $>9$ &rarr; 9; round to INT | Solo trips often have unrecorded passenger count; default to 1 passenger. Warehouse expects `INT`. |
| `trip_distance` | `DECIMAL(10, 2)`, negative or extreme | $0.0 \le \text{distance} \le 500.0$ miles | If negative &rarr; drop; if $> 500$ &rarr; drop | Distances cannot be negative. Trips $> 500$ miles in a yellow cab are GPS tracking errors or meter glitches. |
| `fare_amount` | `DECIMAL(10, 2)`, negative or extreme | $\$0.00 \le \text{fare} \le \$2,000.00$ | If negative &rarr; drop; if $> 2000$ &rarr; drop | Negative fares denote disputes or chargebacks handled outside standard operational ride analytics. |
| `total_amount` | `DECIMAL(10, 2)`, negative or extreme | $\$0.00 \le \text{total} \le \$3,000.00$ | If negative &rarr; drop; if $> 3000$ &rarr; drop | Prevents corrupted sums from distorting OLAP aggregate revenue analyses. |
| `extra`, `mta_tax`, `tip_amount`, `tolls_amount`, `surcharges` | `DECIMAL(10, 2)`, NULL / negative | Must be valid numeric $\ge \$0.00$ | Fill NULL with `0.00`; negative reset to `0.00` | Surcharges cannot reduce fare. Surcharge absence is interpreted as zero fee. |
| `store_and_fwd_flag` | `CHAR(1)`, NULL or dirty string | Must be `'Y'` or `'N'` | Strip whitespace, uppercase; if not `'Y'`, default to `'N'` | Standardizes binary flag across differing vendor encodings. |
| `VendorID` | `TINYINT`, NULL or unknown | Must be in $\{1, 2\}$ | If NULL or invalid &rarr; map to `-1` ("Unknown / Other") | Protects `dim_vendor` foreign key constraint. |
| `RatecodeID` | `TINYINT`, NULL or unknown | Must be in $\{1, 2, 3, 4, 5, 6, 99\}$ | If NULL or invalid &rarr; map to `-1` ("Unknown / Unspecified") | Protects `dim_ratecode` foreign key constraint. |
| `payment_type` | `TINYINT`, NULL or unknown | Must be in $\{1, 2, 3, 4, 5, 6\}$ | If NULL or invalid &rarr; map to `-1` ("Unknown / Unspecified") | Protects `dim_payment_type` foreign key constraint. |
| `PULocationID`, `DOLocationID` | `SMALLINT`, NULL or out of bounds | Must be within $[1, 265]$ | If NULL, $0$, or $> 265$ &rarr; map to `-1` ("Unknown Zone") | Protects `dim_location` foreign key constraint. |

---

## 3. Deduplication Logic

Raw taxi data frequently contains transmission duplicates when taximeters disconnect and re-transmit transactions over cellular networks.

**Composite Deduplication Key:**
```python
[
    "VendorID",
    "tpep_pickup_datetime",
    "tpep_dropoff_datetime",
    "PULocationID",
    "DOLocationID",
    "fare_amount"
]
```
Any identical occurrence within a chunk keeps the first record and drops subsequent duplicates (`keep='first'`).

---

## 4. Deterministic Datetime Surrogate Key Derivation

Standard natural timestamp keys such as `YYYYMMDDHHMMSS` require up to 14 decimal digits ($20,251,231,235,959$). In MySQL, a signed `INT` column supports values up to $2,147,483,647$ (approx. $2.14\times 10^9$). Storing 14 digits in an `INT` triggers an arithmetic overflow.

To resolve this without altering foreign key column data types across all fact and dimension tables, our ETL utilizes a **deterministic second-offset formula**:

$$\text{datetime\_id} = \text{int}\left( \text{timestamp} - \text{Timestamp('2025-01-01 00:00:00')} \right)_{\text{seconds}} + 1$$

* **Lower bound (2025-01-01 00:00:00)**: $\text{datetime\_id} = 1$
* **Upper bound (2025-12-31 23:59:59)**: $\text{datetime\_id} = 31,536,000$
* **Maximum 32-bit INT capacity**: $2,147,483,647$ (sufficient for $> 60$ operational years).
* **Missing / NaT timestamps**: Mapped to $-1$.

### Dimension Attribute Decomposition:
Each distinct timestamp is decomposed into:
* `year`: `timestamp.year`
* `quarter`: `timestamp.quarter`
* `month`: `timestamp.month`
* `day`: `timestamp.day`
* `hour`: `timestamp.hour`
* `minute`: `timestamp.minute`
* `second`: `timestamp.second`
* `is_weekend`: `timestamp.dayofweek >= 5`
* `time_of_day`:
  * `06:00 - 11:59` &rarr; `Morning`
  * `12:00 - 16:59` &rarr; `Afternoon`
  * `17:00 - 21:59` &rarr; `Evening`
  * `22:00 - 05:59` &rarr; `Night`

---

## 5. Rejection & Audit Metrics

For every processed batch, the pipeline logs rejection counts across 6 criteria via `TransformMetrics`:
1. `dropped_null_datetime`: Pickups or dropoffs that could not be parsed.
2. `dropped_inverted_duration`: Dropoffs occurring before or at pickup time, or trips exceeding 24 hours.
3. `dropped_out_of_bounds_date`: Pickups outside calendar year 2025.
4. `dropped_invalid_financials`: Negative fares, negative totals, or extreme outliers ($>\$2000$ fare, $>500$ miles).
5. `dropped_duplicates`: Duplicate meter transmissions.
6. `total_cleaned`: Successfully cleaned rows retained for warehouse fact insertion.
