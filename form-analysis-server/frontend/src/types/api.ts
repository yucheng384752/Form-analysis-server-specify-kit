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