"""
High-throughput transactional batch loader for fact_taxi_rides in STADVDB MCO1.
Executes micro-batch parameterized inserts with sub-batching to respect max_allowed_packet.
"""

import logging
from typing import Optional
import pandas as pd
from sqlalchemy import text

from etl import config
from etl.db import warehouse_engine

logger = logging.getLogger(__name__)

FACT_INSERT_SQL = """
    INSERT INTO fact_taxi_rides (
        pickup_datetime_id,
        dropoff_datetime_id,
        pickup_location_id,
        dropoff_location_id,
        payment_type_id,
        vendor_id,
        ratecode_id,
        passenger_count,
        trip_distance,
        store_and_fwd_flag,
        fare_amount,
        extra,
        mta_tax,
        tip_amount,
        tolls_amount,
        improvement_surcharge,
        congestion_surcharge,
        cbd_congestion_fee,
        airport_fee,
        total_amount
    ) VALUES (
        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
    );
"""


def truncate_warehouse_facts() -> None:
    """
    Safely truncates fact_taxi_rides to guarantee repeatable, idempotent pipeline runs.
    Temporarily disables foreign key checks to avoid constraint blocking.
    """
    logger.warning("Truncating fact_taxi_rides for fresh pipeline execution...")
    with warehouse_engine.connect() as conn:
        with conn.begin():
            conn.execute(text("SET FOREIGN_KEY_CHECKS = 0;"))
            conn.execute(text("TRUNCATE TABLE fact_taxi_rides;"))
            conn.execute(text("SET FOREIGN_KEY_CHECKS = 1;"))
    logger.info("fact_taxi_rides successfully truncated.")


def load_facts_batch(cursor, fact_df: pd.DataFrame, sub_batch_size: int = 25000) -> int:
    """
    Bulk-inserts fact records into fact_taxi_rides.
    Splits large chunks into sub-batches (default 25,000 rows) to stay safely
    within MySQL max_allowed_packet limits and maximize insertion throughput.
    """
    if fact_df.empty:
        return 0

    # Ensure correct column ordering
    ordered_cols = [
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
    df_ordered = fact_df[ordered_cols]

    total_rows = len(df_ordered)
    inserted_count = 0

    # Convert to list of tuples in memory-efficient slices
    for start_idx in range(0, total_rows, sub_batch_size):
        end_idx = min(start_idx + sub_batch_size, total_rows)
        slice_df = df_ordered.iloc[start_idx:end_idx]
        
        records = [
            (
                int(row.pickup_datetime_id),
                int(row.dropoff_datetime_id),
                int(row.pickup_location_id),
                int(row.dropoff_location_id),
                int(row.payment_type_id),
                int(row.vendor_id),
                int(row.ratecode_id),
                int(row.passenger_count),
                float(row.trip_distance),
                str(row.store_and_fwd_flag),
                float(row.fare_amount),
                float(row.extra),
                float(row.mta_tax),
                float(row.tip_amount),
                float(row.tolls_amount),
                float(row.improvement_surcharge),
                float(row.congestion_surcharge),
                float(row.cbd_congestion_fee),
                float(row.airport_fee),
                float(row.total_amount),
            )
            for row in slice_df.itertuples(index=False)
        ]

        cursor.executemany(FACT_INSERT_SQL, records)
        inserted_count += len(records)

    return inserted_count
