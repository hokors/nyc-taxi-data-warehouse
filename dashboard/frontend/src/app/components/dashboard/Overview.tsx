"use client";

import { useEffect, useState } from "react";
import { getOverview } from "@/src/lib/api";
import { Card, Badge } from "@/src/app/components/ui/Controls";

const monthNames = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

export default function Overview() {
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState<{
    total_trips: number;
    total_gross: number;
    avg_fare: number;
    total_tips: number;
    top_zones: Array<{ borough: string; zone: string; trips: number }>;
    monthly_trend: Array<{ month: number; trips: number }>;
  } | null>(null);

  useEffect(() => {
    async function loadData() {
      try {
        setLoading(true);
        const res = await getOverview();
        setData(res);
      } catch (err) {
        console.error("Failed to load warehouse data:", err);
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, []);

  const monthlyTrend = data?.monthly_trend || [];
  const topZones = data?.top_zones || [];
  const maxTrips = Math.max(...monthlyTrend.map((t) => t.trips), 1);
  const trendPoints = monthlyTrend
    .map((v, i) => `${(i / Math.max(monthlyTrend.length - 1, 1)) * 600},${200 - (v.trips / maxTrips) * 160}`)
    .join(" ");

  return (
    <div className="page-content">
      <div className="hero-row">
        <div>
          <div className="eyebrow">DATA OVERVIEW</div>
          <h1>NYC Taxi Overview</h1>
          <p>Aggregated metrics from 41,525,925 fact rides in local MySQL warehouse.</p>
        </div>
        <Badge tone={loading ? "amber" : "green"}>
          {loading ? "Querying MySQL..." : "Connected: nyc_taxi_warehouse"}
        </Badge>
      </div>

      <div className="kpi-grid">
        <Card className="kpi featured">
          <div className="kpi-top">Total Trips <span className="icon-chip">↗</span></div>
          <strong>{loading ? "..." : `${((data?.total_trips || 0) / 1_000_000).toFixed(2)}M`}</strong>
          <div className="kpi-foot">COUNT(*) · Live fact table</div>
        </Card>
        <Card className="kpi">
          <div className="kpi-top">Total Gross Charges <span className="icon-chip">$</span></div>
          <strong>{loading ? "..." : `$${((data?.total_gross || 0) / 1_000_000).toFixed(1)}M`}</strong>
          <p className="kpi-subtext">SUM(total_amount)</p>
          <div className="kpi-foot">Verified warehouse revenue</div>
        </Card>
        <Card className="kpi">
          <div className="kpi-top">Average Fare per Trip <span className="icon-chip">∅</span></div>
          <strong>{loading ? "..." : `$${(data?.avg_fare || 0).toFixed(2)}`}</strong>
          <p className="kpi-subtext">AVG(fare_amount)</p>
          <div className="kpi-foot">Base fare average</div>
        </Card>
        <Card className="kpi">
          <div className="kpi-top">Total Estimated Tips <span className="icon-chip">＋</span></div>
          <strong>{loading ? "..." : `$${((data?.total_tips || 0) / 1_000_000).toFixed(1)}M`}</strong>
          <p className="kpi-subtext">SUM(tip_amount)</p>
          <div className="kpi-foot">Credit card transactions</div>
        </Card>
      </div>

      <div className="analytics-grid overview-analytics">
        <Card className="volume-card">
          <div className="card-header">
            <div>
              <h2>Monthly Ride Volume Trend</h2>
              <p>Temporal distribution across 12 months</p>
            </div>
            <Badge tone="neutral">Monthly</Badge>
          </div>
          <div className="chart-stat">
            <strong>{loading ? "..." : `${(data?.total_trips || 0).toLocaleString()} Total Trips`}</strong>
          </div>
          <div className="chart-wrap">
            <svg viewBox="0 0 600 220" role="img">
              {[40, 80, 120, 160, 200].map((y) => (
                <line key={y} x1="0" y1={y} x2="600" y2={y} className="grid-line" />
              ))}
              {trendPoints && <polyline points={trendPoints} className="line-main" />}
              {monthlyTrend.map((v, i) => (
                <circle
                  key={i}
                  cx={(i / Math.max(monthlyTrend.length - 1, 1)) * 600}
                  cy={200 - (v.trips / maxTrips) * 160}
                  r="4"
                  className="line-dot"
                />
              ))}
              <g className="axis-labels">
                {monthlyTrend.map((m, i) => (
                  <text key={i} x={(i / Math.max(monthlyTrend.length - 1, 1)) * 560} y="215">
                    {monthNames[m.month - 1] || `M${m.month}`}
                  </text>
                ))}
              </g>
            </svg>
          </div>
        </Card>

        <Card className="zone-card">
          <div className="card-header">
            <div>
              <h2>Top Pickup Zones</h2>
              <p>Ranked by trip count across warehouse</p>
            </div>
            <Badge>Pickup</Badge>
          </div>
          <div className="zone-list">
            {topZones.map((z, i) => (
              <div className="zone-item" key={z.zone + i}>
                <div className="zone-rank">
                  <span>#{i + 1} · {z.borough}</span>
                  <strong>{z.zone}</strong>
                </div>
                <div className="zone-value">
                  <strong>{z.trips.toLocaleString()} trips</strong>
                </div>
                <div className="bar-track">
                  <div
                    className="bar-fill"
                    style={{
                      width: `${Math.round((z.trips / (topZones[0]?.trips || 1)) * 100)}%`,
                    }}
                  />
                </div>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </div>
  );
}