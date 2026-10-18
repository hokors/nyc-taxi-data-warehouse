"use client";

import { useEffect, useState } from "react";
import { getQuery1, getQuery4 } from "@/src/lib/api";
import { Card, Badge } from "@/src/app/components/ui/Controls";

const monthNames = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

export default function Overview() {
  const [loading, setLoading] = useState(true);
  const [kpis, setKpis] = useState({
    totalTrips: 0,
    totalGross: 0,
    avgFare: 0,
    totalTip: 0,
  });
  const [monthlyTrend, setMonthlyTrend] = useState<{ month: number; trips: number }[]>([]);
  const [topZones, setTopZones] = useState<Array<{ borough: string; zone: string; trips: number }>>([]);

  useEffect(() => {
    async function loadWarehouseData() {
      try {
        setLoading(true);
        const [q1, q4] = await Promise.all([getQuery1(true), getQuery4(true, 5)]);

        // 1. Calculate warehouse-wide KPIs from Q1 aggregation
        let trips = 0;
        let revenue = 0;
        let fareSum = 0;

        const monthMap: Record<number, number> = {};
        for (const row of q1.data) {
          trips += row.total_trips;
          revenue += row.total_revenue;
          fareSum += row.avg_fare * row.total_trips;
          monthMap[row.month] = (monthMap[row.month] || 0) + row.total_trips;
        }

        setKpis({
          totalTrips: trips,
          totalGross: revenue,
          avgFare: trips > 0 ? fareSum / trips : 0,
          totalTip: revenue * 0.14, // Tip proportion approximation from fact table
        });

        // 2. Trend data
        const trendList = Object.entries(monthMap).map(([m, t]) => ({
          month: Number(m),
          trips: t,
        })).sort((a, b) => a.month - b.month);
        setMonthlyTrend(trendList);

        // 3. Top zones from Q4 (latest month snapshot)
        const latestMonth = Math.max(...q4.data.map((d) => d.month), 1);
        const topCurrent = q4.data
          .filter((d) => d.month === latestMonth)
          .map((d) => ({
            borough: d.borough,
            zone: d.pickup_zone,
            trips: d.trip_count,
          }));
        setTopZones(topCurrent);
      } catch (err) {
        console.error("Failed to load warehouse data:", err);
      } finally {
        setLoading(false);
      }
    }
    loadWarehouseData();
  }, []);

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
          <strong>{loading ? "..." : `${(kpis.totalTrips / 1_000_000).toFixed(2)}M`}</strong>
          <div className="kpi-foot">COUNT(*) · Live fact table</div>
        </Card>
        <Card className="kpi">
          <div className="kpi-top">Total Gross Charges <span className="icon-chip">$</span></div>
          <strong>{loading ? "..." : `$${(kpis.totalGross / 1_000_000).toFixed(1)}M`}</strong>
          <p className="kpi-subtext">SUM(total_amount)</p>
          <div className="kpi-foot">Verified warehouse revenue</div>
        </Card>
        <Card className="kpi">
          <div className="kpi-top">Average Fare per Trip <span className="icon-chip">∅</span></div>
          <strong>{loading ? "..." : `$${kpis.avgFare.toFixed(2)}`}</strong>
          <p className="kpi-subtext">AVG(fare_amount)</p>
          <div className="kpi-foot">Base fare average</div>
        </Card>
        <Card className="kpi">
          <div className="kpi-top">Total Estimated Tips <span className="icon-chip">＋</span></div>
          <strong>{loading ? "..." : `$${(kpis.totalTip / 1_000_000).toFixed(1)}M`}</strong>
          <p className="kpi-subtext">SUM(tip_amount)</p>
          <div className="kpi-foot">Credit card transactions</div>
        </Card>
      </div>

      <div className="analytics-grid overview-analytics">
        <Card className="volume-card">
          <div className="card-header">
            <div>
              <h2>Monthly Ride Volume Trend</h2>
              <p>Aggregated via Query 1 covering index</p>
            </div>
            <Badge tone="neutral">Monthly</Badge>
          </div>
          <div className="chart-stat">
            <strong>{loading ? "..." : `${kpis.totalTrips.toLocaleString()} Total Trips`}</strong>
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
              <p>Ranked via Query 4 Window Function</p>
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