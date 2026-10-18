const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function fetchJson<T>(url: string): Promise<T> {
  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) {
    const errorBody = await res.json().catch(() => ({}));
    throw new Error(errorBody.detail || `Request failed with status ${res.status}`);
  }
  return res.json();
}

export async function getOverview() {
  return fetchJson<{
    total_trips: number;
    total_gross: number;
    avg_fare: number;
    total_tips: number;
    top_zones: Array<{ borough: string; zone: string; trips: number }>;
    monthly_trend: Array<{ month: number; trips: number }>;
  }>(`${API_URL}/api/analytics/overview`);
}

export async function getQuery1() {
  return fetchJson<any>(`${API_URL}/api/analytics/query-1`);
}

export async function getQuery2(limit = 20) {
  return fetchJson<any>(`${API_URL}/api/analytics/query-2?limit=${limit}`);
}

export async function getQuery3() {
  return fetchJson<any>(`${API_URL}/api/analytics/query-3`);
}

export async function getQuery4(topN = 5) {
  return fetchJson<any>(`${API_URL}/api/analytics/query-4?top_n=${topN}`);
}

export async function getQuery5() {
  return fetchJson<any>(`${API_URL}/api/analytics/query-5`);
}

export async function runBenchmark(queryNumber: number) {
  return fetchJson<any>(`${API_URL}/api/analytics/benchmark/${queryNumber}`);
}