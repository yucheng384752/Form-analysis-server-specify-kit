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
import { getAdminApiKeyHeaderName, getAdminApiKeyValue } from './adminAuth';

const BASE = '/api/stations';

function adminHeaders(): Record<string, string> {
  const key = getAdminApiKeyValue();
  if (!key) return {};
  return { [getAdminApiKeyHeaderName()]: key };
}

async function json<T>(url: string): Promise<T> {
  const res = await fetch(url);
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

async function mutate<T>(url: string, method: string, body?: unknown): Promise<T> {
  const init: RequestInit = {
    method,
    headers: { 'Content-Type': 'application/json', ...adminHeaders() },
  };
  if (body !== undefined) {
    init.body = JSON.stringify(body);
  }
  const res = await fetch(url, init);
  if (res.status === 204) return undefined as T;
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

// ------------------------------------------------------------------
// Read-only endpoints
// ------------------------------------------------------------------

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
): Promise<Array<{ source_path: string; output_column: string; output_order: number; data_type: string; null_if_missing: boolean; id: string }>> {
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

// ------------------------------------------------------------------
// Admin CRUD endpoints
// ------------------------------------------------------------------

export async function createStation(body: {
  code: string; name: string; sort_order?: number; has_items?: boolean;
}): Promise<StationInfo> {
  return mutate<StationInfo>(BASE, 'POST', body);
}

export async function updateStation(code: string, body: {
  name?: string; sort_order?: number; has_items?: boolean;
}): Promise<StationInfo> {
  return mutate<StationInfo>(`${BASE}/${code}`, 'PUT', body);
}

export async function deleteStation(code: string): Promise<void> {
  return mutate(`${BASE}/${code}`, 'DELETE');
}

export async function upsertStationSchema(code: string, body: {
  record_fields: Array<Record<string, unknown>>;
  item_fields?: Array<Record<string, unknown>> | null;
  unique_key_fields?: string[];
  csv_signature_columns?: string[] | null;
  csv_filename_pattern?: string | null;
  csv_field_mapping?: Record<string, unknown> | null;
}): Promise<StationSchema> {
  return mutate<StationSchema>(`${BASE}/${code}/schema`, 'PUT', body);
}

export async function createValidationRule(body: {
  field_name: string; rule_type: string; rule_config: Record<string, unknown>;
  station_code?: string | null;
}): Promise<ValidationRuleInfo> {
  return mutate<ValidationRuleInfo>(`${BASE}/validation-rules`, 'POST', body);
}

export async function updateValidationRule(id: string, body: {
  field_name?: string; rule_type?: string; rule_config?: Record<string, unknown>;
  is_active?: boolean;
}): Promise<ValidationRuleInfo> {
  return mutate<ValidationRuleInfo>(`${BASE}/validation-rules/${id}`, 'PUT', body);
}

export async function deleteValidationRule(id: string): Promise<void> {
  return mutate(`${BASE}/validation-rules/${id}`, 'DELETE');
}

export async function createAnalyticsMapping(body: {
  station_code: string; source_path: string; output_column: string;
  output_order: number; data_type?: string; null_if_missing?: boolean;
}): Promise<{ id: string; source_path: string; output_column: string; output_order: number }> {
  return mutate(`${BASE}/analytics-mappings`, 'POST', body);
}

export async function updateAnalyticsMapping(id: string, body: {
  source_path?: string; output_column?: string; output_order?: number;
  data_type?: string; null_if_missing?: boolean;
}): Promise<{ id: string; source_path: string; output_column: string; output_order: number }> {
  return mutate(`${BASE}/analytics-mappings/${id}`, 'PUT', body);
}

export async function deleteAnalyticsMapping(id: string): Promise<void> {
  return mutate(`${BASE}/analytics-mappings/${id}`, 'DELETE');
}

export async function createStationLink(body: {
  from_station_code: string; to_station_code: string; link_type: string;
  link_config?: Record<string, unknown> | null; sort_order?: number;
}): Promise<StationLinkInfo> {
  return mutate<StationLinkInfo>(`${BASE}/links`, 'POST', body);
}

export async function updateStationLink(id: string, body: {
  link_type?: string; link_config?: Record<string, unknown>; sort_order?: number;
}): Promise<StationLinkInfo> {
  return mutate<StationLinkInfo>(`${BASE}/links/${id}`, 'PUT', body);
}

export async function deleteStationLink(id: string): Promise<void> {
  return mutate(`${BASE}/links/${id}`, 'DELETE');
}
