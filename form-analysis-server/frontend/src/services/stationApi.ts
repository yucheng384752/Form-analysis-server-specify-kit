/**
 * Station API client — fetches generic station/schema data from backend.
 *
 * All requests go through the global fetch wrapper which auto-injects
 * X-Tenant-Id and X-API-Key headers.
 */

import type {
  FieldDef,
  StationInfo,
  StationLinkInfo,
  StationSchema,
  TraceNode,
  ValidationRuleInfo,
} from '../types/api';

const BASE = '/api/stations';

async function json<T>(url: string): Promise<T> {
  const res = await fetch(url);
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export async function fetchStations(): Promise<StationInfo[]> {
  return json<StationInfo[]>(BASE);
}

export async function fetchStationSchema(code: string): Promise<StationSchema> {
  return json<StationSchema>(`${BASE}/${code}/schema`);
}

export async function fetchFilterableFields(code: string): Promise<FieldDef[]> {
  return json<FieldDef[]>(`${BASE}/${code}/schema/fields`);
}

export async function fetchValidationRules(code: string): Promise<ValidationRuleInfo[]> {
  return json<ValidationRuleInfo[]>(`${BASE}/${code}/validation-rules`);
}

export async function fetchAnalyticsMapping(
  code: string
): Promise<Array<{ source_path: string; output_column: string; output_order: number }>> {
  return json(`${BASE}/${code}/analytics-mapping`);
}

export async function fetchStationLinks(): Promise<StationLinkInfo[]> {
  return json<StationLinkInfo[]>(`${BASE}/links`);
}

export async function fetchTraceabilityChain(
  lotNoNorm: number,
  startStation?: string
): Promise<TraceNode[]> {
  const qs = startStation ? `?start_station=${startStation}` : '';
  return json<TraceNode[]>(`${BASE}/traceability/${lotNoNorm}${qs}`);
}
