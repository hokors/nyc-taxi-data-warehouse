"use client";

import { useState } from "react";
import { overviewZones } from "@/src/lib/mockData";
import { Card, SelectField, Badge } from "@/src/app/components/ui/Controls";

const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const chartValues: Record<string, number[]> = {
  Year: [30, 38, 43, 48, 54, 59, 64, 61, 70, 74, 80, 86],
  Quarter: [43, 55, 50, 70, 66, 86, 78, 92],
  Month: [35, 49, 42, 63, 57, 72, 61, 79, 70, 88, 76, 95],
  Day: [32, 45, 39, 57, 48, 66, 59, 75, 68, 86, 78, 93],
  Hour: [24, 30, 43, 58, 66, 54, 73, 84, 71, 92, 79, 87],
};

function TrendChart({ level }: { level: string }) {
  const values = chartValues[level] ?? chartValues.Month;
  const points = values.map((v, i) => `${(i / (values.length - 1)) * 600},${200 - v * 1.65}`).join(" ");
  return (
    <div className="chart-wrap">
      <svg viewBox="0 0 600 220" role="img" aria-label={`Illustrative trip trend by ${level.toLowerCase()}`}>
        {[40, 80, 120, 160, 200].map((y) => <line key={y} x1="0" y1={y} x2="600" y2={y} className="grid-line" />)}
        <polyline points={points} className="line-main" />
        {values.map((v, i) => <circle key={i} cx={(i / (values.length - 1)) * 600} cy={200 - v * 1.65} r="3.5" className="line-dot" />)}
        <g className="axis-labels">
          {months.filter((_, i) => i % 2 === 0).map((m, i) => <text key={m} x={i * 100} y="218">{m}</text>)}
        </g>
      </svg>
    </div>
  );
}

export default function Overview() {
  const [level, setLevel] = useState("Month");
  return (
    <div className="page-content">
      <div className="hero-row"><div><div className="eyebrow"> DATA OVERVIEW</div><h1>NYC Taxi Overview</h1><p>Explore ride volume, gross charges, and pickup-zone activity.</p></div><Badge tone="amber">Database not yet connected</Badge></div>
      <div className="kpi-grid">
        <Card className="kpi featured"><div className="kpi-top">Total Trips <span className="icon-chip">↗</span></div><strong>1.48M</strong><div className="kpi-foot">COUNT(*) · sample display</div></Card>
        <Card className="kpi"><div className="kpi-top">Total Gross Charges <span className="icon-chip">$</span></div><strong>$32.6M</strong><p className="kpi-subtext">SUM(total_amount)</p><div className="kpi-foot">Illustrative value</div></Card>
        <Card className="kpi"><div className="kpi-top">Average Total per Trip <span className="icon-chip">∅</span></div><strong>$22.03</strong><p className="kpi-subtext">AVG(total_amount)</p><div className="kpi-foot">Illustrative value</div></Card>
        <Card className="kpi"><div className="kpi-top">Total Tips <span className="icon-chip">＋</span></div><strong>$4.8M</strong><p className="kpi-subtext">SUM(tip_amount)</p><div className="kpi-foot">Illustrative value</div></Card>
      </div>
      <div className="analytics-grid overview-analytics">
        <Card className="volume-card">
          <div className="card-header"><div><h2>Ride Volume Trend</h2><p>Illustrative pattern; not queried from MySQL</p></div><SelectField label="Group by" value={level} options={["Year","Quarter","Month","Day","Hour"]} onChange={setLevel} /></div>
          <div className="chart-stat"><strong>Ride volume</strong><Badge tone="neutral">By {level}</Badge></div>
          <div className="chart-hierarchy">{["Year","Quarter","Month","Day","Hour"].map((x) => <button key={x} className={level === x ? "active" : ""} onClick={() => setLevel(x)}>{x}</button>)}</div>
          <TrendChart level={level} />
        </Card>
        <Card className="zone-card">
          <div className="card-header"><div><h2>Top Pickup Zones</h2><p>Sample ranking for layout preview</p></div><Badge>Pickup</Badge></div>
          <div className="zone-list">{overviewZones.map((z, i) => <div className="zone-item" key={z.zone}><div className="zone-rank"><span>#{i+1} · {z.borough}</span><strong>{z.zone}</strong></div><div className="zone-value"><strong>{z.trips}</strong></div><div className="bar-track"><div className="bar-fill" style={{width: `${z.width}%`}} /></div></div>)}</div>
          <div className="role-context">These figures are placeholder examples. Replace with aggregated results from the warehouse before reporting findings.</div>
        </Card>
      </div>
    </div>
  );
}
