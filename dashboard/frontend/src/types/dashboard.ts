import type { DimensionKey } from "@/lib/mockData";

export type ViewMode = "Chart" | "Table" | "Pivot";

export type FilterState = {
  paymentType: string;
  vendor: string;
  rateCode: string;
  timeOfDay: string;
  dayType: string;
  pickupBorough: string;
  dropoffBorough: string;
};

export type MetricFormat = "count" | "currency" | "distance";

export type NavigationItem = {
  label: string;
  href: string;
  icon: string;
};

export type OlapSelection = {
  dimension: DimensionKey;
  level: string;
  measure: string;
};
