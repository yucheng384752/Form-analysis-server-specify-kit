// API 回應類型
export interface ApiResponse<T = any> {
  success: boolean;
  data?: T;
  message?: string;
  errors?: string[];
}

// 檔案上傳相關類型
export interface UploadedFile {
  id: string;
  filename: string;
  size: number;
  type: string;
  uploaded_at: string;
}

export interface FileValidationError {
  row: number;
  column: string;
  message: string;
  severity: 'error' | 'warning';
}

export interface FilePreview {
  id: string;
  filename: string;
  headers: string[];
  rows: Record<string, any>[];
  errors: FileValidationError[];
  summary: {
    total_rows: number;
    valid_rows: number;
    error_rows: number;
  };
}

// 表單資料類型
export interface LotRecord {
  lot_no: string;
  created_at: string;
  updated_at: string;
}

export interface ExtrusionRecord extends LotRecord {
  material_grade?: string;
  thickness?: number;
  width?: number;
}

export interface SlittingRecord extends LotRecord {
  slitting_machine?: string;
  winder_count?: number;
  checks?: SlittingCheck[];
}

export interface SlittingCheck {
  winder_no: number;
  measurement_point?: string;
  thickness?: number;
  width?: number;
}

export interface PunchingRecord extends LotRecord {
  p3_no: string;
  punching_machine?: string;
  self_check_data?: any;
}

// API 查詢參數
export interface QueryParams {
  limit?: number;
  offset?: number;
  search?: string;
  sort_by?: string;
  sort_order?: 'asc' | 'desc';
}

// 上傳狀態
export type UploadStatus = 'idle' | 'uploading' | 'validating' | 'success' | 'error';

// 檔案類型
export type FileType = 'p1' | 'p2' | 'p3' | 'qc';

// ============================================================
// Generic Schema Types (Phase 3 — schema-driven UI)
// ============================================================

export type FieldType = 'string' | 'integer' | 'float' | 'date' | 'boolean' | 'enum';

export interface FieldDef {
  name: string;
  type: FieldType;
  label: Record<string, string>;
  required?: boolean;
  filterable?: boolean;
  indexed?: boolean;
  unit?: string;
  min?: number;
  max?: number;
  enum_values?: Array<{ value: any; label: Record<string, string> }>;
}

export interface StationInfo {
  id: string;
  code: string;
  name: string;
  sort_order: number;
  has_items: boolean;
}

export interface StationSchema {
  station_code: string;
  version: number;
  record_fields: FieldDef[];
  item_fields?: FieldDef[];
  unique_key_fields: string[];
}

export interface GenericRecord {
  id: string;
  station_code: string;
  lot_no_raw: string;
  lot_no_norm: number;
  data: Record<string, any>;
  items?: GenericRecordItem[];
  created_at: string;
}

export interface GenericRecordItem {
  id: string;
  row_no: number;
  data: Record<string, any>;
}

export interface StationLinkInfo {
  id: string;
  from_station_code: string;
  to_station_code: string;
  link_type: string;
  link_config: Record<string, any>;
}

export interface TraceNode {
  station_code: string;
  station_name: string;
  record: {
    id: string;
    lot_no_raw: string;
    lot_no_norm: number;
    data: Record<string, any>;
    created_at: string | null;
  } | null;
  items: Array<{
    id: string;
    row_no: number;
    data: Record<string, any>;
  }>;
}

export interface ValidationRuleInfo {
  id: string;
  field_name: string;
  rule_type: string;
  rule_config: Record<string, any>;
  station_id?: string | null;
}