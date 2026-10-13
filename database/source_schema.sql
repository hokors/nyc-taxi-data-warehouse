CREATE DATABASE IF NOT EXISTS nyc_taxi_source;

USE nyc_taxi_source;

CREATE TABLE IF NOT EXISTS yellow_taxi_trips (
    VendorID TINYINT,
    tpep_pickup_datetime DATETIME,
    tpep_dropoff_datetime DATETIME,
    passenger_count DECIMAL(6, 2),
    trip_distance DECIMAL(10, 2),
    RatecodeID TINYINT,
    store_and_fwd_flag CHAR(1),
    PULocationID SMALLINT UNSIGNED,
    DOLocationID SMALLINT UNSIGNED,
    payment_type TINYINT,
    fare_amount DECIMAL(10, 2),
    extra DECIMAL(10, 2),
    mta_tax DECIMAL(10, 2),
    tip_amount DECIMAL(10, 2),
    tolls_amount DECIMAL(10, 2),
    improvement_surcharge DECIMAL(10, 2),
    total_amount DECIMAL(10, 2),
    congestion_surcharge DECIMAL(10, 2),
    Airport_fee DECIMAL(10, 2),
    cbd_congestion_fee DECIMAL(10, 2)
);

CREATE TABLE IF NOT EXISTS taxi_zone_lookup (
    LocationID SMALLINT UNSIGNED,
    Borough VARCHAR(50),
    Zone VARCHAR(100),
    service_zone VARCHAR(50)
);
