# STADVDB MCO1

This repository contains the source-database setup and supporting files for an NYC Yellow Taxi data project.

## Repository structure

- `database/` — raw source database definitions
- `etl/` — extraction, transformation, and loading scripts
- `olap/` — analytical query and OLAP work
- `dashboard/` — dashboard application files
- `tests/` — automated tests and data-quality checks
- `docs/` — project documentation
- `convert_2025.py` — combines the local 2025 Parquet files into a CSV
- `taxi_zone_lookup.csv` — trackable taxi-zone reference data
- `data_dictionary_trip_records_yellow.pdf` — trackable Yellow Taxi data dictionary

## Local data

Large local datasets are intentionally excluded from version control. Keep the source Parquet files in `data/`; running `convert_2025.py` creates `yellow_taxi_2025.csv` in the repository root. Both locations are ignored by Git.

## Source database

`database/source_schema.sql` defines only the raw `nyc_taxi_source` database and its two source tables. It does not define a dimensional, star, or snowflake warehouse schema.
