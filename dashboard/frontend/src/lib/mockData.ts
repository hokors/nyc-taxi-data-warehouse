export type DimensionKey = "Time" | "Location" | "Payment Type" | "Vendor" | "Rate Code";

export type DimensionDefinition = {
  table: string;
  hierarchy: string[];
  alternatives: string[];
  roles: string[];
};

export const dimensions: Record<DimensionKey, DimensionDefinition> = {
  Time: {
    table: "dim_datetime",
    hierarchy: ["Year", "Quarter", "Month", "Day", "Hour"],
    alternatives: ["Time of Day", "Weekend / Weekday"],
    roles: ["Pickup Time", "Drop-off Time"],
  },
  Location: {
    table: "dim_location",
    hierarchy: ["Borough", "Zone", "Location ID"],
    alternatives: ["Service Zone"],
    roles: ["Pickup Location", "Drop-off Location", "Pickup-to-Drop-off Flow"],
  },
  "Payment Type": {
    table: "dim_payment_type",
    hierarchy: ["Payment Type Name"],
    alternatives: [],
    roles: [],
  },
  Vendor: {
    table: "dim_vendor",
    hierarchy: ["Vendor Name"],
    alternatives: [],
    roles: [],
  },
  "Rate Code": {
    table: "dim_ratecode",
    hierarchy: ["Rate Code Name"],
    alternatives: [],
    roles: [],
  },
};

export const measures = [
  { label: "Trip Count", expression: "COUNT(*)", format: "count" },
  { label: "Total Gross Charges", expression: "SUM(total_amount)", format: "currency" },
  { label: "Base Fare Revenue", expression: "SUM(fare_amount)", format: "currency" },
  { label: "Average Total per Trip", expression: "AVG(total_amount)", format: "currency" },
  { label: "Total Tips", expression: "SUM(tip_amount)", format: "currency" },
  { label: "Total Distance", expression: "SUM(trip_distance)", format: "distance" },
  { label: "Average Trip Distance", expression: "AVG(trip_distance)", format: "distance" },
] as const;

export const sampleGroups: Record<string, string[]> = {
  Year: ["2019", "2020", "2021", "2022", "2023", "2024"],
  Quarter: ["2023 Q3", "2023 Q4", "2024 Q1", "2024 Q2", "2024 Q3", "2024 Q4"],
  Month: ["January", "February", "March", "April", "May", "June"],
  Day: ["Jun 10", "Jun 11", "Jun 12", "Jun 13", "Jun 14", "Jun 15"],
  Hour: ["6 AM", "8 AM", "10 AM", "12 PM", "4 PM", "8 PM"],
  "Time of Day": ["Morning Rush", "Afternoon", "Evening Rush", "Night"],
  "Weekend / Weekday": ["Weekday", "Weekend"],
  Borough: ["Manhattan", "Queens", "Brooklyn", "Bronx", "Staten Island"],
  Zone: ["Midtown Center", "Upper East Side South", "JFK Airport", "Times Sq/Theatre District", "LaGuardia Airport"],
  "Service Zone": ["Yellow Zone", "Boro Zone", "Airports", "EWR"],
  "Location ID": ["161", "237", "132", "230", "138"],
  "Payment Type Name": ["Credit card", "Cash", "No charge", "Dispute"],
  "Vendor Name": ["Creative Mobile Technologies", "VeriFone Inc."],
  "Rate Code Name": ["Standard rate", "JFK", "Newark", "Negotiated fare"],
};

export const overviewZones = [
  { borough: "Manhattan", zone: "Midtown Center", trips: "186K", width: 94 },
  { borough: "Manhattan", zone: "Upper East Side South", trips: "164K", width: 83 },
  { borough: "Queens", zone: "JFK Airport", trips: "142K", width: 72 },
  { borough: "Manhattan", zone: "Times Sq / Theatre District", trips: "128K", width: 65 },
  { borough: "Queens", zone: "LaGuardia Airport", trips: "109K", width: 55 },
];

export const pivotDimensions = [
  "Borough",
  "Month",
  "Payment Type Name",
  "Vendor Name",
  "Time of Day",
] as const;

export const performanceQueries = [
  { name: "Monthly trip roll-up", strategy: "Composite index", note: "Candidate date-key index; not yet tested." },
  { name: "Zone fare aggregation", strategy: "Covering index", note: "Candidate location and amount coverage; not yet tested." },
  { name: "Payment type slice", strategy: "Query reformulation", note: "Join and predicate order comparison pending." },
  { name: "Quarterly revenue cube", strategy: "Summary table", note: "Aggregate table experiment pending approval." },
];
