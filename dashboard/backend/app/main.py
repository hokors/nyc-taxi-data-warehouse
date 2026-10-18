import os
import time
from decimal import Decimal
from pathlib import Path
from contextlib import asynccontextmanager
from typing import Any, Dict, List

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
import mysql.connector
from mysql.connector import pooling

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=ENV_PATH, override=True)

DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_USER = os.environ.get("DB_USER", "root")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "")
DB_NAME = os.environ.get("DB_NAME", "nyc_taxi_warehouse")

db_pool = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global db_pool
    try:
        db_pool = pooling.MySQLConnectionPool(
            pool_name="olap_pool",
            pool_size=5,
            pool_reset_session=True,
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME,
            connection_timeout=15,
        )
        print(f"Connected to MySQL warehouse [{DB_NAME}] successfully.")
    except Exception as exc:
        print(f"Error creating MySQL pool: {exc}")
    yield

app = FastAPI(
    title="NYC Taxi OLAP API",
    description="OLAP warehouse API for NYC Taxi 2025 (41.5M records)",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_db():
    if not db_pool:
        raise HTTPException(status_code=503, detail="Database pool not initialized.")
    conn = db_pool.get_connection()
    # Configure session parameters matching teammate's specifications
    cursor = conn.cursor()
    cursor.execute("SET SESSION tmp_table_size = 536870912")
    cursor.execute("SET SESSION max_heap_table_size = 536870912")
    cursor.execute("SET SESSION sql_mode = (SELECT REPLACE(@@sql_mode, 'ONLY_FULL_GROUP_BY', ''))")
    cursor.close()
    return conn

def sanitize_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Convert MySQL Decimal values to standard Python floats for JSON serialization."""
    sanitized = []
    for row in rows:
        clean_row = {}
        for k, v in row.items():
            if isinstance(v, Decimal):
                clean_row[k] = float(v)
            else:
                clean_row[k] = v
        sanitized.append(clean_row)
    return sanitized


# ==============================================================================
# Health check
# ==============================================================================
@app.get("/api/health")
def health():
    return {"status": "ok"}

@app.get("/api/health-db")
def health_db():
    conn = None
    cursor = None
    try:
        conn = get_db()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT DATABASE() AS db_name")
        return {"status": "connected", "database": cursor.fetchone()["db_name"]}
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ==============================================================================
# QUERY 1: Monthly & Time-of-Day Revenue
# ==============================================================================
@app.get("/api/analytics/query-1")
def get_query_1(use_index: bool = True):
    conn = None
    cursor = None
    try:
        conn = get_db()
        cursor = conn.cursor(dictionary=True)
        index_clause = "FORCE INDEX (idx_fact_q1_covering)" if use_index else ""

        query = f"""
            SELECT 
                dt.year,
                dt.month,
                dt.time_of_day,
                COUNT(f.ride_id) AS total_trips,
                SUM(f.total_amount) AS total_revenue,
                AVG(f.trip_distance) AS avg_trip_distance,
                AVG(f.fare_amount) AS avg_fare
            FROM dim_datetime dt
            JOIN fact_taxi_rides f {index_clause}
                ON f.pickup_datetime_id = dt.datetime_id
            GROUP BY dt.year, dt.month, dt.time_of_day
            ORDER BY dt.month ASC, total_revenue DESC;
        """
        start = time.perf_counter()
        cursor.execute(query)
        rows = cursor.fetchall()
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)

        return {
            "query_name": "Monthly & Time-of-Day Revenue",
            "execution_time_ms": elapsed_ms,
            "used_covering_index": use_index,
            "row_count": len(rows),
            "data": sanitize_rows(rows),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ==============================================================================
# QUERY 2: Top Inter-Borough Routes
# ==============================================================================
@app.get("/api/analytics/query-2")
def get_query_2(use_index: bool = True, limit: int = 20):
    conn = None
    cursor = None
    try:
        conn = get_db()
        cursor = conn.cursor(dictionary=True)
        index_clause = "FORCE INDEX (idx_fact_q2_covering)" if use_index else ""

        query = f"""
            SELECT 
                pl.borough AS pickup_borough,
                dl.borough AS dropoff_borough,
                COUNT(f.ride_id) AS trip_count,
                SUM(f.total_amount) AS total_revenue,
                AVG(f.tip_amount) AS avg_tip,
                AVG(f.tolls_amount) AS avg_tolls
            FROM fact_taxi_rides f {index_clause}
            STRAIGHT_JOIN dim_location pl ON f.pickup_location_id = pl.location_id
            STRAIGHT_JOIN dim_location dl ON f.dropoff_location_id = dl.location_id
            GROUP BY pl.borough, dl.borough
            ORDER BY trip_count DESC
            LIMIT %s;
        """
        start = time.perf_counter()
        cursor.execute(query, (limit,))
        rows = cursor.fetchall()
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)

        return {
            "query_name": "Top Inter-Borough Routes",
            "execution_time_ms": elapsed_ms,
            "used_covering_index": use_index,
            "row_count": len(rows),
            "data": sanitize_rows(rows),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ==============================================================================
# QUERY 3: Rollup — Hierarchical Revenue Analysis
# ==============================================================================
@app.get("/api/analytics/query-3")
def get_query_3(use_index: bool = True):
    conn = None
    cursor = None
    try:
        conn = get_db()
        cursor = conn.cursor(dictionary=True)
        index_clause = "FORCE INDEX (idx_fact_q3_covering)" if use_index else ""

        query = f"""
            SELECT 
                COALESCE(p.payment_type_name, 'ALL PAYMENTS') AS payment_type_name,
                COALESCE(dt.year, 0) AS year,
                COALESCE(dt.month, 0) AS month,
                COUNT(f.ride_id) AS total_trips,
                SUM(f.total_amount) AS total_revenue,
                SUM(f.tip_amount) AS total_tips
            FROM fact_taxi_rides f {index_clause}
            JOIN dim_datetime dt 
                ON f.pickup_datetime_id = dt.datetime_id
            JOIN dim_payment_type p 
                ON f.payment_type_id = p.payment_type_id
            GROUP BY p.payment_type_name, dt.year, dt.month WITH ROLLUP;
        """
        start = time.perf_counter()
        cursor.execute(query)
        rows = cursor.fetchall()
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)

        return {
            "query_name": "Hierarchical Revenue Analysis (Rollup)",
            "execution_time_ms": elapsed_ms,
            "used_covering_index": use_index,
            "row_count": len(rows),
            "data": sanitize_rows(rows),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ==============================================================================
# QUERY 4: Window Functions — Ranking Top Taxi Zones Per Month
# ==============================================================================
@app.get("/api/analytics/query-4")
def get_query_4(use_index: bool = True, top_n: int = 5):
    conn = None
    cursor = None
    try:
        conn = get_db()
        cursor = conn.cursor(dictionary=True)
        index_clause = "FORCE INDEX (idx_fact_q4_covering)" if use_index else ""

        query = f"""
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
                FROM fact_taxi_rides f {index_clause}
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
            WHERE revenue_rank <= %s
            ORDER BY month ASC, revenue_rank ASC;
        """
        start = time.perf_counter()
        cursor.execute(query, (top_n,))
        rows = cursor.fetchall()
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)

        return {
            "query_name": "Top Taxi Zones Per Month (Window Functions)",
            "execution_time_ms": elapsed_ms,
            "used_covering_index": use_index,
            "row_count": len(rows),
            "data": sanitize_rows(rows),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ==============================================================================
# QUERY 5: Vendor Performance & Rate Code Behavior
# ==============================================================================
@app.get("/api/analytics/query-5")
def get_query_5(use_index: bool = True):
    conn = None
    cursor = None
    try:
        conn = get_db()
        cursor = conn.cursor(dictionary=True)
        index_clause = "FORCE INDEX (idx_fact_q5_covering)" if use_index else ""

        query = f"""
            SELECT 
                v.vendor_name,
                r.ratecode_name,
                COUNT(f.ride_id) AS total_trips,
                SUM(f.fare_amount) AS total_base_fare,
                SUM(f.airport_fee) AS total_airport_fees,
                SUM(f.cbd_congestion_fee) AS total_cbd_fees,
                AVG(f.passenger_count) AS avg_passengers
            FROM fact_taxi_rides f {index_clause}
            STRAIGHT_JOIN dim_vendor v 
                ON f.vendor_id = v.vendor_id
            STRAIGHT_JOIN dim_ratecode r 
                ON f.ratecode_id = r.ratecode_id
            GROUP BY v.vendor_name, r.ratecode_name
            ORDER BY v.vendor_name, total_trips DESC;
        """
        start = time.perf_counter()
        cursor.execute(query)
        rows = cursor.fetchall()
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)

        return {
            "query_name": "Vendor Performance & Rate Code Behavior",
            "execution_time_ms": elapsed_ms,
            "used_covering_index": use_index,
            "row_count": len(rows),
            "data": sanitize_rows(rows),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ==============================================================================
# BENCHMARK COMPARISON ENDPOINT (For the Query Performance Tab)
# ==============================================================================
@app.get("/api/analytics/benchmark/{query_number}")
def benchmark_query(query_number: int):
    """
    Runs both the baseline (without covering index) and optimized query,
    returning actual execution times and speedup factor.
    """
    endpoints = {
        1: get_query_1,
        2: get_query_2,
        3: get_query_3,
        4: get_query_4,
        5: get_query_5,
    }
    if query_number not in endpoints:
        raise HTTPException(status_code=400, detail="Query number must be between 1 and 5")

    target_func = endpoints[query_number]
    
    # 1. Run Optimized (with covering index)
    opt_result = target_func(use_index=True)
    
    # 2. Run Baseline (without index hint)
    base_result = target_func(use_index=False)

    opt_time = opt_result["execution_time_ms"]
    base_time = base_result["execution_time_ms"]
    speedup = round(base_time / opt_time, 2) if opt_time > 0 else 1.0

    return {
        "query_number": query_number,
        "query_name": opt_result["query_name"],
        "baseline_time_ms": base_time,
        "optimized_time_ms": opt_time,
        "speedup": f"{speedup}x",
        "sample_data": opt_result["data"][:10],
    }