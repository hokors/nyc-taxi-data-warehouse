"""
Vectorized Data Wrangling and Cleansing Pipeline for STADVDB MCO1.
Cleans raw taxi trip chunks, handles anomalies, generates surrogate keys,
and extracts datetime dimension attributes.
"""

import logging
from dataclasses import dataclass
from typing import Tuple
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
    Computes a deterministic integer surrogate key from a datetime series.
    Formula: Seconds elapsed since 2025-01-01 00:00:00 + 1.
    Guarantees unique surrogate keys fitting within 32-bit signed INT (< 2.14B).
    Missing / NaT values are mapped to -1.
    """
    # Second offset from base
    offsets = (series - BASE_DATETIME).dt.total_seconds()
    # Map valid to int offset + 1, invalid / NaT to -1
    keys = offsets.fillna(-2).astype("int64") + 1
    keys = keys.where(series.notna(), -1)
    return keys.astype("int32")


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
                "year",
                "quarter",
                "month",
                "day",
                "hour",
                "minute",
                "second",
                "is_weekend",
                "time_of_day",
            ]
        )

    df_dt = pd.DataFrame({"ts": valid_ts})
    df_dt["datetime_id"] = timestamp_to_surrogate_key(df_dt["ts"])
    df_dt["year"] = df_dt["ts"].dt.year
    df_dt["quarter"] = df_dt["ts"].dt.quarter
    df_dt["month"] = df_dt["ts"].dt.month
    df_dt["day"] = df_dt["ts"].dt.day
    df_dt["hour"] = df_dt["ts"].dt.hour
    df_dt["minute"] = df_dt["ts"].dt.minute
    df_dt["second"] = df_dt["ts"].dt.second
    df_dt["is_weekend"] = df_dt["ts"].dt.dayofweek >= 5
    df_dt["time_of_day"] = assign_time_of_day(df_dt["hour"])

    return df_dt.drop(columns=["ts"])


def transform_chunk(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame, TransformMetrics]:
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

    # VendorID: Map invalid/missing to -1
    df["vendor_id"] = (
        pd.to_numeric(df["VendorID"], errors="coerce")
        .fillna(-1)
        .astype("int32")
    )
    df["vendor_id"] = df["vendor_id"].where(df["vendor_id"].isin(VALID_VENDORS), -1)

    # RatecodeID: Map invalid/missing to -1
    df["ratecode_id"] = (
        pd.to_numeric(df["RatecodeID"], errors="coerce")
        .fillna(-1)
        .astype("int32")
    )
    df["ratecode_id"] = df["ratecode_id"].where(df["ratecode_id"].isin(VALID_RATECODES), -1)

    # payment_type: Map invalid/missing to -1
    df["payment_type_id"] = (
        pd.to_numeric(df["payment_type"], errors="coerce")
        .fillna(-1)
        .astype("int32")
    )
    df["payment_type_id"] = df["payment_type_id"].where(
        df["payment_type_id"].isin(VALID_PAYMENTS), -1
    )

    # PULocationID and DOLocationID: Map null or out-of-range (< 1 or > 265) to -1
    df["pickup_location_id"] = (
        pd.to_numeric(df["PULocationID"], errors="coerce")
        .fillna(-1)
        .astype("int32")
    )
    df["pickup_location_id"] = df["pickup_location_id"].where(
        (df["pickup_location_id"] >= VALID_LOCATION_MIN)
        & (df["pickup_location_id"] <= VALID_LOCATION_MAX),
        -1,
    )

    df["dropoff_location_id"] = (
        pd.to_numeric(df["DOLocationID"], errors="coerce")
        .fillna(-1)
        .astype("int32")
    )
    df["dropoff_location_id"] = df["dropoff_location_id"].where(
        (df["dropoff_location_id"] >= VALID_LOCATION_MIN)
        & (df["dropoff_location_id"] <= VALID_LOCATION_MAX),
        -1,
    )

    # 7. Surrogate Key Mapping for Datetimes
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
        "payment_type_id",
        "vendor_id",
        "ratecode_id",
        "passenger_count",
        "trip_distance",
        "store_and_fwd_flag",
        "fare_amount",
        "extra",
        "mta_tax",
        "tip_amount",
        "tolls_amount",
        "improvement_surcharge",
        "congestion_surcharge",
        "cbd_congestion_fee",
        "airport_fee",
        "total_amount",
    ]

    # Handle case-sensitivity alias for Airport_fee
    if "Airport_fee" in df.columns and "airport_fee" not in df.columns:
        df["airport_fee"] = df["Airport_fee"]

    fact_df = df[fact_cols].copy()
    metrics.total_cleaned = len(fact_df)

    return fact_df, dim_datetime_df, metrics
