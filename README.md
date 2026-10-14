# STADVDB MCO1

This repository contains the raw source-database setup and supporting files for the NYC Yellow Taxi project.

## Repository Structure

- `database/` - raw source database definitions
- `etl/` - extraction, transformation, and loading scripts
- `olap/` - analytical and OLAP work
- `dashboard/` - dashboard files
- `tests/` - tests and data-quality checks
- `docs/` - project documentation
- `taxi_zone_lookup.csv` - taxi-zone reference data
- `data_dictionary_trip_records_yellow.pdf` - Yellow Taxi data dictionary

## Warehouse Schema

The warehouse schema is implemented in `database/warehouse_schema.sql` and uses the `nyc_taxi_warehouse` database. It follows a star schema with this grain: one row in `fact_taxi_rides` represents one taxi ride.

The central fact table is `fact_taxi_rides`. Its dimensions are:

- `dim_datetime`
- `dim_location`
- `dim_payment_type`
- `dim_vendor`
- `dim_ratecode`

The fact table uses the following dimension relationships:

- `pickup_datetime_id` and `dropoff_datetime_id` reference `dim_datetime`.
- `pickup_location_id` and `dropoff_location_id` reference `dim_location`.
- `payment_type_id`, `vendor_id`, and `ratecode_id` reference their corresponding dimensions.

## Current Project Status

- Source database setup: completed
- Source dataset import: completed
- Star schema design: completed
- Warehouse tables and PK/FK relationships: completed
- Next step: ETL to populate the dimensions and `fact_taxi_rides`

## Dataset Setup

`yellow_taxi_2025.csv` is several gigabytes and is too large for GitHub. Download it from our shared Google Drive:

[GOOGLE DRIVE LINK HERE]

After cloning this repository, place the downloaded file in the repository root. The result should look like this:

```text
STADVDB_MCO1/
├── yellow_taxi_2025.csv
├── taxi_zone_lookup.csv
├── database/
└── README.md
```

The dataset is listed in `.gitignore`, so it will not be committed accidentally.

## MySQL Setup

These instructions use MySQL 8.0. In Windows paths inside SQL, use forward slashes (`/`).

### 1. Create the source database and tables

Open and run `database/source_schema.sql` in MySQL. It creates:

- `nyc_taxi_source`
- `yellow_taxi_trips`
- `taxi_zone_lookup`

### 2. Enable local file imports

Check whether `local_infile` is enabled:

```sql
SHOW GLOBAL VARIABLES LIKE 'local_infile';
```

If its value is `OFF`, run the following command using an account with sufficient privileges, then reconnect to MySQL:

```sql
SET GLOBAL local_infile = 1;
```

If you use MySQL Workbench and local imports still fail, edit the connection, open **Advanced**, add `OPT_LOCAL_INFILE=1` under **Others**, and reconnect.

### 3. Import `yellow_taxi_2025.csv`

Change the path below to the actual location of the repository on your computer, then run the entire statement:

```sql
USE nyc_taxi_source;

LOAD DATA LOCAL INFILE 'C:/path/to/STADVDB_MCO1/yellow_taxi_2025.csv'
INTO TABLE yellow_taxi_trips
CHARACTER SET utf8mb4
FIELDS TERMINATED BY ','
OPTIONALLY ENCLOSED BY '"'
LINES TERMINATED BY '\n'
IGNORE 1 LINES
(
    @VendorID,
    @tpep_pickup_datetime,
    @tpep_dropoff_datetime,
    @passenger_count,
    @trip_distance,
    @RatecodeID,
    @store_and_fwd_flag,
    @PULocationID,
    @DOLocationID,
    @payment_type,
    @fare_amount,
    @extra,
    @mta_tax,
    @tip_amount,
    @tolls_amount,
    @improvement_surcharge,
    @total_amount,
    @congestion_surcharge,
    @Airport_fee,
    @cbd_congestion_fee
)
SET
    VendorID = NULLIF(@VendorID, ''),
    tpep_pickup_datetime = NULLIF(@tpep_pickup_datetime, ''),
    tpep_dropoff_datetime = NULLIF(@tpep_dropoff_datetime, ''),
    passenger_count = NULLIF(@passenger_count, ''),
    trip_distance = NULLIF(@trip_distance, ''),
    RatecodeID = NULLIF(@RatecodeID, ''),
    store_and_fwd_flag = NULLIF(@store_and_fwd_flag, ''),
    PULocationID = NULLIF(@PULocationID, ''),
    DOLocationID = NULLIF(@DOLocationID, ''),
    payment_type = NULLIF(@payment_type, ''),
    fare_amount = NULLIF(@fare_amount, ''),
    extra = NULLIF(@extra, ''),
    mta_tax = NULLIF(@mta_tax, ''),
    tip_amount = NULLIF(@tip_amount, ''),
    tolls_amount = NULLIF(@tolls_amount, ''),
    improvement_surcharge = NULLIF(@improvement_surcharge, ''),
    total_amount = NULLIF(@total_amount, ''),
    congestion_surcharge = NULLIF(@congestion_surcharge, ''),
    Airport_fee = NULLIF(@Airport_fee, ''),
    cbd_congestion_fee = NULLIF(TRIM(TRAILING '\r' FROM @cbd_congestion_fee), '');
```

### 4. Import `taxi_zone_lookup.csv`

Change this path to match your local repository path:

```sql
LOAD DATA LOCAL INFILE 'C:/path/to/STADVDB_MCO1/taxi_zone_lookup.csv'
INTO TABLE taxi_zone_lookup
CHARACTER SET utf8mb4
FIELDS TERMINATED BY ','
OPTIONALLY ENCLOSED BY '"'
LINES TERMINATED BY '\r\n'
IGNORE 1 LINES
(LocationID, Borough, Zone, service_zone);
```

### 5. Verify the imports

Use small result sets so MySQL does not try to display the full tables:

```sql
SELECT * FROM yellow_taxi_trips LIMIT 5;
SELECT * FROM taxi_zone_lookup LIMIT 5;
```
