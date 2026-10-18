"""Compare the baseline and optimized OLAP queries against the same warehouse.

Run from the project root:

    python tests/test_olap_performance.py --iterations 5

Connection settings are read from .env. The script verifies result equivalence,
records repeated execution times, captures EXPLAIN FORMAT=JSON output, and writes
CSV and Markdown reports under reports/.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import statistics
import sys
import time
from collections import Counter
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

import pymysql


PROJECT_ROOT = Path(__file__).resolve().parent.parent
BASELINE_FILE = PROJECT_ROOT / "olap" / "baseline_queries.sql"
OPTIMIZED_FILE = PROJECT_ROOT / "olap" / "optimized_queries.sql"
REPORT_DIR = PROJECT_ROOT / "reports"
QUERY_HEADER = re.compile(
    r"^\s*--\s*QUERY\s+(\d+)\s*:\s*(.*?)\s*$", re.IGNORECASE | re.MULTILINE
)
FORCED_INDEX = re.compile(r"FORCE\s+INDEX\s*\(\s*`?([\w$]+)`?\s*\)", re.IGNORECASE)


@dataclass(frozen=True)
class QueryCase:
    number: int
    title: str
    baseline_sql: str
    optimized_sql: str


def load_env_file(path: Path) -> None:
    """Load simple KEY=VALUE settings without requiring python-dotenv."""
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if value[:1] == value[-1:] and value.startswith(("'", '"')):
            value = value[1:-1]
        if key:
            os.environ.setdefault(key, value)


def parse_query_file(path: Path) -> dict[int, tuple[str, str]]:
    """Return {query_number: (title, analytical_select)} from a SQL file."""
    text = path.read_text(encoding="utf-8-sig")
    headers = list(QUERY_HEADER.finditer(text))
    if not headers:
        raise ValueError(f"No '-- QUERY N:' sections found in {path}")

    parsed: dict[int, tuple[str, str]] = {}
    for index, header in enumerate(headers):
        number = int(header.group(1))
        title = header.group(2).strip(" =")
        end = headers[index + 1].start() if index + 1 < len(headers) else len(text)
        block = text[header.end() : end]
        candidates = []
        for statement in block.split(";"):
            statement = _strip_line_comments(statement).strip()
            upper = statement.upper()
            if upper.startswith(("SELECT", "WITH")) and "TIMEDIFF(" not in upper:
                candidates.append(statement)

        if len(candidates) != 1:
            raise ValueError(
                f"Query {number} in {path} must contain exactly one analytical "
                f"SELECT/WITH statement; found {len(candidates)}"
            )
        if number in parsed:
            raise ValueError(f"Duplicate query number {number} in {path}")
        parsed[number] = (title, candidates[0])
    return parsed


def _strip_line_comments(sql: str) -> str:
    return "\n".join(
        line for line in sql.splitlines() if not line.lstrip().startswith("--")
    )


def load_cases() -> list[QueryCase]:
    baseline = parse_query_file(BASELINE_FILE)
    optimized = parse_query_file(OPTIMIZED_FILE)
    if baseline.keys() != optimized.keys():
        raise ValueError(
            "Baseline and optimized query numbers differ: "
            f"baseline={sorted(baseline)}, optimized={sorted(optimized)}"
        )
    return [
        QueryCase(number, baseline[number][0], baseline[number][1], optimized[number][1])
        for number in sorted(baseline)
    ]


def connect():
    load_env_file(PROJECT_ROOT / ".env")
    return pymysql.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "3306")),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", ""),
        database=os.getenv("WAREHOUSE_DB", os.getenv("DB_NAME", "nyc_taxi_warehouse")),
        charset="utf8mb4",
        autocommit=True,
        connect_timeout=int(os.getenv("DB_CONNECT_TIMEOUT", "10")),
        read_timeout=int(os.getenv("DB_READ_TIMEOUT", "1800")),
        write_timeout=int(os.getenv("DB_WRITE_TIMEOUT", "1800")),
    )


def available_fact_indexes(connection) -> set[str]:
    with connection.cursor() as cursor:
        cursor.execute("SHOW INDEX FROM fact_taxi_rides")
        key_name_position = [item[0] for item in cursor.description].index("Key_name")
        return {row[key_name_position] for row in cursor.fetchall()}


def validate_forced_indexes(connection, cases: list[QueryCase]) -> None:
    required = {
        name for case in cases for name in FORCED_INDEX.findall(case.optimized_sql)
    }
    missing = sorted(required - available_fact_indexes(connection))
    if missing:
        raise RuntimeError(
            "Optimized queries reference indexes that do not exist: "
            + ", ".join(missing)
            + ". Create or rename these indexes before benchmarking."
        )


def execute_query(connection, sql: str) -> tuple[list[tuple[Any, ...]], float]:
    started = time.perf_counter()
    with connection.cursor() as cursor:
        cursor.execute(sql)
        rows = list(cursor.fetchall())
    return rows, time.perf_counter() - started


def normalized_rows(rows: list[tuple[Any, ...]]) -> Counter:
    """Compare result sets independent of row order."""
    def normalize(value: Any) -> Any:
        if isinstance(value, Decimal):
            return ("decimal", str(value.normalize()))
        if isinstance(value, float):
            return ("float", round(value, 10))
        if isinstance(value, (bytes, bytearray)):
            return ("bytes", bytes(value).hex())
        return value

    return Counter(tuple(normalize(value) for value in row) for row in rows)


def explain(connection, sql: str) -> Any:
    with connection.cursor() as cursor:
        cursor.execute("EXPLAIN FORMAT=JSON " + sql)
        raw = cursor.fetchone()[0]
    return json.loads(raw) if isinstance(raw, str) else raw


def write_reports(results: list[dict[str, Any]], explains: dict[str, Any]) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = REPORT_DIR / "olap_performance_results.csv"
    md_path = REPORT_DIR / "olap_performance_summary.md"
    explain_path = REPORT_DIR / "olap_explain_plans.json"

    with csv_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(results[0]))
        writer.writeheader()
        writer.writerows(results)

    grouped: dict[int, dict[str, list[float]]] = {}
    titles: dict[int, str] = {}
    row_counts: dict[int, int] = {}
    for row in results:
        number = int(row["query"])
        titles[number] = str(row["title"])
        row_counts[number] = int(row["rows"])
        grouped.setdefault(number, {"baseline": [], "optimized": []})[
            str(row["version"])
        ].append(float(row["seconds"]))

    lines = [
        "# OLAP Baseline vs Optimized Performance",
        "",
        "| Query | Rows | Baseline median (s) | Optimized median (s) | Improvement |",
        "|---|---:|---:|---:|---:|",
    ]
    for number in sorted(grouped):
        baseline_median = statistics.median(grouped[number]["baseline"])
        optimized_median = statistics.median(grouped[number]["optimized"])
        improvement = (
            ((baseline_median - optimized_median) / baseline_median * 100)
            if baseline_median
            else 0.0
        )
        lines.append(
            f"| Q{number}: {titles[number]} | {row_counts[number]} | "
            f"{baseline_median:.6f} | {optimized_median:.6f} | {improvement:.2f}% |"
        )

    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    explain_path.write_text(json.dumps(explains, indent=2), encoding="utf-8")
    print(f"CSV results:     {csv_path}")
    print(f"Summary report:  {md_path}")
    print(f"EXPLAIN plans:   {explain_path}")


def run(iterations: int, warmups: int) -> None:
    if iterations < 1 or warmups < 0:
        raise ValueError("iterations must be at least 1 and warmups cannot be negative")

    cases = load_cases()
    results: list[dict[str, Any]] = []
    explains: dict[str, Any] = {}

    with connect() as connection:
        validate_forced_indexes(connection, cases)

        for case in cases:
            print(f"Q{case.number}: {case.title}")
            baseline_rows, _ = execute_query(connection, case.baseline_sql)
            optimized_rows, _ = execute_query(connection, case.optimized_sql)
            if normalized_rows(baseline_rows) != normalized_rows(optimized_rows):
                raise AssertionError(
                    f"Q{case.number} failed: baseline and optimized results differ"
                )
            print(f"  correctness: PASS ({len(baseline_rows):,} rows)")

            explains[f"Q{case.number}_baseline"] = explain(connection, case.baseline_sql)
            explains[f"Q{case.number}_optimized"] = explain(connection, case.optimized_sql)

            for _ in range(warmups):
                execute_query(connection, case.baseline_sql)
                execute_query(connection, case.optimized_sql)

            for iteration in range(1, iterations + 1):
                order = (
                    (("baseline", case.baseline_sql), ("optimized", case.optimized_sql))
                    if iteration % 2
                    else (("optimized", case.optimized_sql), ("baseline", case.baseline_sql))
                )
                measured: dict[str, float] = {}
                for version, sql in order:
                    rows, seconds = execute_query(connection, sql)
                    measured[version] = seconds
                    results.append(
                        {
                            "query": case.number,
                            "title": case.title,
                            "iteration": iteration,
                            "version": version,
                            "rows": len(rows),
                            "seconds": f"{seconds:.6f}",
                        }
                    )
                print(
                    f"  run {iteration}: baseline={measured['baseline']:.3f}s, "
                    f"optimized={measured['optimized']:.3f}s"
                )

    write_reports(results, explains)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Test correctness and performance of paired OLAP queries."
    )
    parser.add_argument("--iterations", type=int, default=3)
    parser.add_argument("--warmups", type=int, default=1)
    return parser.parse_args()


if __name__ == "__main__":
    try:
        arguments = parse_args()
        run(arguments.iterations, arguments.warmups)
    except (AssertionError, OSError, RuntimeError, ValueError, pymysql.MySQLError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        sys.exit(1)
