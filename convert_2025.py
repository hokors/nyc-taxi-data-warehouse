import duckdb

print("Combining 2025 Parquet files...")

duckdb.sql("""
COPY (
    SELECT *
    FROM read_parquet(
        'data/yellow_tripdata_2025-*.parquet',
        union_by_name = true
    )
)
TO 'yellow_taxi_2025.csv'
(FORMAT CSV, HEADER);
""")

print("DONE: yellow_taxi_2025.csv created")