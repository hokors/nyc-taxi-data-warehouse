CREATE DATABASE IF NOT EXISTS nyc_taxi_warehouse;
USE nyc_taxi_warehouse;

CREATE TABLE dim_payment_type (
    payment_type_id INT PRIMARY KEY,
    payment_type_name VARCHAR(50)
);

CREATE TABLE dim_vendor (
    vendor_id INT PRIMARY KEY,
    vendor_name VARCHAR(100)
);

CREATE TABLE dim_ratecode (
    ratecode_id INT PRIMARY KEY,
    ratecode_name VARCHAR(100)
);

CREATE TABLE dim_location (
    location_id INT PRIMARY KEY,
    borough VARCHAR(50),
    zone VARCHAR(100),
    service_zone VARCHAR(50)
);

CREATE TABLE dim_datetime (
    datetime_id INT AUTO_INCREMENT PRIMARY KEY,
    year INT,
    quarter INT,
    month INT,
    day INT,
    hour INT,
    minute INT,
    second INT,
    is_weekend BOOLEAN,
    time_of_day VARCHAR(30)
);

CREATE TABLE fact_taxi_rides (
    ride_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    pickup_datetime_id INT,
    dropoff_datetime_id INT,
    pickup_location_id INT,
    dropoff_location_id INT,
    payment_type_id INT,
    vendor_id INT,
    ratecode_id INT,
    passenger_count INT,
    trip_distance DECIMAL(10,2),
    store_and_fwd_flag VARCHAR(1),
    fare_amount DECIMAL(10,2),
    extra DECIMAL(10,2),
    mta_tax DECIMAL(10,2),
    tip_amount DECIMAL(10,2),
    tolls_amount DECIMAL(10,2),
    improvement_surcharge DECIMAL(10,2),
    congestion_surcharge DECIMAL(10,2),
    cbd_congestion_fee DECIMAL(10,2),
    airport_fee DECIMAL(10,2),
    total_amount DECIMAL(10,2),

    FOREIGN KEY (pickup_datetime_id)
        REFERENCES dim_datetime(datetime_id),

    FOREIGN KEY (dropoff_datetime_id)
        REFERENCES dim_datetime(datetime_id),

    FOREIGN KEY (pickup_location_id)
        REFERENCES dim_location(location_id),

    FOREIGN KEY (dropoff_location_id)
        REFERENCES dim_location(location_id),

    FOREIGN KEY (payment_type_id)
        REFERENCES dim_payment_type(payment_type_id),

    FOREIGN KEY (vendor_id)
        REFERENCES dim_vendor(vendor_id),

    FOREIGN KEY (ratecode_id)
        REFERENCES dim_ratecode(ratecode_id)
);