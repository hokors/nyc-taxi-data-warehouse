const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function fetchJson<T>(url: string): Promise<T> {
  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) {
    const errorBody = await res.json().catch(() => ({}));
    throw new Error(errorBody.detail || `Request failed with status ${res.status}`);
  }
  return res.json();
}

export async function getHealthDb() {
  return fetchJson<{ status: string; database: string }>(`${API_URL}/api/health-db`);
}

export async function getQuery1(useIndex = true) {
  return fetchJson<{
    query_name: string;
    execution_time_ms: number;
    used_covering_index: boolean;
    row_count: number;
    data: Array<{
      year: number;
      month: number;
      time_of_day: string;
      total_trips: number;
      total_revenue: number;
      avg_trip_distance: number;
      avg_fare: number;
    }>;
  }>(`${API_URL}/api/analytics/query-1?use_index=${useIndex}`);
}

export async function getQuery2(useIndex = true, limit = 20) {
  return fetchJson<{
    query_name: string;
    execution_time_ms: number;
    used_covering_index: boolean;
    row_count: number;
    data: Array<{
      pickup_borough: string;
      dropoff_borough: string;
      trip_count: number;
      total_revenue: number;
      avg_tip: number;
      avg_tolls: number;
    }>;
  }>(`${API_URL}/api/analytics/query-2?use_index=${useIndex}&limit=${limit}`);
}

export async function getQuery3(useIndex = true) {
  return fetchJson<{
    query_name: string;
    execution_time_ms: number;
    used_covering_index: boolean;
    row_count: number;
    data: Array<{
      payment_type_name: string;
      year: number;
      month: number;
      total_trips: number;
      total_revenue: number;
      total_tips: number;
    }>;
  }>(`${API_URL}/api/analytics/query-3?use_index=${useIndex}`);
}

export async function getQuery4(useIndex = true, topN = 5) {
  return fetchJson<{
    query_name: string;
    execution_time_ms: number;
    used_covering_index: boolean;
    row_count: number;
    data: Array<{
      month: number;
      revenue_rank: number;
      pickup_zone: string;
      borough: string;
      trip_count: number;
      revenue: number;
    }>;
  }>(`${API_URL}/api/analytics/query-4?use_index=${useIndex}&top_n=${topN}`);
}

export async function getQuery5(useIndex = true) {
  return fetchJson<{
    query_name: string;
    execution_time_ms: number;
    used_covering_index: boolean;
    row_count: number;
    data: Array<{
      vendor_name: string;
      ratecode_name: string;
      total_trips: number;
      total_base_fare: number;
      total_airport_fees: number;
      total_cbd_fees: number;
      avg_passengers: number;
    }>;
  }>(`${API_URL}/api/analytics/query-5?use_index=${useIndex}`);
}

export async function runBenchmark(queryNumber: number) {
  return fetchJson<{
    query_number: number;
    query_name: string;
    baseline_time_ms: number;
    optimized_time_ms: number;
    speedup: string;
    sample_data: any[];
  }>(`${API_URL}/api/analytics/benchmark/${queryNumber}`);
}