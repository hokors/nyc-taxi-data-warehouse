"use client";

import { useState } from "react";
import { runBenchmark } from "@/src/lib/api";
import { Card, Badge, Button } from "@/src/app/components/ui/Controls";

const scenarios = [
  {
    id: 1,
    name: "Query 1: Monthly & Time-of-Day Revenue",
    strategy: "Covering index (idx_fact_q1_covering)",
    sql: `-- Query 1: Monthly & Time-of-Day Revenue
SELECT dt.year, dt.month, dt.time_of_day,
       COUNT(f.ride_id) AS total_trips,
       SUM(f.total_amount) AS total_revenue,
       AVG(f.trip_distance) AS avg_trip_distance,
       AVG(f.fare_amount) AS avg_fare
FROM dim_datetime dt
JOIN fact_taxi_rides f FORCE INDEX (idx_fact_q1_covering)
  ON f.pickup_datetime_id = dt.datetime_id
GROUP BY dt.year, dt.month, dt.time_of_day
ORDER BY dt.month ASC, total_revenue DESC;`,
  },
  {
    id: 2,
    name: "Query 2: Top Inter-Borough Routes",
    strategy: "Covering index & STRAIGHT_JOIN (idx_fact_q2_covering)",
    sql: `-- Query 2: Top Inter-Borough Routes
SELECT pl.borough AS pickup_borough, dl.borough AS dropoff_borough,
       COUNT(f.ride_id) AS trip_count,
       SUM(f.total_amount) AS total_revenue
FROM fact_taxi_rides f FORCE INDEX (idx_fact_q2_covering)
STRAIGHT_JOIN dim_location pl ON f.pickup_location_id = pl.location_id
STRAIGHT_JOIN dim_location dl ON f.dropoff_location_id = dl.location_id
GROUP BY pl.borough, dl.borough
ORDER BY trip_count DESC LIMIT 20;`,
  },
  {
    id: 3,
    name: "Query 3: Hierarchical Revenue (WITH ROLLUP)",
    strategy: "Multi-dimension Rollup Covering Index (idx_fact_q3_covering)",
    sql: `-- Query 3: Rollup Hierarchical Revenue Analysis
SELECT p.payment_type_name, dt.year, dt.month,
       COUNT(f.ride_id) AS total_trips,
       SUM(f.total_amount) AS total_revenue
FROM fact_taxi_rides f FORCE INDEX (idx_fact_q3_covering)
JOIN dim_datetime dt ON f.pickup_datetime_id = dt.datetime_id
JOIN dim_payment_type p ON f.payment_type_id = p.payment_type_id
GROUP BY p.payment_type_name, dt.year, dt.month WITH ROLLUP;`,
  },
  {
    id: 4,
    name: "Query 4: Window Functions (Monthly Zone Rank)",
    strategy: "DENSE_RANK() with Covering Index (idx_fact_q4_covering)",
    sql: `-- Query 4: Ranking Top Taxi Zones Per Month
WITH zone_monthly_revenue AS (
  SELECT dt.month, loc.zone AS pickup_zone, loc.borough,
         COUNT(f.ride_id) AS trip_count, SUM(f.total_amount) AS revenue,
         DENSE_RANK() OVER (PARTITION BY dt.month ORDER BY SUM(f.total_amount) DESC) AS revenue_rank
  FROM fact_taxi_rides f FORCE INDEX (idx_fact_q4_covering)
  STRAIGHT_JOIN dim_datetime dt ON f.pickup_datetime_id = dt.datetime_id
  STRAIGHT_JOIN dim_location loc ON f.pickup_location_id = loc.location_id
  GROUP BY dt.month, loc.zone, loc.borough
)
SELECT * FROM zone_monthly_revenue WHERE revenue_rank <= 5;`,
  },
  {
    id: 5,
    name: "Query 5: Vendor & Rate Code Analysis",
    strategy: "Covering Index for Multi-Measure Aggregation (idx_fact_q5_covering)",
    sql: `-- Query 5: Vendor Performance & Rate Code Behavior
SELECT v.vendor_name, r.ratecode_name,
       COUNT(f.ride_id) AS total_trips,
       SUM(f.fare_amount) AS total_base_fare,
       AVG(f.passenger_count) AS avg_passengers
FROM fact_taxi_rides f FORCE INDEX (idx_fact_q5_covering)
STRAIGHT_JOIN dim_vendor v ON f.vendor_id = v.vendor_id
STRAIGHT_JOIN dim_ratecode r ON f.ratecode_id = r.ratecode_id
GROUP BY v.vendor_name, r.ratecode_name;`,
  },
];

export default function QueryPerformance() {
  const [selected, setSelected] = useState(0);
  const [loading, setLoading] = useState(false);
  const [benchmarkResults, setBenchmarkResults] = useState<Record<number, any>>({});

  const activeScenario = scenarios[selected];
  const activeBenchmark = benchmarkResults[activeScenario.id];

  async function handleRunBenchmark(queryId: number) {
    try {
      setLoading(true);
      const res = await runBenchmark(queryId);
      setBenchmarkResults((prev) => ({ ...prev, [queryId]: res }));
    } catch (err: any) {
      alert(`Benchmark failed: ${err.message}`);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="page-content">
      <div className="hero-row">
        <div>
          <div className="eyebrow">QUERY BENCHMARKS</div>
          <h1>Query Performance</h1>
          <p>Execute actual baseline vs covering-index queries against 41.5M records in MySQL.</p>
        </div>
        <Badge tone={activeBenchmark ? "green" : "amber"}>
          {activeBenchmark ? "Benchmark recorded" : "Select & execute test"}
        </Badge>
      </div>

      <div className="perf-summary">
        <Card>
          <span>Baseline runtime (no index hint)</span>
          <strong>{activeBenchmark ? `${activeBenchmark.baseline_time_ms} ms` : "—"}</strong>
          <small>{activeBenchmark ? "Measured MySQL time" : "Run test to populate"}</small>
        </Card>
        <Card>
          <span>Optimized runtime (covering index)</span>
          <strong>{activeBenchmark ? `${activeBenchmark.optimized_time_ms} ms` : "—"}</strong>
          <small>{activeBenchmark ? "Measured MySQL time" : "Run test to populate"}</small>
        </Card>
        <Card className={activeBenchmark ? "" : "pending-card"}>
          <span>Performance improvement</span>
          <strong>{activeBenchmark ? activeBenchmark.speedup : "Pending"}</strong>
          <small>{activeBenchmark ? "Relative speedup factor" : "Awaiting execution"}</small>
        </Card>
      </div>

      <Card className="table-card performance-table">
        <div className="card-header" style={{ padding: "18px 20px" }}>
          <div>
            <h2>Benchmark scenarios</h2>
            <p>Click a scenario to inspect its query, or execute the test live.</p>
          </div>
          <Button
            variant="primary"
            onClick={() => handleRunBenchmark(activeScenario.id)}
            disabled={loading}
          >
            {loading ? "Running MySQL Benchmark..." : `Run Benchmark (Q${activeScenario.id})`}
          </Button>
        </div>
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Query scenario</th>
                <th>Optimization strategy</th>
                <th>Baseline</th>
                <th>Optimized</th>
                <th>Speedup</th>
              </tr>
            </thead>
            <tbody>
              {scenarios.map((q, i) => {
                const bm = benchmarkResults[q.id];
                return (
                  <tr
                    key={q.name}
                    className={selected === i ? "selected-row" : ""}
                    onClick={() => setSelected(i)}
                  >
                    <td><strong>{q.name}</strong></td>
                    <td>{q.strategy}</td>
                    <td>{bm ? `${bm.baseline_time_ms} ms` : "—"}</td>
                    <td>{bm ? `${bm.optimized_time_ms} ms` : "—"}</td>
                    <td>
                      {bm ? (
                        <Badge tone="green">{bm.speedup}</Badge>
                      ) : (
                        <Badge tone="neutral">Ready to run</Badge>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Card>

      <div className="comparison-grid">
        <Card className="sql-card">
          <div className="card-header">
            <div>
              <h2>SQL Query Plan</h2>
              <p>{activeScenario.name}</p>
            </div>
            <Badge tone="neutral">Live SQL</Badge>
          </div>
          <pre>{activeScenario.sql}</pre>
        </Card>

        <Card className="explain-card">
          <div className="card-header">
            <div>
              <h2>Sample Aggregated Output</h2>
              <p>{activeBenchmark ? `Showing rows from MySQL` : "Execute benchmark to view rows"}</p>
            </div>
          </div>
          {activeBenchmark?.sample_data ? (
            <div className="table-scroll" style={{ maxHeight: 280 }}>
              <table>
                <thead>
                  <tr>
                    {Object.keys(activeBenchmark.sample_data[0] || {}).map((k) => (
                      <th key={k}>{k}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {activeBenchmark.sample_data.map((row: any, idx: number) => (
                    <tr key={idx}>
                      {Object.values(row).map((v: any, cIdx: number) => (
                        <td key={cIdx}>{typeof v === "number" ? v.toLocaleString() : String(v)}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="explain-empty">
              <div>
                <strong>{activeScenario.strategy}</strong>
                <p>Click &quot;Run Benchmark&quot; to test execution times across 41.5 million fact records.</p>
              </div>
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}