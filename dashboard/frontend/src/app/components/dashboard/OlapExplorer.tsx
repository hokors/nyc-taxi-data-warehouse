"use client";

import { useMemo, useState } from "react";
import { dimensions, measures, sampleGroups, pivotDimensions, type DimensionKey } from "@/src/lib/mockData";
import { Card, Button, SelectField, Badge } from "@/src/app/components/ui/Controls";

const dimensionKeys = Object.keys(dimensions) as DimensionKey[];
const levelsFor = (dimension: DimensionKey) => [...dimensions[dimension].hierarchy, ...dimensions[dimension].alternatives];
const demoValues = [186000, 164000, 142000, 128000, 109000, 94000];

export default function OlapExplorer() {
  const [dimension, setDimension] = useState<DimensionKey>("Time");
  const [level, setLevel] = useState("Month");
  const [measureIndex, setMeasureIndex] = useState("0");
  const [role, setRole] = useState("Pickup Time");
  const [view, setView] = useState("Chart");
  const [rowDim, setRowDim] = useState("Borough");
  const [colDim, setColDim] = useState("Payment Type Name");
  const [payment, setPayment] = useState("All");
  const [vendor, setVendor] = useState("All");
  const [rateCode, setRateCode] = useState("All");
  const [timeOfDay, setTimeOfDay] = useState("All");
  const [dayType, setDayType] = useState("All");
  const [pickupBorough, setPickupBorough] = useState("All");
  const [dropoffBorough, setDropoffBorough] = useState("All");
  const [filtersApplied, setFiltersApplied] = useState(false);

  const levels = levelsFor(dimension);
  const selectedLevel = levels.includes(level) ? level : levels[0];
  const groups = sampleGroups[selectedLevel] ?? sampleGroups[levels[0]] ?? ["Sample A", "Sample B"];
  const measure = measures[Number(measureIndex)] ?? measures[0];
  const activeFilterCount = [payment, vendor, rateCode, timeOfDay, dayType, pickupBorough, dropoffBorough].filter(v => v !== "All").length;
  const resultRows = useMemo(() => groups.map((label, i) => ({ label, value: demoValues[i % demoValues.length] - i * 3200 })), [groups]);

  function changeDimension(next: string) {
    const d = next as DimensionKey;
    setDimension(d);
    setLevel(dimensions[d].hierarchy[0]);
    setRole(dimensions[d].roles[0] ?? "Not role-specific");
  }
  function rollUp() {
    const i = levels.indexOf(selectedLevel);
    if (i > 0) setLevel(levels[i - 1]);
  }
  function drillDown() {
    const i = levels.indexOf(selectedLevel);
    if (i < levels.length - 1) setLevel(levels[i + 1]);
  }
  function resetFilters() {
    setPayment("All"); setVendor("All"); setRateCode("All"); setTimeOfDay("All");
    setDayType("All"); setPickupBorough("All"); setDropoffBorough("All"); setFiltersApplied(false);
  }

  return (
    <div className="page-content">
      <div className="hero-row"><div><div className="eyebrow"> ANALYTICAL WORKSPACE</div><h1>OLAP Explorer</h1><p>Explore dimensions, aggregation levels, filters, and pivoted summaries.</p></div><Badge tone="amber">Mock results only</Badge></div>
      <Card className="workspace-controls">
        <div className="control-section-heading"><span>01</span><div><strong>Choose your analysis</strong><small>Select a dimension, hierarchy level, and aggregation measure.</small></div></div>
        <div className="control-grid">
          <SelectField label="Dimension" value={dimension} options={dimensionKeys} onChange={changeDimension} />
          <SelectField label="Group by level" value={selectedLevel} options={levels} onChange={setLevel} />
          <SelectField label="Measure" value={measureIndex} options={measures.map((m, i) => `${i} · ${m.label}`)} onChange={(v) => setMeasureIndex(v.split(" · ")[0])} wide />
          <SelectField label="Role-playing dimension" value={role} options={dimensions[dimension].roles.length ? dimensions[dimension].roles : ["Not role-specific"]} onChange={setRole} wide />
        </div>
        <div className="grouping-row">
          <div className="grouping-path"><span>Hierarchy path</span><div>{levels.map((l, i) => <span key={l}><strong className={l === selectedLevel ? "current" : ""}>{l}</strong>{i < levels.length - 1 ? <small>›</small> : null}</span>)}</div></div>
          <div className="operation-buttons"><Button onClick={rollUp} disabled={levels.indexOf(selectedLevel) === 0}>Roll Up</Button><Button variant="primary" onClick={drillDown} disabled={levels.indexOf(selectedLevel) === levels.length - 1}>Drill Down</Button></div>
        </div>
      </Card>

      <Card className="explorer-filters">
        <div className="filter-toggle"><div><span className="filter-icon">⌕</span><span><strong>Slice & Dice Filters</strong><small>Choose one filter for a slice or combine filters for a dice.</small></span></div><Badge tone="neutral">{activeFilterCount} active</Badge></div>
        <div className="filter-panel-body">
          <div className="filter-grid expanded-grid">
            <SelectField label="Payment type" value={payment} options={["All","Credit card","Cash","No charge","Dispute"]} onChange={setPayment} />
            <SelectField label="Vendor" value={vendor} options={["All","Creative Mobile Technologies","VeriFone Inc."]} onChange={setVendor} />
            <SelectField label="Rate code" value={rateCode} options={["All","Standard rate","JFK","Newark","Negotiated fare"]} onChange={setRateCode} />
            <SelectField label="Time of day" value={timeOfDay} options={["All","Morning Rush","Afternoon","Evening Rush","Night"]} onChange={setTimeOfDay} />
            <SelectField label="Day type" value={dayType} options={["All","Weekday","Weekend"]} onChange={setDayType} />
            <SelectField label="Pickup borough" value={pickupBorough} options={["All","Manhattan","Queens","Brooklyn","Bronx","Staten Island","EWR"]} onChange={setPickupBorough} />
            <SelectField label="Drop-off borough" value={dropoffBorough} options={["All","Manhattan","Queens","Brooklyn","Bronx","Staten Island","EWR"]} onChange={setDropoffBorough} />
          </div>
          <div className="filter-footer"><p>Prototype controls do not execute SQL yet.</p><div><Button onClick={resetFilters}>Reset</Button><Button variant="primary" onClick={() => setFiltersApplied(true)}>Apply filters</Button></div></div>
          {filtersApplied && <div className="applied-note"><span>Applied</span> {activeFilterCount} filter(s) selected. The mock display is unchanged until backend integration.</div>}
        </div>
      </Card>

      <Card className="results-card">
        <div className="results-head"><div><h2>{measure.label} by {selectedLevel}</h2><p className="card-header"><span>{measure.expression} · role: {role}</span></p></div><div className="segmented">{["Chart","Table","Pivot"].map(v => <button key={v} className={view === v ? "active" : ""} onClick={() => setView(v)}>{v}</button>)}</div></div>
        <div className="prototype-notice">These values are illustrative sample results, not live database output. <Badge tone="amber">Not connected to API</Badge></div>
        {view === "Chart" && <div className="result-bars">{resultRows.map((r, i) => <button className="result-bar-row" key={r.label} onClick={() => setLevel(selectedLevel)}><span>{r.label}</span><div className="result-bar-track"><i style={{width: `${Math.max(12, 100 - i * 13)}%`}} /></div><strong>{r.value.toLocaleString()}</strong><span>›</span></button>)}</div>}
        {view === "Table" && <div className="table-scroll"><table><thead><tr><th>{selectedLevel}</th><th>{measure.label}</th><th>Source</th></tr></thead><tbody>{resultRows.map(r => <tr key={r.label}><td><strong>{r.label}</strong></td><td>{r.value.toLocaleString()}</td><td>Mock data</td></tr>)}</tbody></table></div>}
        {view === "Pivot" && <div className="pivot-workspace"><div className="pivot-controls"><SelectField label="Rows" value={rowDim} options={[...pivotDimensions]} onChange={setRowDim} /><div className="pivot-swap">×</div><SelectField label="Columns" value={colDim} options={[...pivotDimensions]} onChange={setColDim} /></div><p className="query-description">Pivot preview: {rowDim} × {colDim} · {measure.expression}. Matrix values below are placeholders.</p><div className="table-scroll"><table className="pivot-table"><thead><tr><th>{rowDim}</th><th>Category A</th><th>Category B</th><th>Total</th></tr></thead><tbody>{["Manhattan","Queens","Brooklyn","Bronx"].map((name, i) => <tr key={name}><td><strong>{name}</strong></td><td>{(demoValues[i] / 2).toLocaleString()}</td><td>{(demoValues[i] / 3).toLocaleString()}</td><td><strong>{demoValues[i].toLocaleString()}</strong></td></tr>)}</tbody></table></div><div className="pivot-footnote">Placeholder pivot data only. Real totals and subtotals must come from the backend query.</div></div>}
      </Card>
    </div>
  );
}
