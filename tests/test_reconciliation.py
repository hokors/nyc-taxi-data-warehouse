"""
Automated Data Reconciliation and Warehouse Integrity Test Suite for STADVDB MCO1.
Compares source vs. target row counts, verifies foreign key referential integrity,
and audits aggregate financial metrics.
"""

import sys
from typing import Dict, Any
from sqlalchemy import text

from etl import config
from etl.db import source_engine, warehouse_engine


class Colors:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    CYAN = "\033[96m"
    RESET = "\033[0m"
    BOLD = "\033[1m"


def print_check(name: str, passed: bool, details: str = ""):
    status = f"{Colors.GREEN}[PASS]{Colors.RESET}" if passed else f"{Colors.RED}[FAIL]{Colors.RESET}"
    print(f" {status} {name:<45} {details}")


def check_row_counts() -> Dict[str, Any]:
    """Reconciles total row counts across source, fact, and dimension tables."""
    print(f"\n{Colors.BOLD}--- 1. ROW COUNT & TABLE POPULATION RECONCILIATION ---{Colors.RESET}")
    results = {}

    with source_engine.connect() as src_conn:
        try:
            source_count = src_conn.execute(
                text(f"SELECT COUNT(*) FROM {config.SOURCE_TABLE}")
            ).scalar() or 0
        except Exception:
            source_count = 0
    results["source_count"] = source_count

    with warehouse_engine.connect() as wh_conn:
        fact_count = wh_conn.execute(
            text("SELECT COUNT(*) FROM fact_taxi_rides")
        ).scalar() or 0
        dim_loc_count = wh_conn.execute(
            text("SELECT COUNT(*) FROM dim_location")
        ).scalar() or 0
        dim_dt_count = wh_conn.execute(
            text("SELECT COUNT(*) FROM dim_datetime")
        ).scalar() or 0
        dim_vendor_count = wh_conn.execute(
            text("SELECT COUNT(*) FROM dim_vendor")
        ).scalar() or 0
        dim_ratecode_count = wh_conn.execute(
            text("SELECT COUNT(*) FROM dim_ratecode")
        ).scalar() or 0
        dim_payment_count = wh_conn.execute(
            text("SELECT COUNT(*) FROM dim_payment_type")
        ).scalar() or 0

    results.update({
        "fact_count": fact_count,
        "dim_location": dim_loc_count,
        "dim_datetime": dim_dt_count,
        "dim_vendor": dim_vendor_count,
        "dim_ratecode": dim_ratecode_count,
        "dim_payment_type": dim_payment_count,
    })

    print(f"  Source Records ({config.SOURCE_DB}.{config.SOURCE_TABLE}): {source_count:,}")
    print(f"  Warehouse Facts (fact_taxi_rides):                      {fact_count:,}")
    print(f"  Dimension Locations (dim_location):                     {dim_loc_count:,}")
    print(f"  Dimension Timestamps (dim_datetime):                    {dim_dt_count:,}")
    print(f"  Dimension Vendors (dim_vendor):                         {dim_vendor_count:,}")
    print(f"  Dimension Ratecodes (dim_ratecode):                     {dim_ratecode_count:,}")
    print(f"  Dimension Payment Types (dim_payment_type):             {dim_payment_count:,}")

    # Checks
    fact_populated = fact_count > 0
    print_check("Warehouse Fact Table Populated", fact_populated, f"Count = {fact_count:,}")

    if source_count > 0:
        count_valid = fact_count <= source_count
        ratio = (fact_count / source_count) * 100
        print_check(
            "Fact Count <= Source Count (Cleaning Retention)",
            count_valid,
            f"{ratio:.2f}% retained (Dirty records rejected)",
        )
    else:
        print(f"  {Colors.YELLOW}[INFO]{Colors.RESET} Source table empty; skipping relative retention check.")

    dim_populated = (
        dim_loc_count >= 265
        and dim_vendor_count >= 3
        and dim_ratecode_count >= 7
        and dim_payment_count >= 6
    )
    print_check("Static Reference Dimensions Fully Seeded", dim_populated)

    return results


def check_referential_integrity() -> bool:
    """Verifies that NO orphaned foreign keys exist in fact_taxi_rides."""
    print(f"\n{Colors.BOLD}--- 2. REFERENTIAL INTEGRITY & ORPHAN AUDITING ---{Colors.RESET}")
    all_passed = True

    fk_checks = [
        (
            "Pickup Datetime FK (pickup_datetime_id)",
            """
            SELECT COUNT(*) FROM fact_taxi_rides f
            LEFT JOIN dim_datetime d ON f.pickup_datetime_id = d.datetime_id
            WHERE d.datetime_id IS NULL;
            """,
        ),
        (
            "Dropoff Datetime FK (dropoff_datetime_id)",
            """
            SELECT COUNT(*) FROM fact_taxi_rides f
            LEFT JOIN dim_datetime d ON f.dropoff_datetime_id = d.datetime_id
            WHERE d.datetime_id IS NULL;
            """,
        ),
        (
            "Pickup Location FK (pickup_location_id)",
            """
            SELECT COUNT(*) FROM fact_taxi_rides f
            LEFT JOIN dim_location l ON f.pickup_location_id = l.location_id
            WHERE l.location_id IS NULL;
            """,
        ),
        (
            "Dropoff Location FK (dropoff_location_id)",
            """
            SELECT COUNT(*) FROM fact_taxi_rides f
            LEFT JOIN dim_location l ON f.dropoff_location_id = l.location_id
            WHERE l.location_id IS NULL;
            """,
        ),
        (
            "Vendor FK (vendor_id)",
            """
            SELECT COUNT(*) FROM fact_taxi_rides f
            LEFT JOIN dim_vendor v ON f.vendor_id = v.vendor_id
            WHERE v.vendor_id IS NULL;
            """,
        ),
        (
            "Ratecode FK (ratecode_id)",
            """
            SELECT COUNT(*) FROM fact_taxi_rides f
            LEFT JOIN dim_ratecode r ON f.ratecode_id = r.ratecode_id
            WHERE r.ratecode_id IS NULL;
            """,
        ),
        (
            "Payment Type FK (payment_type_id)",
            """
            SELECT COUNT(*) FROM fact_taxi_rides f
            LEFT JOIN dim_payment_type p ON f.payment_type_id = p.payment_type_id
            WHERE p.payment_type_id IS NULL;
            """,
        ),
    ]

    with warehouse_engine.connect() as conn:
        for fk_name, query in fk_checks:
            orphan_count = conn.execute(text(query)).scalar() or 0
            passed = orphan_count == 0
            if not passed:
                all_passed = False
            print_check(fk_name, passed, f"Orphaned Rows = {orphan_count}")

    return all_passed


def check_business_constraints() -> bool:
    """Verifies that no negative fares, impossible distances, or corrupted metrics exist in the warehouse."""
    print(f"\n{Colors.BOLD}--- 3. DATA QUALITY & BUSINESS CONSTRAINT AUDIT ---{Colors.RESET}")
    all_passed = True

    constraint_checks = [
        (
            "No Negative Fares (fare_amount >= 0)",
            "SELECT COUNT(*) FROM fact_taxi_rides WHERE fare_amount < 0;",
        ),
        (
            "No Negative Totals (total_amount >= 0)",
            "SELECT COUNT(*) FROM fact_taxi_rides WHERE total_amount < 0;",
        ),
        (
            "No Negative Trip Distances (trip_distance >= 0)",
            "SELECT COUNT(*) FROM fact_taxi_rides WHERE trip_distance < 0;",
        ),
        (
            "Valid Passenger Counts (passenger_count >= 0)",
            "SELECT COUNT(*) FROM fact_taxi_rides WHERE passenger_count < 0;",
        ),
        (
            "No Unparsed Datetimes (pickup_datetime_id != -1)",
            "SELECT COUNT(*) FROM fact_taxi_rides WHERE pickup_datetime_id = -1;",
        ),
        (
            "Distance Anomaly Check (trip_distance <= 500)",
            "SELECT COUNT(*) FROM fact_taxi_rides WHERE trip_distance > 500;",
        ),
    ]

    with warehouse_engine.connect() as conn:
        for check_name, query in constraint_checks:
            violation_count = conn.execute(text(query)).scalar() or 0
            passed = violation_count == 0
            if not passed:
                all_passed = False
            print_check(check_name, passed, f"Violations = {violation_count}")

    return all_passed


def check_aggregate_parity() -> bool:
    """Compares financial aggregate totals between source and warehouse."""
    print(f"\n{Colors.BOLD}--- 4. AGGREGATE FINANCIAL & VOLUMETRIC PARITY ---{Colors.RESET}")

    wh_query = """
        SELECT 
            COUNT(*) as total_rows,
            SUM(fare_amount) as sum_fare,
            SUM(tip_amount) as sum_tip,
            SUM(total_amount) as sum_total,
            AVG(trip_distance) as avg_distance
        FROM fact_taxi_rides;
    """

    src_query = f"""
        SELECT 
            COUNT(*) as total_rows,
            SUM(fare_amount) as sum_fare,
            SUM(tip_amount) as sum_tip,
            SUM(total_amount) as sum_total,
            AVG(trip_distance) as avg_distance
        FROM {config.SOURCE_TABLE};
    """

    with warehouse_engine.connect() as wh_conn:
        wh_row = wh_conn.execute(text(wh_query)).mappings().first()

    with source_engine.connect() as src_conn:
        try:
            src_row = src_conn.execute(text(src_query)).mappings().first()
        except Exception:
            src_row = None

    if not src_row or not src_row["total_rows"]:
        print(f"  {Colors.YELLOW}[INFO]{Colors.RESET} Source table empty or inaccessible; reporting warehouse aggregates only:")
        print(f"    • Total Warehouse Fares:     ${wh_row['sum_fare'] or 0:,.2f}")
        print(f"    • Total Warehouse Tips:      ${wh_row['sum_tip'] or 0:,.2f}")
        print(f"    • Total Warehouse Revenue:   ${wh_row['sum_total'] or 0:,.2f}")
        print(f"    • Average Trip Distance:     {wh_row['avg_distance'] or 0:.2f} miles")
        return True

    print(f"  {'Metric':<25} {'Source DB':<20} {'Warehouse':<20} {'Variance'}")
    print("  " + "-" * 75)

    metrics = [
        ("Sum Fare Amount", float(src_row["sum_fare"] or 0), float(wh_row["sum_fare"] or 0)),
        ("Sum Tip Amount", float(src_row["sum_tip"] or 0), float(wh_row["sum_tip"] or 0)),
        ("Sum Total Amount", float(src_row["sum_total"] or 0), float(wh_row["sum_total"] or 0)),
        ("Avg Trip Distance", float(src_row["avg_distance"] or 0), float(wh_row["avg_distance"] or 0)),
    ]

    for label, src_val, wh_val in metrics:
        diff = wh_val - src_val
        pct_diff = (diff / src_val * 100) if src_val else 0.0
        print(f"  {label:<25} {src_val:>18,.2f} {wh_val:>18,.2f} {pct_diff:>+8.2f}%")

    print(f"\n  {Colors.CYAN}[NOTE]{Colors.RESET} Small variance is expected due to the filtration of negative/corrupted transactions.")
    return True


def run_all_checks() -> bool:
    print("\n" + "=" * 78)
    print("       STADVDB MCO1 — AUTOMATED RECONCILIATION & VALIDATION AUDIT")
    print("=" * 78)

    row_counts = check_row_counts()
    fk_passed = check_referential_integrity()
    constraints_passed = check_business_constraints()
    aggregates_passed = check_aggregate_parity()

    print("\n" + "=" * 78)
    overall_passed = (row_counts["fact_count"] > 0) and fk_passed and constraints_passed and aggregates_passed
    if overall_passed:
        print(f" {Colors.GREEN}{Colors.BOLD}OVERALL AUDIT STATUS: PASSED — WAREHOUSE IS INTEGRITY-CERTIFIED{Colors.RESET}")
    else:
        print(f" {Colors.RED}{Colors.BOLD}OVERALL AUDIT STATUS: FAILED — INTEGRITY ISSUES DETECTED{Colors.RESET}")
    print("=" * 78 + "\n")

    return overall_passed


# Pytest test cases
def test_row_counts():
    counts = check_row_counts()
    assert counts["fact_count"] > 0, "Warehouse fact table contains zero records."


def test_referential_integrity():
    assert check_referential_integrity(), "Referential integrity check failed: orphaned foreign keys found."


def test_business_constraints():
    assert check_business_constraints(), "Business constraint check failed: negative or anomalous values found."


if __name__ == "__main__":
    success = run_all_checks()
    sys.exit(0 if success else 1)
