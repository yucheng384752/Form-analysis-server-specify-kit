import type { DataType } from '../../types/common'

export const TENANT_STORAGE_KEY = "form_analysis_tenant_id";

export interface QueryRecord {
  id: string;
  lot_no: string;
  data_type: DataType;
  production_date?: string;
  created_at: string;
  display_name: string;

  // P1專用欄位
  product_name?: string;
  quantity?: number;
  notes?: string;

  // P2專用欄位
  slitting_machine_number?: number;
  winder_number?: number;
  winder_numbers?: number[];
  sheet_width?: number;
  thickness1?: number;
  thickness2?: number;
  thickness3?: number;
  thickness4?: number;
  thickness5?: number;
  thickness6?: number;
  thickness7?: number;
  appearance?: number;
  rough_edge?: number;
  slitting_result?: number;

  // P3專用欄位
  p3_no?: string;
  product_id?: string;
  machine_no?: string;
  mold_no?: string;
  production_lot?: number;
  source_winder?: number;
  specification?: string;
  bottom_tape_lot?: string;

  // 額外資料欄位 (來自CSV的其他欄位，包含溫度資料等)
  additional_data?: { [key: string]: any };
}

export interface QueryResponse {
  total_count: number;
  page: number;
  page_size: number;
  records: QueryRecord[];
}
