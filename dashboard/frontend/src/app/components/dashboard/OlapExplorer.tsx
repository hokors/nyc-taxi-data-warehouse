"use client";

import { useEffect, useState } from "react";
import { getQuery1, getQuery2, getQuery3, getQuery4, getQuery5 } from "@/src/lib/api";
import { Card, Button, Badge } from "@/src/app/components/ui/Controls";

const queryTabs = [
  { id: 1, label: "Q1: Monthly & Time-of-Day", desc: "Temporal roll-up across months and rush hours" },
  { id: 2, label: "Q2: Inter-Borough Flow", desc: "Origin-destination slice and dice" },
  { id: 3, label: "Q3: Payment Hierarchical Rollup", desc: "WITH ROLLUP grouping on payment and dates" },
  { id: 4, label: "Q4: Zone Ranking Window", desc: "DENSE_RANK() partition by month" },
  { id: 5, label: "Q5: Vendor & Rate Code", desc: "Multi-dimensional categorical comparison" },
];

export default function OlapExplorer() {
  const [activeTab, setActiveTab] = useState(1);
  const [data, setData] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [executionTime, setExecutionTime] = useState<number | null>(null);

  useEffect(() => {
    async function fetchActiveQuery() {
      try {
        setLoading(true);
        let res: any;
        if (activeTab === 1) res = await getQuery1(false);
        else if (activeTab === 2) res = await getQuery2(false, 20);
        else if (activeTab === 3) res = await getQuery3(false);
        else if (activeTab === 4) res = await getQuery4(false, 10);
        else if (activeTab === 5) res = await getQuery5(false);

        setData(res?.data || []);
        setExecutionTime(res?.execution_time_ms || null);
      } catch (err: any) {
        console.error("OLAP query error:", err);
      } finally {
        setLoading(false);
      }
    }
    fetchActiveQuery();
  }, [activeTab]);

  return (
    <div className="page-content">
      <div className="hero-row">
        <div>
          <div className="eyebrow">ANALYTICAL WORKSPACE</div>
          <h1>OLAP Explorer</h1>
          <p>Execute and inspect OLAP warehouse queries across 41.5 million rides.</p>
        </div>
        <Badge tone="green">Live MySQL Data</Badge>
      </div>

      <Card className="workspace-controls">
        <div className="control-section-heading">
          <span>01</span>
          <div>
            <strong>Select OLAP Dimension & Query Scenario</strong>
            <small>Choose between Roll-up, Drill-down, Slicing, and Window Functions.</small>
          </div>
        </div>
        <div style={{ display: "flex", gap: "8px", marginTop: "16px", flexWrap: "wrap" }}>
          {queryTabs.map((tab) => (
            <Button
              key={tab.id}
              variant={activeTab === tab.id ? "primary" : "secondary"}
              onClick={() => setActiveTab(tab.id)}
            >
              {tab.label}
            </Button>
          ))}
        </div>
      </Card>

      <Card className="results-card">
        <div className="results-head">
          <div>
            <h2>{queryTabs.find((t) => t.id === activeTab)?.label}</h2>
            <p className="card-header">
              <span>{queryTabs.find((t) => t.id === activeTab)?.desc}</span>
            </p>
          </div>
          {executionTime !== null && (
            <Badge tone="neutral">Executed in {executionTime} ms</Badge>
          )}
        </div>

        {loading ? (
          <div style={{ padding: "40px", textAlign: "center", color: "#66726d" }}>
            Running query against warehouse...
          </div>
        ) : (
          <div className="table-scroll" style={{ padding: "0 20px 20px" }}>
            <table>
              <thead>
                <tr>
                  {Object.keys(data[0] || {}).map((col) => (
                    <th key={col}>{col.replace(/_/g, " ").toUpperCase()}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data.map((row, idx) => (
                  <tr key={idx}>
                    {Object.values(row).map((val: any, cIdx) => (
                      <td key={cIdx}>
                        {typeof val === "number" ? val.toLocaleString() : String(val ?? "NULL")}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}