-- =============================================================================
-- STADVDB MCO1: Dimension Seeder Script
-- Purpose: Pre-populate reference dimensions with official TLC metadata
--          and ensure default fallback records (-1) exist for foreign key safety.
-- =============================================================================

USE nyc_taxi_warehouse;

-- 1. Seed dim_payment_type (Official TLC Payment Code Mapping)
INSERT INTO dim_payment_type (payment_type_id, payment_type_name) VALUES
    (1, 'Credit card'),
    (2, 'Cash'),
    (3, 'No charge'),
    (4, 'Dispute'),
    (5, 'Unknown'),
    (6, 'Voided trip'),
    (-1, 'Unknown / Unspecified')
ON DUPLICATE KEY UPDATE payment_type_name = VALUES(payment_type_name);

-- 2. Seed dim_vendor (Official TLC Vendor Mapping)
INSERT INTO dim_vendor (vendor_id, vendor_name) VALUES
    (1, 'Creative Mobile Technologies, LLC'),
    (2, 'VeriFone Inc.'),
    (-1, 'Unknown / Other')
ON DUPLICATE KEY UPDATE vendor_name = VALUES(vendor_name);

-- 3. Seed dim_ratecode (Official TLC Rate Code Mapping)
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

-- 4. Seed dim_location fallback unknown records
INSERT INTO dim_location (location_id, borough, zone, service_zone) VALUES
    (-1, 'Unknown', 'Unknown / Unspecified', 'Unknown'),
    (0, 'Unknown', 'Unknown / Default', 'Unknown')
ON DUPLICATE KEY UPDATE borough = VALUES(borough), zone = VALUES(zone), service_zone = VALUES(service_zone);

-- 5. Seed dim_location from source database (if taxi_zone_lookup was staged)
INSERT IGNORE INTO dim_location (location_id, borough, zone, service_zone)
SELECT LocationID, Borough, Zone, service_zone 
FROM nyc_taxi_source.taxi_zone_lookup
WHERE LocationID IS NOT NULL;
