"""
Vectorized Data Wrangling and Cleansing Pipeline for STADVDB MCO1.
Cleans raw taxi trip chunks, handles anomalies, generates surrogate keys,
and extracts datetime dimension attributes.
"""

import logging
from dataclasses import dataclass
from typing import Tuple, Optional
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# Base reference date for deterministic datetime surrogate key calculation
BASE_DATETIME = pd.Timestamp("2025-01-01 00:00:00")

# Valid domain values per official TLC Data Dictionary
VALID_VENDORS = {1, 2}
VALID_RATECODES = {1, 2, 3, 4, 5, 6, 99}
VALID_PAYMENTS = {1, 2, 3, 4, 5, 6}
VALID_LOCATION_MIN = 1
VALID_LOCATION_MAX = 265


def get_valid_dimension_lookups() -> dict:
    """
    Loads active valid dimension primary keys from warehouse to enable dynamic lookups.
    """
    from etl.db import warehouse_engine
    from sqlalchemy import text

    lookups = {
        "locations": set(),
        "vendors": {1, 2},
        "ratecodes": {1, 2, 3, 4, 5, 6, 99},
        "payments": {1, 2, 3, 4, 5, 6},
    }
    try:
        with warehouse_engine.connect() as conn:
            loc_ids = conn.execute(text("SELECT location_id FROM dim_location")).scalars().all()
            if loc_ids:
                lookups["locations"] = set(loc_ids)
    except Exception as e:
        logger.warning(f"Could not load dynamic location lookup from DB: {e}. Falling back to default range.")

    if not lookups["locations"]:
        lookups["locations"] = set(range(1, 266))

    return lookups


@dataclass
class TransformMetrics:
    total_received: int = 0
    dropped_null_datetime: int = 0
    dropped_inverted_duration: int = 0
    dropped_out_of_bounds_date: int = 0
    dropped_invalid_financials: int = 0
    dropped_duplicates: int = 0
    total_cleaned: int = 0


def timestamp_to_surrogate_key(series: pd.Series) -> pd.Series:
    """
    Computes a deterministic integer hourly surrogate key: YYYYMMDDHH.
    Guarantees unique surrogate keys fitting within 32-bit signed INT (< 2.14B).
    Missing / NaT values are mapped to 0.
    """
    keys = (
        series.dt.year * 1000000
        + series.dt.month * 10000
        + series.dt.day * 100
        + series.dt.hour
    )
    return keys.fillna(0).astype("int64")


def assign_time_of_day(hours: pd.Series) -> pd.Series:
    """Categorizes hour into standardized time_of_day buckets."""
    conditions = [
        (hours >= 6) & (hours < 12),
        (hours >= 12) & (hours < 17),
        (hours >= 17) & (hours < 22),
    ]
    choices = ["Morning", "Afternoon", "Evening"]
    return pd.Series(np.select(conditions, choices, default="Night"), index=hours.index)


def decompose_datetime(timestamps: pd.Series) -> pd.DataFrame:
    """
    Decomposes a series of unique Timestamps into dim_datetime records.
    """
    valid_ts = timestamps.dropna().drop_duplicates()
    if valid_ts.empty:
        return pd.DataFrame(
            columns=[
                "datetime_id",
                "full_datetime",
                "year",
                "month",
                "day",
                "hour",
                "time_of_day",
            ]
        )

    df_dt = pd.DataFrame({"ts": valid_ts})
    df_dt["datetime_id"] = timestamp_to_surrogate_key(df_dt["ts"])
    df_dt["full_datetime"] = df_dt["ts"].dt.floor("h")
    df_dt["year"] = df_dt["ts"].dt.year
    df_dt["month"] = df_dt["ts"].dt.month
    df_dt["day"] = df_dt["ts"].dt.day
    df_dt["hour"] = df_dt["ts"].dt.hour
    df_dt["time_of_day"] = assign_time_of_day(df_dt["hour"])

    return df_dt.drop(columns=["ts"]).drop_duplicates(subset=["datetime_id"])


def transform_chunk(
    df: pd.DataFrame, dimension_lookups: Optional[dict] = None
) -> Tuple[pd.DataFrame, pd.DataFrame, TransformMetrics]:
    """
    Applies data wrangling, cleansing filters, and surrogate key mapping to a raw chunk.
    
    Returns:
        fact_df: Cleaned dataframe ready for batch insertion into fact_taxi_rides
        dim_datetime_df: Unique decomposed datetime records to upsert into dim_datetime
        metrics: TransformMetrics tracking record retention and rejection counts
    """
    metrics = TransformMetrics(total_received=len(df))
    if df.empty:
        return pd.DataFrame(), pd.DataFrame(), metrics

    df = df.copy()

    # 1. Parse Datetimes
    df["tpep_pickup_datetime"] = pd.to_datetime(df["tpep_pickup_datetime"], errors="coerce")
    df["tpep_dropoff_datetime"] = pd.to_datetime(df["tpep_dropoff_datetime"], errors="coerce")

    # Drop null datetimes
    null_dt_mask = df["tpep_pickup_datetime"].isna() | df["tpep_dropoff_datetime"].isna()
    metrics.dropped_null_datetime = int(null_dt_mask.sum())
    df = df[~null_dt_mask]
    if df.empty:
        return pd.DataFrame(), pd.DataFrame(), metrics

    # 2. Filter inverted or zero duration (dropoff must be strictly after pickup)
    # Also filter unrealistic long trips (> 24 hours)
    duration_seconds = (df["tpep_dropoff_datetime"] - df["tpep_pickup_datetime"]).dt.total_seconds()
    valid_duration = (duration_seconds > 0) & (duration_seconds <= 86400)
    metrics.dropped_inverted_duration = int((~valid_duration).sum())
    df = df[valid_duration]
    if df.empty:
        return pd.DataFrame(), pd.DataFrame(), metrics

    # 3. Calendar boundaries (trip pickup must be within calendar year 2025)
    valid_dates = (df["tpep_pickup_datetime"].dt.year == 2025) & (
        df["tpep_dropoff_datetime"] < pd.Timestamp("2026-01-02")
    )
    metrics.dropped_out_of_bounds_date = int((~valid_dates).sum())
    df = df[valid_dates]
    if df.empty:
        return pd.DataFrame(), pd.DataFrame(), metrics

    # 4. Numeric and Financial Validations
    for col in [
        "fare_amount",
        "extra",
        "mta_tax",
        "tip_amount",
        "tolls_amount",
        "improvement_surcharge",
        "total_amount",
        "congestion_surcharge",
        "Airport_fee",
        "cbd_congestion_fee",
        "trip_distance",
    ]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

    # Business rule: trips cannot have negative fare, negative distance, or negative total amount
    # Filter extreme outliers (> 500 miles, > $2000 fare, > $3000 total)
    valid_financials = (
        (df["fare_amount"] >= 0)
        & (df["fare_amount"] <= 2000)
        & (df["total_amount"] >= 0)
        & (df["total_amount"] <= 3000)
        & (df["trip_distance"] >= 0)
        & (df["trip_distance"] <= 500)
    )
    metrics.dropped_invalid_financials = int((~valid_financials).sum())
    df = df[valid_financials]
    if df.empty:
        return pd.DataFrame(), pd.DataFrame(), metrics

    # 5. Deduplication within chunk
    dup_cols = [
        "VendorID",
        "tpep_pickup_datetime",
        "tpep_dropoff_datetime",
        "PULocationID",
        "DOLocationID",
        "fare_amount",
    ]
    existing_cols = [c for c in dup_cols if c in df.columns]
    dups_mask = df.duplicated(subset=existing_cols, keep="first")
    metrics.dropped_duplicates = int(dups_mask.sum())
    df = df[~dups_mask]

    # 6. Categorical Cleansing & Foreign Key Harmonization
    # passenger_count: decimal in source, INT in warehouse. Fill nulls with 1, clip [0, 9]
    df["passenger_count"] = (
        pd.to_numeric(df["passenger_count"], errors="coerce")
        .fillna(1)
        .round()
        .clip(0, 9)
        .astype("int32")
    )

    # store_and_fwd_flag: standard 'Y' or 'N'
    df["store_and_fwd_flag"] = (
        df["store_and_fwd_flag"].astype(str).str.strip().str.upper()
    )
    df["store_and_fwd_flag"] = df["store_and_fwd_flag"].where(
        df["store_and_fwd_flag"].isin(["Y", "N"]), "N"
    )

    # Resolve dynamic or static dimension lookup sets
    valid_vendors = dimension_lookups.get("vendors", VALID_VENDORS) if dimension_lookups else VALID_VENDORS
    valid_ratecodes = dimension_lookups.get("ratecodes", VALID_RATECODES) if dimension_lookups else VALID_RATECODES
    valid_payments = dimension_lookups.get("payments", VALID_PAYMENTS) if dimension_lookups else VALID_PAYMENTS
    valid_locations = dimension_lookups.get("locations", set(range(1, 266))) if dimension_lookups else set(range(1, 266))

    # VendorID: Map invalid/missing to 0 (Unknown/Other)
    df["vendor_id"] = (
        pd.to_numeric(df["VendorID"], errors="coerce")
        .fillna(0)
        .astype("int32")
    )
    df["vendor_id"] = df["vendor_id"].where(df["vendor_id"].isin(valid_vendors), 0)

    # RatecodeID: Map invalid/missing to 0 (Unknown/Unspecified)
    df["ratecode_id"] = (
        pd.to_numeric(df["RatecodeID"], errors="coerce")
        .fillna(0)
        .astype("int32")
    )
    df["ratecode_id"] = df["ratecode_id"].where(df["ratecode_id"].isin(valid_ratecodes), 0)

    # payment_type: Map invalid/missing to 0 (Unknown/Unspecified)
    df["payment_type_id"] = (
        pd.to_numeric(df["payment_type"], errors="coerce")
        .fillna(0)
        .astype("int32")
    )
    df["payment_type_id"] = df["payment_type_id"].where(
        df["payment_type_id"].isin(valid_payments), 0
    )

    # PULocationID and DOLocationID: Dynamic lookup against valid locations (fallback: 0)
    df["pickup_location_id"] = (
        pd.to_numeric(df["PULocationID"], errors="coerce")
        .fillna(0)
        .astype("int32")
    )
    df["pickup_location_id"] = df["pickup_location_id"].where(
        df["pickup_location_id"].isin(valid_locations),
        0,
    )

    df["dropoff_location_id"] = (
        pd.to_numeric(df["DOLocationID"], errors="coerce")
        .fillna(0)
        .astype("int32")
    )
    df["dropoff_location_id"] = df["dropoff_location_id"].where(
        df["dropoff_location_id"].isin(valid_locations),
        0,
    )

    # Handle case-sensitivity alias for Airport_fee
    if "Airport_fee" in df.columns and "airport_fee" not in df.columns:
        df["airport_fee"] = df["Airport_fee"]
    elif "airport_fee" not in df.columns:
        df["airport_fee"] = 0.0

    if "cbd_congestion_fee" not in df.columns:
        df["cbd_congestion_fee"] = 0.0

    # Component fee aggregation and reconciliation
    # Total revenue must reflect fare plus all regulatory surcharges and tips
    calculated_total = (
        df["fare_amount"]
        + df.get("extra", 0.0)
        + df.get("mta_tax", 0.0)
        + df["tip_amount"]
        + df["tolls_amount"]
        + df.get("improvement_surcharge", 0.0)
        + df.get("congestion_surcharge", 0.0)
        + df["airport_fee"]
        + df["cbd_congestion_fee"]
    )
    # If raw total_amount is zero or null but components exist, impute with calculated sum
    df["total_amount"] = df["total_amount"].where(df["total_amount"] > 0, calculated_total)

    # 7. Surrogate Key Mapping for Datetimes (Hourly YYYYMMDDHH)
    df["pickup_datetime_id"] = timestamp_to_surrogate_key(df["tpep_pickup_datetime"])
    df["dropoff_datetime_id"] = timestamp_to_surrogate_key(df["tpep_dropoff_datetime"])

    # Extract unique timestamps for dim_datetime upsert
    unique_ts = pd.concat([df["tpep_pickup_datetime"], df["tpep_dropoff_datetime"]]).unique()
    dim_datetime_df = decompose_datetime(pd.Series(unique_ts))

    # 8. Align with fact_taxi_rides warehouse schema columns
    fact_cols = [
        "pickup_datetime_id",
        "dropoff_datetime_id",
        "pickup_location_id",
        "dropoff_location_id",
        "vendor_id",
        "ratecode_id",
        "payment_type_id",
        "passenger_count",
        "trip_distance",
        "fare_amount",
        "tip_amount",
        "tolls_amount",
        "total_amount",
        "airport_fee",
        "cbd_congestion_fee",
    ]

    fact_df = df[fact_cols].copy()
    metrics.total_cleaned = len(fact_df)

    return fact_df, dim_datetime_df, metrics

