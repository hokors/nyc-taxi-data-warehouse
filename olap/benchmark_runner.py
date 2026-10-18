import os
import re
import time
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()

# Database Configs
DB_USER = os.getenv("DB_USER", "root")
DB_PASS = os.getenv("DB_PASSWORD", "yourpasswordhere")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "3306")
DB_NAME = os.getenv("DB_NAME", "nyc_taxi_warehouse")

# Fallback URI connection string
DATABASE_URI = f"mysql+pymysql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

BASE_DIR = Path(__file__).resolve().parent.parent
QUERY_FILE = BASE_DIR / "olap" / "olap_queries.sql"
REPORT_DIR = BASE_DIR / "reports"


def clean_sql_statement(sql_str):
    """Strips SQL comments (-- and /* */) to expose raw statement."""
    sql_str = re.sub(r'/\*.*?\*/', '', sql_str, flags=re.DOTALL)
    lines = [line for line in sql_str.splitlines() if not line.strip().startswith('--')]
    return "\n".join(lines).strip()


def parse_queries(filepath):
    """Parses individual SELECT and CTE (WITH) queries from olap_queries.sql."""
    if not filepath.exists():
        raise FileNotFoundError(f"Benchmark file not found at: {filepath}")

    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    # Split by semicolon
    raw_statements = [stmt.strip() for stmt in content.split(";") if stmt.strip()]
    
    valid_queries = []
    for stmt in raw_statements:
        cleaned = clean_sql_statement(stmt)
        # Accepts SELECT queries as well as CTEs starting with WITH
        if cleaned.upper().startswith(("SELECT", "WITH")):
            valid_queries.append(cleaned)
            
    return valid_queries


def run_benchmarks():
    print("=" * 80)
    print("        STADVDB MCO1 — AUTOMATED OLAP BENCHMARK RUNNER")
    print("=" * 80)
    print(f"Connecting to database: {DB_NAME} on {DB_HOST}:{DB_PORT}")
    print(f"Loading queries from:   {QUERY_FILE}\n")

    try:
        queries = parse_queries(QUERY_FILE)
    except FileNotFoundError as e:
        print(f"[ERROR] {e}")
        return

    if not queries:
        print("[ERROR] No valid SELECT/WITH queries found in SQL file.")
        return

    print(f"[SUCCESS] Loaded {len(queries)} benchmark queries for execution.\n")
    engine = create_engine(DATABASE_URI)
    results = []

    with engine.connect() as conn:
        for idx, query_sql in enumerate(queries, 1):
            query_label = f"OLAP Query {idx}"
            print(f"[*] Executing {query_label}...")

            try:
                # Cold Run (Initial execution to populate buffer cache)
                start_cold = time.perf_counter()
                conn.execute(text(query_sql))
                cold_time = time.perf_counter() - start_cold

                # Warm Run (Measured execution time with warm cache)
                start_warm = time.perf_counter()
                res = conn.execute(text(query_sql))
                rows_fetched = len(res.fetchall())
                warm_time = time.perf_counter() - start_warm

                results.append({
                    "query": query_label,
                    "rows": rows_fetched,
                    "cold": round(cold_time, 3),
                    "warm": round(warm_time, 3)
                })

                print(f"    -> Done! Returned {rows_fetched:,} rows | Cold: {cold_time:.3f}s | Warm: {warm_time:.3f}s")

            except Exception as e:
                print(f"    [ERROR] Failed running {query_label}: {e}")

    # Output Markdown Summary Table
    markdown_output = [
        "## OLAP Benchmark Execution Results",
        f"**Database:** `{DB_NAME}`  ",
        f"**Queries Tested:** {len(results)}  \n",
        "| Query | Rows Returned | Cold Execution (s) | Warm Execution (s) |",
        "| :--- | :--- | :--- | :--- |"
    ]
    for r in results:
        markdown_output.append(f"| {r['query']} | {r['rows']:,} | {r['cold']}s | {r['warm']}s |")

    markdown_str = "\n".join(markdown_output)

    print("\n" + "=" * 80)
    print("                    BENCHMARK RESULTS (MARKDOWN TABLE)")
    print("=" * 80 + "\n")
    print(markdown_str)

    # Save to Markdown Report File
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report_file = REPORT_DIR / "benchmark_results.md"
    with open(report_file, "w", encoding="utf-8") as f:
        f.write(markdown_str + "\n")

    print(f"\n[SUCCESS] Report exported to: {report_file}")


if __name__ == "__main__":
    run_benchmarks()