"""
High-performance streaming extraction engine for STADVDB MCO1.
Streams multi-gigabyte NYC Yellow Taxi datasets in bounded memory chunks.
Supports both MySQL source table streaming and raw CSV streaming.
"""

import logging
from typing import Generator, Optional
import pandas as pd
from sqlalchemy import text

from etl import config
from etl.db import get_raw_connection, source_engine

logger = logging.getLogger(__name__)

# Standard schema column names for yellow taxi records
TAXI_COLUMNS = [
    "VendorID",
    "tpep_pickup_datetime",
    "tpep_dropoff_datetime",
    "passenger_count",
    "trip_distance",
    "RatecodeID",
    "store_and_fwd_flag",
    "PULocationID",
    "DOLocationID",
    "payment_type",
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
]


def get_source_row_count(mode: Optional[str] = None) -> int:
    """
    Returns the total number of records available for extraction.
    Used for progress bars and reconciliation.
    """
    extract_mode = (mode or config.EXTRACT_MODE).lower()
    if extract_mode == "db":
        try:
            with source_engine.connect() as conn:
                result = conn.execute(
                    text(f"SELECT COUNT(*) FROM {config.SOURCE_TABLE}")
                ).scalar()
                return int(result or 0)
        except Exception as e:
            logger.warning(f"Could not get row count from DB: {e}")
            return 0
    else:
        # Fast line count for CSV if file exists
        if config.RAW_CSV_PATH.exists():
            count = 0
            with open(config.RAW_CSV_PATH, "rb") as f:
                for line in f:
                    count += 1
            return max(0, count - 1)  # subtract header
        return 0


def extract_from_db(chunk_size: Optional[int] = None) -> Generator[pd.DataFrame, None, None]:
    """
    Streams data from MySQL nyc_taxi_source.yellow_taxi_trips using a server-side cursor (SSCursor).
    This streams directly over the socket in batches without loading the 3GB table into RAM.
    """
    chunk_size = chunk_size or config.CHUNK_SIZE
    logger.info(f"Starting DB extraction from {config.SOURCE_DB}.{config.SOURCE_TABLE} (chunk_size={chunk_size})")

    query = f"""
        SELECT 
            VendorID,
            tpep_pickup_datetime,
            tpep_dropoff_datetime,
            passenger_count,
            trip_distance,
            RatecodeID,
            store_and_fwd_flag,
            PULocationID,
            DOLocationID,
            payment_type,
            fare_amount,
            extra,
            mta_tax,
            tip_amount,
            tolls_amount,
            improvement_surcharge,
            total_amount,
            congestion_surcharge,
            Airport_fee,
            cbd_congestion_fee
        FROM {config.SOURCE_TABLE}
    """

    conn = get_raw_connection(config.SOURCE_DB, server_side_cursor=True)
    try:
        with conn.cursor() as cursor:
            cursor.execute(query)
            batch_num = 0
            while True:
                rows = cursor.fetchmany(chunk_size)
                if not rows:
                    break
                batch_num += 1
                df_chunk = pd.DataFrame(rows, columns=TAXI_COLUMNS)
                logger.debug(f"Extracted DB chunk #{batch_num}: {len(df_chunk)} rows")
                yield df_chunk
    finally:
        conn.close()


def extract_from_csv(chunk_size: Optional[int] = None) -> Generator[pd.DataFrame, None, None]:
    """
    Streams data from raw flat CSV (yellow_taxi_2025.csv) in bounded memory chunks.
    """
    chunk_size = chunk_size or config.CHUNK_SIZE
    csv_path = config.RAW_CSV_PATH

    if not csv_path.exists():
        raise FileNotFoundError(f"Raw CSV file not found at: {csv_path.resolve()}")

    logger.info(f"Starting CSV extraction from {csv_path} (chunk_size={chunk_size})")

    # Efficient chunked reader
    chunk_iterator = pd.read_csv(
        csv_path,
        chunksize=chunk_size,
        low_memory=False,
    )

    batch_num = 0
    for df_chunk in chunk_iterator:
        batch_num += 1
        logger.debug(f"Extracted CSV chunk #{batch_num}: {len(df_chunk)} rows")
        yield df_chunk


def extract_chunks(
    mode: Optional[str] = None, chunk_size: Optional[int] = None
) -> Generator[pd.DataFrame, None, None]:
    """
    Unified extraction interface. Routes to either DB streaming or CSV streaming based on configuration.
    """
    extract_mode = (mode or config.EXTRACT_MODE).lower()
    if extract_mode == "db":
        yield from extract_from_db(chunk_size)
    elif extract_mode == "csv":
        yield from extract_from_csv(chunk_size)
    else:
        raise ValueError(f"Invalid EXTRACT_MODE: '{extract_mode}'. Expected 'db' or 'csv'.")
