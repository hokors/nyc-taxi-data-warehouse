"""
STADVDB MCO1 - Production ETL Pipeline CLI Runner
Orchestrates end-to-end extraction, wrangling, dimension seeding, and fact batch loading.
"""

import argparse
import logging
import sys
import time
from datetime import datetime
from tqdm import tqdm

from etl import config
from etl.db import check_db_connections, get_raw_connection
from etl.extract import extract_chunks, get_source_row_count
from etl.load_dimensions import (
    load_dim_datetime_batch,
    load_dim_location_from_csv,
    seed_static_dimensions,
)
from etl.load_facts import load_facts_batch, truncate_warehouse_facts
from etl.transform import transform_chunk

# Configure logging
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("ETL_Pipeline")


def parse_args():
    parser = argparse.ArgumentParser(
        description="STADVDB MCO1 - NYC Yellow Taxi High-Performance ETL Pipeline"
    )
    parser.add_argument(
        "--mode",
        choices=["db", "csv"],
        default=config.EXTRACT_MODE,
        help="Extraction source mode: 'db' (MySQL source table) or 'csv' (flat raw CSV)",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=config.CHUNK_SIZE,
        help=f"Number of rows per streaming batch (default: {config.CHUNK_SIZE})",
    )
    parser.add_argument(
        "--limit-chunks",
        type=int,
        default=None,
        help="Optional limit on number of chunks to process (useful for dry runs and testing)",
    )
    parser.add_argument(
        "--skip-dimensions",
        action="store_true",
        help="Skip re-seeding static dimensions and location lookups",
    )
    parser.add_argument(
        "--truncate-facts",
        action="store_true",
        help="Truncate fact_taxi_rides before running the pipeline",
    )
    return parser.parse_args()


def run_pipeline():
    args = parse_args()

    print("\n" + "=" * 78)
    print("       STADVDB MCO1 — NYC YELLOW TAXI DATA WAREHOUSE ETL PIPELINE")
    print("=" * 78)
    print(f" Timestamp:        {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f" Extraction Mode:  {args.mode.upper()}")
    print(f" Chunk Size:       {args.chunk_size:,} rows")
    print(f" Source DB:        {config.SOURCE_DB}.{config.SOURCE_TABLE}")
    print(f" Warehouse DB:     {config.WAREHOUSE_DB}")
    print(f" Limit Chunks:     {args.limit_chunks or 'None (Full Load)'}")
    print("=" * 78 + "\n")

    # Step 1: Health Check
    logger.info("Performing database connectivity pre-flight checks...")
    db_status = check_db_connections()
    if not db_status["warehouse"]:
        logger.error("Warehouse DB connection FAILED. Please check .env configuration.")
        for err in db_status["errors"]:
            logger.error(f" -> {err}")
        sys.exit(1)

    if args.mode == "db" and not db_status["source"]:
        logger.error("Source DB connection FAILED. Please check .env configuration.")
        for err in db_status["errors"]:
            logger.error(f" -> {err}")
        sys.exit(1)
    logger.info("Database connectivity verified.")

    # Step 2: Seed Dimensions
    if not args.skip_dimensions:
        logger.info("Step 1/3: Initializing and seeding warehouse dimensions...")
        seed_static_dimensions()
        load_dim_location_from_csv()
    else:
        logger.info("Step 1/3: Skipping dimension seeding as requested.")

    # Step 3: Truncate Facts if requested
    if args.truncate_facts:
        truncate_warehouse_facts()

    # Step 4: Stream and Process Chunks
    logger.info(f"Step 2/3: Starting chunked extraction and micro-batch loading (mode={args.mode})...")
    total_available_rows = get_source_row_count(args.mode)
    if total_available_rows > 0:
        logger.info(f"Total available source rows: {total_available_rows:,}")

    start_time = time.time()
    total_extracted = 0
    total_loaded = 0
    total_dt_inserted = 0

    # Cumulative rejection counters
    dropped_null_dt = 0
    dropped_duration = 0
    dropped_dates = 0
    dropped_financials = 0
    dropped_dups = 0

    chunk_count = 0
    warehouse_conn = get_raw_connection(config.WAREHOUSE_DB)

    try:
        total_chunks_est = (
            (total_available_rows // args.chunk_size) + 1
            if total_available_rows > 0
            else None
        )
        if args.limit_chunks and total_chunks_est:
            total_chunks_est = min(total_chunks_est, args.limit_chunks)

        pbar = tqdm(
            desc="Processing Chunks",
            total=total_chunks_est,
            unit="chunk",
            dynamic_ncols=True,
        )

        with warehouse_conn.cursor() as cursor:
            # Optimize session settings for batch load throughput
            cursor.execute("SET FOREIGN_KEY_CHECKS = 0;")
            cursor.execute("SET UNIQUE_CHECKS = 0;")

            for chunk_df in extract_chunks(mode=args.mode, chunk_size=args.chunk_size):
                chunk_count += 1
                chunk_raw_len = len(chunk_df)
                total_extracted += chunk_raw_len

                # Transform, clean, and generate surrogate keys
                fact_df, dim_datetime_df, metrics = transform_chunk(chunk_df)

                # Accumulate rejection metrics
                dropped_null_dt += metrics.dropped_null_datetime
                dropped_duration += metrics.dropped_inverted_duration
                dropped_dates += metrics.dropped_out_of_bounds_date
                dropped_financials += metrics.dropped_invalid_financials
                dropped_dups += metrics.dropped_duplicates

                # Micro-batch transaction
                try:
                    # 1. Upsert unique timestamps into dim_datetime
                    dt_count = load_dim_datetime_batch(cursor, dim_datetime_df)
                    total_dt_inserted += dt_count

                    # 2. Bulk insert cleaned facts into fact_taxi_rides
                    facts_inserted = load_facts_batch(cursor, fact_df)
                    total_loaded += facts_inserted

                    # Commit per chunk to free InnoDB undo/redo logs
                    warehouse_conn.commit()

                except Exception as batch_err:
                    warehouse_conn.rollback()
                    logger.error(f"Chunk #{chunk_count} failed during batch load: {batch_err}")
                    raise

                pbar.update(1)
                pbar.set_postfix({
                    "Extracted": f"{total_extracted:,}",
                    "Loaded": f"{total_loaded:,}",
                    "Speed": f"{total_loaded / max(1.0, time.time() - start_time):,.0f} r/s",
                })

                if args.limit_chunks and chunk_count >= args.limit_chunks:
                    logger.info(f"Reached chunk limit of {args.limit_chunks}. Halting extraction.")
                    break

            pbar.close()

            # Re-enable constraint checks
            cursor.execute("SET FOREIGN_KEY_CHECKS = 1;")
            cursor.execute("SET UNIQUE_CHECKS = 1;")
            warehouse_conn.commit()

    finally:
        warehouse_conn.close()

    elapsed = time.time() - start_time
    total_rejected = (
        dropped_null_dt
        + dropped_duration
        + dropped_dates
        + dropped_financials
        + dropped_dups
    )

    # Step 5: Final Execution Report
    print("\n" + "=" * 78)
    print("                      ETL PIPELINE EXECUTION SUMMARY")
    print("=" * 78)
    print(f" Status:                    SUCCESS")
    print(f" Total Elapsed Time:        {elapsed:.2f} seconds ({elapsed / 60:.2f} minutes)")
    print(f" Processing Throughput:     {total_loaded / max(0.1, elapsed):,.0f} rows/second")
    print("-" * 78)
    print(f" Chunks Processed:          {chunk_count:,}")
    print(f" Total Rows Extracted:      {total_extracted:,}")
    print(f" Total Fact Rows Loaded:    {total_loaded:,}")
    print(f" Total Unique Datetimes:    {total_dt_inserted:,}")
    print(f" Total Rows Rejected:       {total_rejected:,} ({total_rejected / max(1, total_extracted) * 100:.2f}%)")
    print("-" * 78)
    print(" Rejection Breakdown:")
    print(f"   • Missing / Corrupted Datetime:  {dropped_null_dt:,}")
    print(f"   • Inverted Duration (<= 0s):     {dropped_duration:,}")
    print(f"   • Non-2025 Calendar Date:        {dropped_dates:,}")
    print(f"   • Financial / Distance Outliers: {dropped_financials:,}")
    print(f"   • Deduplicated Transmissions:    {dropped_dups:,}")
    print("=" * 78 + "\n")


if __name__ == "__main__":
    run_pipeline()
