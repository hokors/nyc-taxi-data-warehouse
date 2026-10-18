USE nyc_taxi_warehouse;

SET SESSION tmp_table_size = 536870912;
SET SESSION max_heap_table_size = 536870912;
SET SESSION sql_mode = (SELECT REPLACE(@@sql_mode, 'ONLY_FULL_GROUP_BY', ''));

-- ==============================================================================
-- QUERY 1: Monthly & Time-of-Day Revenue
-- ==============================================================================
SET @start_time = NOW(6);

SELECT 
    dt.year,
    dt.month,
    dt.time_of_day,
    COUNT(f.ride_id) AS total_trips,
    SUM(f.total_amount) AS total_revenue,
    AVG(f.trip_distance) AS avg_trip_distance,
    AVG(f.fare_amount) AS avg_fare
FROM dim_datetime dt
JOIN fact_taxi_rides f FORCE INDEX (idx_fact_q1_covering)
    ON f.pickup_datetime_id = dt.datetime_id
GROUP BY dt.year, dt.month, dt.time_of_day
ORDER BY dt.month ASC, total_revenue DESC;

SELECT TIMEDIFF(NOW(6), @start_time) AS Q1_execution_time;

-- ==============================================================================
-- QUERY 2: Top Inter-Borough Routes
-- ==============================================================================
SET @start_time = NOW(6);

SELECT 
    pl.borough AS pickup_borough,
    dl.borough AS dropoff_borough,
    COUNT(f.ride_id) AS trip_count,
    SUM(f.total_amount) AS total_revenue,
    AVG(f.tip_amount) AS avg_tip,
    AVG(f.tolls_amount) AS avg_tolls
FROM fact_taxi_rides f FORCE INDEX (idx_fact_q2_covering)
STRAIGHT_JOIN dim_location pl ON f.pickup_location_id = pl.location_id
STRAIGHT_JOIN dim_location dl ON f.dropoff_location_id = dl.location_id
GROUP BY pl.borough, dl.borough
ORDER BY trip_count DESC
LIMIT 20;

SELECT TIMEDIFF(NOW(6), @start_time) AS Q2_execution_time;


-- ==============================================================================
-- QUERY 3: Rollup — Hierarchical Revenue Analysis
-- ==============================================================================
SET @start_time = NOW(6);

SELECT 
    p.payment_type_name,
    dt.year,
    dt.month,
    COUNT(f.ride_id) AS total_trips,
    SUM(f.total_amount) AS total_revenue,
    SUM(f.tip_amount) AS total_tips
FROM fact_taxi_rides f FORCE INDEX (idx_fact_q3_covering)
JOIN dim_datetime dt 
    ON f.pickup_datetime_id = dt.datetime_id
JOIN dim_payment_type p 
    ON f.payment_type_id = p.payment_type_id
GROUP BY p.payment_type_name, dt.year, dt.month WITH ROLLUP;

SELECT TIMEDIFF(NOW(6), @start_time) AS Q3_execution_time;

-- ==============================================================================
-- QUERY 4: Window Functions — Ranking Top Taxi Zones Per Month
-- ==============================================================================
SET @start_time = NOW(6);

WITH zone_monthly_revenue AS (
    SELECT 
        dt.month,
        loc.zone AS pickup_zone,
        loc.borough,
        COUNT(f.ride_id) AS trip_count,
        SUM(f.total_amount) AS revenue,
        DENSE_RANK() OVER (
            PARTITION BY dt.month
            ORDER BY SUM(f.total_amount) DESC
        ) AS revenue_rank
    FROM fact_taxi_rides f FORCE INDEX (idx_fact_q4_covering)
    STRAIGHT_JOIN dim_datetime dt 
        ON f.pickup_datetime_id = dt.datetime_id
    STRAIGHT_JOIN dim_location loc 
        ON f.pickup_location_id = loc.location_id
    GROUP BY dt.month, loc.zone, loc.borough
)
SELECT 
    month,
    revenue_rank,
    pickup_zone,
    borough,
    trip_count,
    revenue
FROM zone_monthly_revenue
WHERE revenue_rank <= 5
ORDER BY month ASC, revenue_rank ASC;

SELECT TIMEDIFF(NOW(6), @start_time) AS Q4_execution_time;

-- ==============================================================================
-- QUERY 5: Vendor Performance & Rate Code Behavior
-- ==============================================================================
SET @start_time = NOW(6);

SELECT 
    v.vendor_name,
    r.ratecode_name,
    COUNT(f.ride_id) AS total_trips,
    SUM(f.fare_amount) AS total_base_fare,
    SUM(f.airport_fee) AS total_airport_fees,
    SUM(f.cbd_congestion_fee) AS total_cbd_fees,
    AVG(f.passenger_count) AS avg_passengers
FROM fact_taxi_rides f FORCE INDEX (idx_fact_q5_covering)
STRAIGHT_JOIN dim_vendor v 
    ON f.vendor_id = v.vendor_id
STRAIGHT_JOIN dim_ratecode r 
    ON f.ratecode_id = r.ratecode_id
GROUP BY v.vendor_name, r.ratecode_name
ORDER BY v.vendor_name, total_trips DESC;

SELECT TIMEDIFF(NOW(6), @start_time) AS Q5_execution_time;