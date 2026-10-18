"""
Dimension loader module for STADVDB MCO1.
Populates reference dimensions (vendor, ratecode, payment_type, location)
and provides streaming upserts for dim_datetime during ETL batch processing.
"""

import logging
from pathlib import Path
from typing import Optional
import pandas as pd
from sqlalchemy import text

from etl import config
from etl.db import get_raw_connection, warehouse_engine

logger = logging.getLogger(__name__)


def seed_static_dimensions() -> None:
    """
    Executes database/seed_dimensions.sql to ensure all TLC domain tables
    (dim_payment_type, dim_vendor, dim_ratecode, dim_location default fallback)
    are seeded with official codes and fallback surrogate records (-1).
    """
    seed_sql_path = config.BASE_DIR / "database" / "seed_dimensions.sql"
    if not seed_sql_path.exists():
        logger.warning(f"Seed script not found at {seed_sql_path}, falling back to inline seeding.")
        seed_inline_dimensions()
        return

    logger.info("Seeding static dimensions from database/seed_dimensions.sql...")
    with open(seed_sql_path, "r", encoding="utf-8") as f:
        statements = [stmt.strip() for stmt in f.read().split(";") if stmt.strip()]

    with warehouse_engine.connect() as conn:
        with conn.begin():
            for stmt in statements:
                # Skip USE database statement if using SQLAlchemy connection bound to warehouse
                if stmt.upper().startswith("USE"):
                    continue
                conn.execute(text(stmt))
    logger.info("Static reference dimensions successfully seeded.")


def seed_inline_dimensions() -> None:
    """Inline fallback seeder for static dimensions."""
    with warehouse_engine.connect() as conn:
        with conn.begin():
            # Vendors
            conn.execute(
                text(
                    """
                    INSERT INTO dim_vendor (vendor_id, vendor_name) VALUES
                        (1, 'Creative Mobile Technologies, LLC'),
                        (2, 'VeriFone Inc.'),
                        (-1, 'Unknown / Other')
                    ON DUPLICATE KEY UPDATE vendor_name = VALUES(vendor_name);
                    """
                )
            )
            # Payment types
            conn.execute(
                text(
                    """
                    INSERT INTO dim_payment_type (payment_type_id, payment_type_name) VALUES
                        (1, 'Credit card'),
                        (2, 'Cash'),
                        (3, 'No charge'),
                        (4, 'Dispute'),
                        (5, 'Unknown'),
                        (6, 'Voided trip'),
                        (-1, 'Unknown / Unspecified')
                    ON DUPLICATE KEY UPDATE payment_type_name = VALUES(payment_type_name);
                    """
                )
            )
            # Ratecodes
            conn.execute(
                text(
                    """
                    INSERT INTO dim_ratecode (ratecode_id, ratecode_name) VALUES
                        (1, 'Standard rate'),
                        (2, 'JFK'),
                        (3, 'Newark'),
                        (4, 'Nassau or Westchester'),
                        (5, 'Negotiated fare'),
                        (6, 'Group ride'),
                        (99, 'Special / Unknown'),
                        (-1, 'Unknown / Unspecified')
                    ON DUPLICATE KEY UPDATE ratecode_name = VALUES(ratecode_name);
                    """
                )
            )
            # Location Fallback
            conn.execute(
                text(
                    """
                    INSERT INTO dim_location (location_id, borough, zone, service_zone) VALUES
                        (-1, 'Unknown', 'Unknown / Unspecified', 'Unknown'),
                        (0, 'Unknown', 'Unknown / Default', 'Unknown')
                    ON DUPLICATE KEY UPDATE borough = VALUES(borough);
                    """
                )
            )
            # Datetime Fallback
            conn.execute(
                text(
                    """
                    INSERT INTO dim_datetime (
                        datetime_id, full_datetime, year, month, day, hour, time_of_day
                    ) VALUES (
                        0, '1970-01-01 00:00:00', 0, 0, 0, 0, 'Unknown'
                    ) ON DUPLICATE KEY UPDATE time_of_day = VALUES(time_of_day);
                    """
                )
            )


def load_dim_location_from_csv(csv_path: Optional[Path] = None) -> int:
    """
    Populates dim_location directly from taxi_zone_lookup.csv.
    Ensures all 265 official NYC taxi zones are present.
    """
    path = csv_path or config.LOOKUP_CSV_PATH
    if not path.exists():
        logger.warning(f"Lookup file {path} not found. Skipping CSV location loading.")
        return 0

    logger.info(f"Loading dim_location from {path}...")
    df_zones = pd.read_csv(path)
    
    # Standardize column naming
    col_mapping = {
        "LocationID": "location_id",
        "Borough": "borough",
        "Zone": "zone",
        "service_zone": "service_zone",
    }
    df_zones = df_zones.rename(columns=col_mapping)
    df_zones["location_id"] = pd.to_numeric(df_zones["location_id"], errors="coerce").astype(int)
    df_zones = df_zones.fillna("Unknown")

    insert_sql = """
        INSERT INTO dim_location (location_id, borough, zone, service_zone)
        VALUES (%s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            borough = VALUES(borough),
            zone = VALUES(zone),
            service_zone = VALUES(service_zone);
    """

    records = [
        (
            row["location_id"],
            str(row["borough"]),
            str(row["zone"]),
            str(row["service_zone"]),
        )
        for _, row in df_zones.iterrows()
    ]

    conn = get_raw_connection(config.WAREHOUSE_DB)
    try:
        with conn.cursor() as cursor:
            cursor.executemany(insert_sql, records)
        conn.commit()
        logger.info(f"Loaded {len(records)} locations into dim_location.")
        return len(records)
    finally:
        conn.close()


def load_dim_datetime_batch(
    cursor, dim_datetime_df: pd.DataFrame, sub_batch_size: int = 25000
) -> int:
    """
    Bulk-inserts unique decomposed datetime records into dim_datetime for the current chunk.
    Uses INSERT IGNORE so already-inserted timestamps are safely skipped.
    Executes in sub-batches (default 25,000 rows) to stay safely within max_allowed_packet.
    """
    if dim_datetime_df.empty:
        return 0

    insert_sql = """
        INSERT INTO dim_datetime (
            datetime_id,
            full_datetime,
            year,
            month,
            day,
            hour,
            time_of_day
        ) VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE time_of_day = VALUES(time_of_day);
    """

    records = [
        (
            int(r.datetime_id),
            r.full_datetime,
            int(r.year),
            int(r.month),
            int(r.day),
            int(r.hour),
            str(r.time_of_day),
        )
        for r in dim_datetime_df.itertuples(index=False)
    ]

    total_records = len(records)
    total_inserted = 0

    for start_idx in range(0, total_records, sub_batch_size):
        end_idx = min(start_idx + sub_batch_size, total_records)
        cursor.executemany(insert_sql, records[start_idx:end_idx])
        total_inserted += (end_idx - start_idx)

    return total_inserted

