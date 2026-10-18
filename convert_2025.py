"""
STADVDB MCO1 - 2025 Parquet to CSV Converter using DuckDB
Combines monthly TLC Parquet files into a single unified CSV (yellow_taxi_2025.csv).
"""

import glob
import shutil
from pathlib import Path
import duckdb

BASE_DIR = Path(__file__).resolve().parent
PARQUET_GLOB = str(BASE_DIR / "data" / "yellow_tripdata_2025-*.parquet")
OUTPUT_CSV = BASE_DIR / "yellow_taxi_2025.csv"
EXISTING_LARGE_CSV = BASE_DIR / "2025_Yellow_Taxi_Trip_Data_20261018.csv"

matched_parquets = glob.glob(PARQUET_GLOB)

if matched_parquets:
    print(f"Combining {len(matched_parquets)} 2025 Parquet files via DuckDB...")
    duckdb.sql(f"""
    COPY (
        SELECT *
        FROM read_parquet(
            '{PARQUET_GLOB.replace('\\', '/')}',
            union_by_name = true
        )
    )
    TO '{str(OUTPUT_CSV).replace('\\', '/')}'
    (FORMAT CSV, HEADER);
    """)
    print(f"DONE: {OUTPUT_CSV.name} created successfully.")

elif EXISTING_LARGE_CSV.exists():
    print(f"Found existing raw CSV: {EXISTING_LARGE_CSV.name} ({EXISTING_LARGE_CSV.stat().st_size / (1024**3):.2f} GB)")
    if not OUTPUT_CSV.exists():
        print(f"Creating symlink/alias {OUTPUT_CSV.name} -> {EXISTING_LARGE_CSV.name}...")
        try:
            OUTPUT_CSV.symlink_to(EXISTING_LARGE_CSV.name)
            print("Symlink created.")
        except (OSError, NotImplementedError):
            print(f"Note: Run pipeline directly with {EXISTING_LARGE_CSV.name} or set RAW_CSV_PATH in .env.")
    else:
        print(f"{OUTPUT_CSV.name} already exists.")
else:
    print("No input files found!")
    print(f" -> Expected Parquet files at: {PARQUET_GLOB}")
    print(f" -> Or CSV at: {OUTPUT_CSV} or {EXISTING_LARGE_CSV}")