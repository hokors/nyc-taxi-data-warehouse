-- ==============================================================================
-- STADVDB MCO1: Physical Database Optimization & Indexing
-- Target Database: nyc_taxi_warehouse
-- Target Table: fact_taxi_rides (45.3M rows)
-- ==============================================================================

USE nyc_taxi_warehouse;

-- 1. Pickup Datetime Index (Optimizes Query 1, Query 3, Query 4)
-- Accelerates joins with dim_datetime and temporal aggregation (month/year/time_of_day)
DROP PROCEDURE IF EXISTS create_idx_pickup_dt;
DELIMITER //
CREATE PROCEDURE create_idx_pickup_dt()
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.statistics 
        WHERE table_schema = 'nyc_taxi_warehouse' 
          AND table_name = 'fact_taxi_rides' 
          AND index_name = 'idx_fact_pickup_dt'
    ) THEN
        CREATE INDEX idx_fact_pickup_dt ON fact_taxi_rides(pickup_datetime_id);
    END IF;
END //
DELIMITER ;
CALL create_idx_pickup_dt();
DROP PROCEDURE IF EXISTS create_idx_pickup_dt;


-- 2. Pickup Location Index (Optimizes Query 2, Query 4)
-- Accelerates borough and zone joins from dim_location
DROP PROCEDURE IF EXISTS create_idx_pickup_loc;
DELIMITER //
CREATE PROCEDURE create_idx_pickup_loc()
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.statistics 
        WHERE table_schema = 'nyc_taxi_warehouse' 
          AND table_name = 'fact_taxi_rides' 
          AND index_name = 'idx_fact_pickup_loc'
    ) THEN
        CREATE INDEX idx_fact_pickup_loc ON fact_taxi_rides(pickup_location_id);
    END IF;
END //
DELIMITER ;
CALL create_idx_pickup_loc();
DROP PROCEDURE IF EXISTS create_idx_pickup_loc;


-- 3. Dropoff Location Index (Optimizes Query 2)
-- Accelerates matrix analysis for pickup-to-dropoff corridors
DROP PROCEDURE IF EXISTS create_idx_dropoff_loc;
DELIMITER //
CREATE PROCEDURE create_idx_dropoff_loc()
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.statistics 
        WHERE table_schema = 'nyc_taxi_warehouse' 
          AND table_name = 'fact_taxi_rides' 
          AND index_name = 'idx_fact_dropoff_loc'
    ) THEN
        CREATE INDEX idx_fact_dropoff_loc ON fact_taxi_rides(dropoff_location_id);
    END IF;
END //
DELIMITER ;
CALL create_idx_dropoff_loc();
DROP PROCEDURE IF EXISTS create_idx_dropoff_loc;


-- 4. Payment Type & Vendor Composite Index (Optimizes Query 3, Query 5)
-- Multi-column composite index covering revenue rollups and vendor distributions
DROP PROCEDURE IF EXISTS create_idx_payment_vendor;
DELIMITER //
CREATE PROCEDURE create_idx_payment_vendor()
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.statistics 
        WHERE table_schema = 'nyc_taxi_warehouse' 
          AND table_name = 'fact_taxi_rides' 
          AND index_name = 'idx_fact_payment_vendor'
    ) THEN
        CREATE INDEX idx_fact_payment_vendor ON fact_taxi_rides(payment_type_id, vendor_id);
    END IF;
END //
DELIMITER ;
CALL create_idx_payment_vendor();
DROP PROCEDURE IF EXISTS create_idx_payment_vendor;


-- 5. Ratecode Index (Optimizes Query 5)
-- Accelerates fare policy breakdown (Standard, JFK, Newark, Negotiated)
DROP PROCEDURE IF EXISTS create_idx_ratecode;
DELIMITER //
CREATE PROCEDURE create_idx_ratecode()
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.statistics 
        WHERE table_schema = 'nyc_taxi_warehouse' 
          AND table_name = 'fact_taxi_rides' 
          AND index_name = 'idx_fact_ratecode'
    ) THEN
        CREATE INDEX idx_fact_ratecode ON fact_taxi_rides(ratecode_id);
    END IF;
END //
DELIMITER ;
CALL create_idx_ratecode();
DROP PROCEDURE IF EXISTS create_idx_ratecode;

SHOW INDEX FROM nyc_taxi_warehouse.fact_taxi_rides;