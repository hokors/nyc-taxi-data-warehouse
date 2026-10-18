"use client";

import { useState } from "react";
import { performanceQueries } from "@/src/lib/mockData";
import { Card, Badge } from "@/src/app/components/ui/Controls";

export default function QueryPerformance() {
  const [selected, setSelected] = useState(0);
  const query = performanceQueries[selected];
  return (
    <div className="page-content">
      <div className="hero-row"><div><div className="eyebrow"> QUERY BENCHMARKS</div><h1>Query Performance</h1><p>Compare baseline and optimized warehouse queries using measured execution times.</p></div><Badge tone="amber">Awaiting benchmarks</Badge></div>
      <div className="perf-summary">
        <Card><span>Baseline runtime</span><strong>—</strong><small>Run against MySQL to populate</small></Card>
        <Card><span>Optimized runtime</span><strong>—</strong><small>Run against MySQL to populate</small></Card>
        <Card className="pending-card"><span>Performance improvement</span><strong>Pending</strong><small>No timing data has been recorded</small></Card>
      </div>
      <Card className="table-card performance-table">
        <div className="card-header" style={{padding: "18px 20px"}}><div><h2>Benchmark scenarios</h2><p>Select a scenario to inspect its proposed optimization.</p></div></div>
        <div className="table-scroll"><table><thead><tr><th>Query scenario</th><th>Optimization strategy</th><th>Status</th></tr></thead><tbody>{performanceQueries.map((q, i) => <tr key={q.name} className={selected === i ? "selected-row" : ""} onClick={() => setSelected(i)}><td><strong>{q.name}</strong></td><td>{q.strategy}</td><td><Badge tone="amber">Not tested</Badge></td></tr>)}</tbody></table></div>
      </Card>
      <div className="comparison-grid">
        <Card className="sql-card"><div className="card-header"><div><h2>Selected scenario</h2><p>{query.name}</p></div><Badge tone="neutral">Plan</Badge></div><pre>{`-- ${query.name}\n-- Proposed strategy: ${query.strategy}\n-- Run EXPLAIN and record actual timings.\n-- Do not report a speedup until measured.`}</pre></Card>
        <Card className="explain-card"><div className="card-header"><div><h2>Optimization notes</h2><p>Implementation status</p></div></div><div className="explain-empty"><div><strong>{query.strategy}</strong><p>{query.note} Capture baseline and optimized execution times and EXPLAIN output before drawing conclusions.</p></div></div></Card>
      </div>
      <Card className="performance-note"><div className="insight-icon">i</div><div><strong>Benchmarking reminder</strong><p>Use the same dataset, parameters, and test conditions for both versions. Record actual results from MySQL; this screen intentionally does not invent runtime measurements.</p></div></Card>
    </div>
  );
}
