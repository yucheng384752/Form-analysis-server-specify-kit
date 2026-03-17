// src/pages/QueryPage.tsx
import React, { useState, useRef } from "react";
import { useTranslation } from "react-i18next";
import { useToast } from "../components/common/ToastContext";
import { Modal } from "../components/common/Modal";
import { AdvancedSearch, AdvancedSearchParams } from "../components/AdvancedSearch";
import { EditRecordModal } from "../components/EditRecordModal";
import "../styles/query-page.css";
import type { DataType } from "../types/common";

const TENANT_STORAGE_KEY = "form_analysis_tenant_id";

interface QueryRecord {
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

interface QueryResponse {
  total_count: number;
  page: number;
  page_size: number;
  records: QueryRecord[];
}

const normalizeMaybeNumber = (v: any): number | null => {
  if (v === null || v === undefined) return null;
  if (typeof v === 'number' && Number.isFinite(v)) return v;
  const s = String(v).trim();
  if (!s) return null;
  const n = Number(s);
  return Number.isFinite(n) ? n : null;
};

const getP2RowWinderNumber = (row: any): number | null => {
  if (!row || typeof row !== 'object') return null;
  return (
    normalizeMaybeNumber(row.winder_number) ??
    normalizeMaybeNumber(row['winder_number']) ??
    normalizeMaybeNumber(row['Winder number']) ??
    normalizeMaybeNumber(row['Winder Number'])
  );
};

const mergeP2RecordsForLotNo = (records: QueryRecord[], lotNo: string): QueryRecord[] => {
  if (!lotNo) return records;

  const isTarget = (r: QueryRecord) => r?.data_type === 'P2' && String(r?.lot_no || '') === lotNo;
  const p2Records = records.filter(isTarget);
  if (p2Records.length <= 1) return records;

  const mergedRows: any[] = [];
  for (const r of p2Records) {
    const rows = (r as any)?.additional_data?.rows;
    if (Array.isArray(rows)) {
      for (const row of rows) {
        if (row && typeof row === 'object' && !Array.isArray(row)) {
          mergedRows.push(row);
        }
      }
    }
  }

  // 依 winder_number 做穩定排序（有的就排前面，沒有就維持原順序）。
  const mergedRowsSorted = mergedRows
    .map((row, idx) => ({ row, idx, w: getP2RowWinderNumber(row) }))
    .sort((a, b) => {
      if (a.w === null && b.w === null) return a.idx - b.idx;
      if (a.w === null) return 1;
      if (b.w === null) return -1;
      if (a.w !== b.w) return a.w - b.w;
      return a.idx - b.idx;
    })
    .map(x => x.row);

  // 用第一筆 record 當 base，把 rows 合併進去；避免誤導，清掉會「每 winder 不同」的欄位。
  const base = { ...p2Records[0] };
  (base as any).winder_number = undefined;
  (base as any).slitting_machine_number = undefined;
  base.additional_data = {
    ...(base.additional_data || {}),
    rows: mergedRowsSorted,
  };

  const out: QueryRecord[] = [];
  let inserted = false;
  for (const r of records) {
    if (isTarget(r)) {
      if (!inserted) {
        out.push(base);
        inserted = true;
      }
      continue;
    }
    out.push(r);
  }
  return out;
};

export function QueryPage() {
  const { t } = useTranslation();
  const { showToast } = useToast();
  // 搜尋相關狀態
  const [searchKeyword, setSearchKeyword] = useState("");
  const [searchPerformed, setSearchPerformed] = useState(false);
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [suggestionLoading, setSuggestionLoading] = useState(false);
  
  // 進階搜尋相關狀態
  const [advancedSearchExpanded, setAdvancedSearchExpanded] = useState(false);
  const [advancedSearchParams, setAdvancedSearchParams] = useState<AdvancedSearchParams | null>(null);
  
  // 記錄列表相關狀態
  const [records, setRecords] = useState<QueryRecord[]>([]);
  const [expandedRecordId, setExpandedRecordId] = useState<string | null>(null);
  const [collapsedSections, setCollapsedSections] = useState<{ [key: string]: boolean }>({});
  const [detailRecord, setDetailRecord] = useState<QueryRecord | null>(null);
  const [editRecord, setEditRecord] = useState<QueryRecord | null>(null);
  const [tenantId, setTenantId] = useState<string>("");

  const effectiveTenantId = tenantId || window.localStorage.getItem(TENANT_STORAGE_KEY) || ''
  
  // 表格排序狀態: { 'recordId-tableType': { column: 'columnName', direction: 'asc'|'desc' } }
  const [tableSortState, setTableSortState] = useState<{ [key: string]: { column: string; direction: 'asc' | 'desc' } }>({});

  React.useEffect(() => {
    const storedTenantId = window.localStorage.getItem(TENANT_STORAGE_KEY);
    if (storedTenantId) {
      setTenantId(storedTenantId);
    }
  }, []);

  const mergeTenantHeaders = (headers?: HeadersInit): HeadersInit => {
    const tenantHeaders: Record<string, string> = effectiveTenantId ? { 'X-Tenant-Id': effectiveTenantId } : {};

    if (!headers) return tenantHeaders;
    if (headers instanceof Headers) {
      const merged = new Headers(headers);
      for (const [k, v] of Object.entries(tenantHeaders)) merged.set(k, v);
      return merged;
    }
    if (Array.isArray(headers)) {
      const mergedObj: Record<string, string> = { ...tenantHeaders };
      for (const [k, v] of headers) mergedObj[String(k)] = String(v);
      return mergedObj;
    }
    return { ...tenantHeaders, ...(headers as Record<string, string>) };
  };

  const fetchWithTenant = (input: RequestInfo | URL, init?: RequestInit) => {
    return fetch(input, {
      ...init,
      headers: mergeTenantHeaders(init?.headers),
    });
  };
  const [loading, setLoading] = useState(false);
  const [totalCount, setTotalCount] = useState(0);
  const [currentPage, setCurrentPage] = useState(1);
  const [traceabilityData, setTraceabilityData] = useState<any>(null);
  const [traceActiveTab, setTraceActiveTab] = useState<DataType>('P3');
  
  const inputRef = useRef<HTMLInputElement>(null);
  const suggestionsRef = useRef<HTMLDivElement>(null);
  const traceSectionRef = useRef<HTMLDivElement>(null);
  const pageSize = 50;

  const isLikelyProductId = (value: string): boolean => {
    const v = value.trim();
    // Product ID format: YYYYMMDD_MachineNo_MoldNo_lot (allow flexible segments after date)
    return /^\d{8}_.+_.+_.+/.test(v);
  };

  const getRowFieldValue = (row: any, keys: string[]): any => {
    for (const key of keys) {
      if (row && Object.prototype.hasOwnProperty.call(row, key)) {
        const val = row[key];
        if (val !== undefined && val !== null && val !== '') return val;
      }
    }
    return undefined;
  };

  const isNgLike = (formatted: string): boolean => {
    const v = (formatted || '').toString().trim().toUpperCase();
    return v === 'X' || v.includes('NG');
  };

  const sortRowsNgFirst = (rows: any[], fieldKeys: string[]): any[] => {
    if (!Array.isArray(rows) || rows.length <= 1) return rows;

    // stable sort
    return rows
      .map((row, idx) => ({ row, idx }))
      .sort((a, b) => {
        const aKey = fieldKeys.find(k => a.row && Object.prototype.hasOwnProperty.call(a.row, k)) || fieldKeys[0];
        const bKey = fieldKeys.find(k => b.row && Object.prototype.hasOwnProperty.call(b.row, k)) || fieldKeys[0];

        const aRaw = getRowFieldValue(a.row, fieldKeys);
        const bRaw = getRowFieldValue(b.row, fieldKeys);

        const aFmt = formatFieldValue(aKey, aRaw);
        const bFmt = formatFieldValue(bKey, bRaw);

        const aNg = isNgLike(aFmt);
        const bNg = isNgLike(bFmt);

        if (aNg !== bNg) return aNg ? -1 : 1;
        return a.idx - b.idx;
      })
      .map(x => x.row);
  };

  const normalizeTraceRecord = (type: DataType, record: any): QueryRecord | null => {
    if (!record) return null;

    const createdAt = record.created_at || record.createdAt || record.updated_at || record.updatedAt;
    const lotNo = record.lot_no || record.lotNo || record.production_lot || record.productionLot || '';
    const stableId = String(record.id || `${type}-${record.product_id || record.productId || lotNo || 'unknown'}`);

    return {
      ...(record as any),
      id: stableId,
      lot_no: String(lotNo),
      data_type: type,
      created_at: createdAt ? String(createdAt) : new Date().toISOString(),
      display_name: record.display_name || record.displayName || '',
      additional_data: record.additional_data || record.additionalData || record.extras || record.data || record.additional || {},
    };
  };

  const scrollToTrace = () => {
    setTimeout(() => {
      traceSectionRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, 50);
  };

  // 輔助函數：格式化欄位值（處理多種 boolean 轉換和日期轉換）
  const formatFieldValue = (header: string, value: any): string => {
    // 空值處理
    if (value === null || value === undefined) return '-';

    // 避免直接渲染物件導致 [object Object]
    if (Array.isArray(value)) {
      // 陣列內容可能是物件或原始值
      const parts = value
        .map((v) => {
          if (v === null || v === undefined) return '';
          if (typeof v === 'object') {
            try {
              return JSON.stringify(v);
            } catch {
              return String(v);
            }
          }
          return String(v);
        })
        .filter((s) => s.trim().length > 0);
      return parts.length ? parts.join(', ') : '-';
    }

    if (typeof value === 'object') {
      // 常見包裝格式（避免直接顯示 [object Object]）
      const obj: any = value;
      for (const k of ['value', 'raw', 'text', 'display', 'name']) {
        const v = obj?.[k];
        if (v !== null && v !== undefined && typeof v !== 'object') {
          return String(v);
        }
      }
      try {
        return JSON.stringify(value);
      } catch {
        return String(value);
      }
    }
    // 10Po 欄位的 boolean 轉換
    if (header === '10Po' || header === '10PO') {
      if (typeof value === 'boolean') {
        return value ? 'V' : 'X';
      }
      if (value === 1 || value === '1' || value === true) {
        return 'V';
      }
      if (value === 0 || value === '0' || value === false) {
        return 'X';
      }
    }

    // P3 欄位的 boolean 轉換: shift, iron, mold, rubber wheel, finish
    const p3BooleanFields = ['shift', 'iron', 'mold', 'rubber wheel', 'finish', 'Shift', 'Iron', 'Mold', 'Rubber wheel', 'Finish'];
    if (p3BooleanFields.includes(header)) {
      if (typeof value === 'boolean') {
        return value ? 'V' : 'X';
      }
      if (value === 1 || value === '1' || value === true) {
        return 'V';
      }
      if (value === 0 || value === '0' || value === false) {
        return 'X';
      }
    }

    // P2 欄位的 boolean 轉換: appearance, rough edge, striped results
    const p2BooleanFields = ['appearance', 'rough edge', 'striped results', 'Appearance', 'Rough edge', 'Striped results', '外觀', '毛邊', '分條結果'];
    if (p2BooleanFields.includes(header)) {
      if (typeof value === 'boolean') {
        return value ? 'V' : 'X';
      }
      if (value === 1 || value === '1' || value === true) {
        return 'V';
      }
      if (value === 0 || value === '0' || value === false) {
        return 'X';
      }
    }

    // P2 分條時間民國年轉西元年
    if (header === '分條時間' || header === 'slitting time') {
      if (value && typeof value === 'string') {
        // 嘗試解析民國年格式: YYY/MM/DD 或 YYY-MM-DD
        const rocMatch = value.match(/^(\d{3})[\/-](\d{1,2})[\/-](\d{1,2})/);
        if (rocMatch) {
          const rocYear = parseInt(rocMatch[1]);
          const month = rocMatch[2].padStart(2, '0');
          const day = rocMatch[3].padStart(2, '0');
          const adYear = rocYear + 1911;
          return `${adYear}-${month}-${day}`;
        }
      }
    }

    // P2 分條機編號轉換顯示名稱
    if (header === 'Slitting machine' || header === 'slitting machine' || header === 'slitting_machine_number') {
      if (value === 1 || value === '1') {
        return t('query.p2.slittingMachineDisplay.points1');
      }
      if (value === 2 || value === '2') {
        return t('query.p2.slittingMachineDisplay.points2');
      }
    }

    // P1 Production Date 格式處理（修正 250,717 這類數字顯示問題）
    if (header === 'Production Date' || header === 'production_date') {
      if (!value) return '-';
      
      // 如果是數字（可能是 Excel 序列值或 YYMMDD 格式）
      if (typeof value === 'number') {
        // 檢查是否為 YYMMDD 格式 (6位數字)
        const numStr = value.toString();
        if (numStr.length === 6) {
          // 250717 -> 2025-07-17
          const year = '20' + numStr.substring(0, 2);
          const month = numStr.substring(2, 4);
          const day = numStr.substring(4, 6);
          return `${year}-${month}-${day}`;
        }
      }
      
      // 如果是字串格式
      if (typeof value === 'string') {
        // 如果已經是 YYYY-MM-DD 格式，直接返回
        if (/^\d{4}-\d{2}-\d{2}$/.test(value)) {
          return value;
        }
        
        // 如果是 YYMMDD 格式字串 (6位數字)
        if (/^\d{6}$/.test(value)) {
          const year = '20' + value.substring(0, 2);
          const month = value.substring(2, 4);
          const day = value.substring(4, 6);
          return `${year}-${month}-${day}`;
        }
        
        // 如果是 YYYY/MM/DD 或 YY/MM/DD 格式
        if (value.includes('/')) {
          const parts = value.split('/');
          if (parts.length === 3) {
            let year = parts[0];
            const month = parts[1].padStart(2, '0');
            const day = parts[2].padStart(2, '0');
            
            // 如果是兩位年份，補上 20
            if (year.length === 2) {
              year = '20' + year;
            }
            return `${year}-${month}-${day}`;
          }
        }
      }
    }
    
    // 數字格式化（排除日期欄位）
    if (typeof value === 'number') {
      return value.toLocaleString();
    }
    
    // 空字串處理
    return value === '' ? '-' : String(value);
  };

  const formatP2SlittingTimeValue = (rawValue: any, productionDate?: any): string => {
    if (rawValue === null || rawValue === undefined) return '-';
    if (productionDate && typeof rawValue === 'string') {
      const v = rawValue.trim();
      const timeOnly = /^\d{1,2}:\d{2}(:\d{2})?$/.test(v);
      const hasLeadingDate =
        /^\d{3}[\/-]\d{1,2}[\/-]\d{1,2}/.test(v) ||
        /^\d{4}-\d{2}-\d{2}/.test(v);
      if (timeOnly && !hasLeadingDate) {
        return `${formatFieldValue('production_date', productionDate)} ${v}`;
      }
    }
    return formatFieldValue('分條時間', rawValue);
  };

  const getP2SlittingTimeForSummary = (record: QueryRecord): string | null => {
    const additional = (record.additional_data || {}) as any;
    const rows = Array.isArray(additional.rows) ? (additional.rows as any[]) : [];
    for (const row of rows) {
      if (!row || typeof row !== 'object') continue;
      const rawValue = row['分條時間'] ?? row['slitting time'] ?? row['slitting_time'];
      if (rawValue === null || rawValue === undefined || String(rawValue).trim() === '') continue;
      const formatted = formatP2SlittingTimeValue(rawValue, record.production_date);
      return formatted === '-' ? null : formatted;
    }
    return null;
  };

  // 搜尋記錄 (支援基本搜尋和進階搜尋)
  const searchRecords = async (search: string, page: number = 1, advancedParams?: AdvancedSearchParams) => {
    setLoading(true);
    // 每次搜尋預設收合（避免沿用上一次展開狀態）
    setExpandedRecordId(null);
    setCollapsedSections({});
    try {
      let apiUrl = '/api/v2/query/records';

      const isLikelyExactLotNo = (value: string): boolean => {
        // Typical lot pattern in this project: 6-8 digits + '_' + 2 digits (e.g. 2507173_02)
        // Keep this strict so fuzzy search won't accidentally trigger P2 merge mode.
        return /^\d{6,8}_\d{2}$/.test(value.trim());
      };

      const lotNoForMerge = (advancedParams?.lot_no || search || '').trim();
      const canMergeP2LotNo =
        isLikelyExactLotNo(lotNoForMerge) &&
        (!advancedParams || !advancedParams.winder_number) &&
        (!advancedParams?.data_type || advancedParams.data_type === 'P2');

      // lot_no 查詢下，P2 可能會是一個 lot 多筆 records（每個 winder 一筆）。
      // 為了讓前端能顯示「20 筆 items 明細」，這裡把 page_size 拉到上限並固定抓第 1 頁。
      const effectivePage = canMergeP2LotNo ? 1 : page;
      const effectivePageSize = canMergeP2LotNo ? (advancedParams ? 200 : 100) : pageSize;

      const params = new URLSearchParams({
        page: effectivePage.toString(),
        page_size: effectivePageSize.toString()
      });
      
      // 優先使用進階搜尋參數
      if (advancedParams) {
        apiUrl = '/api/v2/query/records/dynamic';

        type DynamicFilter = { field: string; op: string; value: any };

        const filters: DynamicFilter[] = [];
        if (advancedParams.lot_no) {
          filters.push({ field: 'lot_no', op: 'contains', value: advancedParams.lot_no });
        }

        const dateFrom = (advancedParams.production_date_from || '').trim();
        const dateTo = (advancedParams.production_date_to || '').trim();
        if (dateFrom && dateTo) {
          if (dateFrom === dateTo) {
            filters.push({ field: 'production_date', op: 'eq', value: dateFrom });
          } else {
            filters.push({ field: 'production_date', op: 'between', value: [dateFrom, dateTo] });
          }
        }

        if (advancedParams.machine_no && advancedParams.machine_no.length) {
          filters.push({ field: 'machine_no', op: 'all_of', value: advancedParams.machine_no });
        }
        if (advancedParams.mold_no && advancedParams.mold_no.length) {
          filters.push({ field: 'mold_no', op: 'all_of', value: advancedParams.mold_no });
        }
        if (advancedParams.product_id) {
          filters.push({ field: 'product_id', op: 'contains', value: advancedParams.product_id });
        }
        if (advancedParams.specification && advancedParams.specification.length) {
          filters.push({ field: 'specification', op: 'all_of', value: advancedParams.specification });
        }
        if (advancedParams.material && advancedParams.material.length) {
          filters.push({ field: 'material', op: 'all_of', value: advancedParams.material });
        }
        if (advancedParams.winder_number) {
          filters.push({ field: 'winder_number', op: 'eq', value: advancedParams.winder_number });
        }
        if (advancedParams.thickness_min || advancedParams.thickness_max) {
          const a = advancedParams.thickness_min ? Number(advancedParams.thickness_min) : null;
          const b = advancedParams.thickness_max ? Number(advancedParams.thickness_max) : null;
          if (Number.isFinite(a) && Number.isFinite(b)) {
            filters.push({ field: 'thickness', op: 'between', value: [a, b] });
          } else if (Number.isFinite(a)) {
            filters.push({ field: 'thickness', op: 'between', value: [a, a] });
          } else if (Number.isFinite(b)) {
            filters.push({ field: 'thickness', op: 'between', value: [b, b] });
          }
        }

        const dataTypeRaw = (advancedParams.data_type || '').trim().toUpperCase();
        const dataType = (dataTypeRaw === 'P1' || dataTypeRaw === 'P2' || dataTypeRaw === 'P3') ? dataTypeRaw : undefined;

        const response = await fetchWithTenant(apiUrl, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            data_type: dataType,
            filters,
            page: effectivePage,
            page_size: effectivePageSize,
          }),
        });

        if (response.ok) {
          const data: QueryResponse = await response.json();

          if (canMergeP2LotNo) {
            const merged = mergeP2RecordsForLotNo(data.records, lotNoForMerge);
            setRecords(merged);
            setTotalCount(merged.length);
            setCurrentPage(1);
          } else {
            setRecords(data.records);
            setTotalCount(data.total_count);
            setCurrentPage(data.page);
          }
          setSearchPerformed(true);
        } else {
          console.error('Error searching records:', response.status);
        }

        return;
      } else if (search) {
        params.append('lot_no', search);
      }
      
      const response = await fetchWithTenant(`${apiUrl}?${params}`);
      if (response.ok) {
        const data: QueryResponse = await response.json();

        if (canMergeP2LotNo) {
          const merged = mergeP2RecordsForLotNo(data.records, lotNoForMerge);
          setRecords(merged);
          setTotalCount(merged.length);
          setCurrentPage(1);
        } else {
          setRecords(data.records);
          setTotalCount(data.total_count);
          setCurrentPage(data.page);
        }
        setSearchPerformed(true);
      } else {
        console.error('Error searching records:', response.status);
      }
    } catch (error) {
      console.error('Error searching records:', error);
    } finally {
      setLoading(false);
    }
  };

  // 輔助函數：產生 P3 Row 的 Product ID
  const generateRowProductId = (record: QueryRecord, row: any): string => {
    const normalizeLotToken = (value: any): string => {
      if (value === null || value === undefined) return '';
      const s = String(value).trim();
      if (!s) return '';
      if (/^\d+(\.\d+)?$/.test(s)) {
        const n = Number(s);
        if (Number.isFinite(n)) return String(Math.trunc(n));
      }
      const m = s.match(/(\d{2,4})$/);
      return m ? m[1] : s;
    };

    // 1. 取得日期 (YYYYMMDD)
    let dateStr = '';
    if (record.production_date) {
      // 移除所有非數字字符
      dateStr = record.production_date.replace(/\D/g, '');
      // 確保是 8 位數 (YYYYMMDD)
      if (dateStr.length > 8) dateStr = dateStr.substring(0, 8);
    } else {
      // 如果沒有 production_date，嘗試從 created_at 取得
      const dateObj = new Date(record.created_at);
      const year = dateObj.getFullYear();
      const month = String(dateObj.getMonth() + 1).padStart(2, '0');
      const day = String(dateObj.getDate()).padStart(2, '0');
      dateStr = `${year}${month}${day}`;
    }

    // 2. 機台
    const machine = record.machine_no || row['Machine NO'] || row['Machine No'] || row['machine'] || row['Machine'] || 'Unknown';

    // 3. 模具號碼
    const mold = record.mold_no || row['Mold NO'] || row['Mold No'] || row['mold'] || row['Mold'] || 'Unknown';

    // 4. Lot (優先使用 row 中的 lot 資訊)
    const lotRaw = row['lot'] || row['Lot'] || row['production_lot'] || row['Production Lot'] || row['lot_no'] || row['Lot No'] || '0';
    const lot = normalizeLotToken(lotRaw) || '0';

    // 若後端已提供 product_id，僅在與 row 的 lot 一致時採用，避免 record-level fallback 蓋掉 row-level 值。
    const providedId = String(row['product_id'] || '').trim();
    if (providedId) {
      const suffix = providedId.split('_').pop() || '';
      if (!lot || suffix === lot) {
        return providedId;
      }
    }

    return `${dateStr}_${machine}_${mold}_${lot}`;
  };

  // 處理 P3 關聯查詢（使用規格和 winder_number 精確查詢對應的單筆 P2）
  const handleP3LinkSearch = async (record: QueryRecord, row: any, rowProductId?: string) => {
    try {
      let baseLotNo = '';
      let sourceWinder: number | null = null;
      
      // 1. 嘗試從 P3_No 解析 (最準確)
      // P3_No 格式通常為: LotNo_Winder_Batch (例如: 2503273_03_14_301)
      const p3No = row['P3_No.'] || row['P3 No.'] || row['p3_no'] || row['P3NO'];
      
      if (p3No) {
        const parts = p3No.toString().trim().split('_');
        // 假設格式至少有 3 部分: Lot_Winder_Batch 或 LotPart1_LotPart2_Winder_Batch
        if (parts.length >= 3) {
          // 倒數第二部分通常是 Winder
          const winderPart = parts[parts.length - 2];
          if (/^\d+$/.test(winderPart)) {
            sourceWinder = parseInt(winderPart, 10);
            // 剩下的前面部分是 Lot No
            baseLotNo = parts.slice(0, parts.length - 2).join('_');
            
            console.log('Parsed from P3_No:', { p3No, baseLotNo, sourceWinder });
          }
        }
      }
      
      // 2. 嘗試從 lot no 欄位解析 (使用者指定)
      // 格式: 2507173_02_17 (Lot_Part_Winder)
      if (!sourceWinder) {
        const lotNoVal = row['lot no'] || row['lot_no'] || row['Lot No'] || row['Lot No.'];
        if (lotNoVal) {
          const parts = lotNoVal.toString().trim().split('_');
          // 假設最後一部分是 Winder (例如 17)
          if (parts.length >= 3) {
            const lastPart = parts[parts.length - 1];
            if (/^\d+$/.test(lastPart)) {
              sourceWinder = parseInt(lastPart, 10);
              // 剩下的前面部分是 Base Lot No (例如 2507173_02)
              // 如果之前沒解析出 baseLotNo，就用這個
              if (!baseLotNo) {
                baseLotNo = parts.slice(0, parts.length - 1).join('_');
              }
              console.log('Parsed from lot no field:', { lotNoVal, baseLotNo, sourceWinder });
            }
          }
        }
      }

      // 3. 如果無法從 P3_No 或 lot no 解析，嘗試從 record.lot_no 和 row 數據推斷
      if (!baseLotNo || !sourceWinder) {
        // 使用記錄的 lot_no 作為基礎
        baseLotNo = record.lot_no;
        
        // 嘗試從 row 中找 winder 相關欄位
        const winderVal = row['Winder'] || row['winder'] || row['Winder No'] || row['source_winder'];
        if (winderVal && /^\d+$/.test(winderVal.toString())) {
          sourceWinder = parseInt(winderVal.toString(), 10);
        } else {
          // 如果沒有 winder 欄位，嘗試從 lot_no 解析 (舊邏輯，可能不準確)
          // 假設 lot_no 結尾是 winder (例如 2503033_01_17)
          const parts = record.lot_no.split('_');
          if (parts.length >= 3) {
             // 只有當部分夠多時才嘗試拆分，避免把 2503033_03 拆成 Lot:2503033 Winder:03
             const lastPart = parts[parts.length - 1];
             if (/^\d{1,2}$/.test(lastPart)) {
               // 這裡很危險，因為 _03 可能是批號的一部分
               // 只有當我們確定它是 winder 時才用
               // 暫時保留原值作為 LotNo，除非我們非常確定
             }
          }
        }
      }

      if (!baseLotNo) {
        showToast('error', t('query.errors.lotInfoMissing'));
        return;
      }
      
      if (!sourceWinder) {
        showToast('error', t('query.errors.winderMissing'));
        return;
      }
      
      console.log('P3 link search executing:', {
        baseLotNo,
        sourceWinder,
        message: 'Search P2 by parsed lot no + winder_number'
      });
      
      setLoading(true);
      
      // 使用新的追溯 API 獲取完整資料
      const traceResponse = await fetchWithTenant(
        `/api/traceability/winder/${encodeURIComponent(baseLotNo)}/${sourceWinder}`
      );
      
      if (!traceResponse.ok) {
        // 如果追溯 API 失敗，嘗試回退到舊的查詢方式，或者直接報錯
        // 這裡我們假設追溯 API 應該要成功，如果 404 代表真的沒資料
        if (traceResponse.status === 404) {
            showToast('error', t('query.errors.p2NotFound', { lotNo: baseLotNo, winder: sourceWinder }));
           setLoading(false);
           return;
        }
        showToast(
          'error',
          t('query.errors.traceFailedWithStatus', {
            status: traceResponse.status,
            statusText: traceResponse.statusText || String(traceResponse.status)
          })
        );
        setLoading(false);
        return;
      }
      
      const traceData = await traceResponse.json();
      
      console.log('[Traceability Debug] Backend response traceData:', traceData);
      if (traceData.p2) {
          console.log('[Traceability Debug] P2 data from backend:', traceData.p2);
          console.log('[Traceability Debug] P2 additional_data:', traceData.p2.additional_data);
          if (traceData.p2.additional_data && traceData.p2.additional_data.rows) {
              console.log('[Traceability Debug] P2 rows count:', traceData.p2.additional_data.rows.length);
          } else {
              console.warn('[Traceability Debug] P2 has no rows in additional_data');
          }
      } else {
          console.warn('[Traceability Debug] No P2 data in response');
      }

      // 轉換資料格式以符合 TraceabilityFlow 的需求
      // 建立一個新的 P3 記錄物件，並根據 row 資料更新欄位
      const p3Record = { ...record };
      
      // 如果有 rowProductId，更新 product_id
      if (rowProductId) {
        p3Record.product_id = rowProductId;
      }
      
      // 嘗試從 row 更新其他欄位，例如 production_lot (批號)
      // 檢查常見的批號欄位名稱
      const lotVal = row['lot'] || row['Lot'] || row['production_lot'] || row['Production Lot'] || row['lot_no'] || row['Lot No'];
      if (lotVal) {
         p3Record.production_lot = lotVal;
         // 同時更新 lot_no 以確保顯示一致 (視需求而定，通常 P3 的 lot_no 是指生產序號)
         // p3Record.lot_no = lotVal; 
      }

      const flowData = {
        product_id: rowProductId || record.product_id || `${baseLotNo}_${sourceWinder}`,
        p3: p3Record, // 使用更新後的 P3 記錄
        p2: traceData.p2,
        p1: traceData.p1,
        trace_complete: !!(record && traceData.p2 && traceData.p1),
        missing_links: [] as string[]
      };
      
      if (!traceData.p2) flowData.missing_links.push('P2');
      if (!traceData.p1) flowData.missing_links.push('P1');
      
      setTraceabilityData(flowData);
      setTraceActiveTab('P3');
      scrollToTrace();
      
      setLoading(false);
      
      // 滾動到搜尋結果
      setTimeout(() => {
        const searchResultsElement = document.querySelector('.data-container');
        if (searchResultsElement) {
          searchResultsElement.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
      }, 500);
      
    } catch (error: any) {
      console.error('P3 link search failed:', error);
      showToast('error', t('query.errors.searchFailedWithDetail', { detail: String(error?.message || '') || t('query.errors.unknownError') }));
      setLoading(false);
    }
  };


  // 獲取搜尋建議
  const fetchSuggestions = async (query: string) => {
    if (!query.trim() || query.trim().length < 1) {
      setSuggestions([]);
      setShowSuggestions(false);
      return;
    }

    setSuggestionLoading(true);
    try {
      const params = new URLSearchParams({
        term: query.trim(),
        limit: '10'
      });
      
      const response = await fetchWithTenant(`/api/v2/query/lots/suggestions?${params}`);
      if (response.ok) {
        const data: string[] = await response.json();
        setSuggestions(data);
        setShowSuggestions(data.length > 0);
      } else {
        console.error('Error fetching suggestions:', response.status);
        setSuggestions([]);
        setShowSuggestions(false);
      }
    } catch (error) {
      console.error('Error fetching suggestions:', error);
      setSuggestions([]);
      setShowSuggestions(false);
    } finally {
      setSuggestionLoading(false);
    }
  };

  // 處理基本搜尋
  const handleSearch = async () => {
    if (!effectiveTenantId) {
      showToast('error', t('query.noTenantWarning'));
      return;
    }

    const keyword = searchKeyword.trim();
    if (!keyword) return;

    setShowSuggestions(false);

    // 若看起來像 Product ID，直接走追溯查詢（不改動既有 lot_no 查詢流程）
    if (isLikelyProductId(keyword)) {
      try {
        setLoading(true);
        setAdvancedSearchParams(null);
        setRecords([]);
        setTotalCount(0);
        setSearchPerformed(false);

        const res = await fetchWithTenant(`/api/traceability/product/${encodeURIComponent(keyword)}`);
        if (!res.ok) {
          if (res.status === 404) {
            showToast('error', t('query.errors.productNotFound'));
            return;
          }
          const text = await res.text().catch(() => '');
          throw new Error(text || res.statusText);
        }
        const data = await res.json();
        setTraceabilityData(data);
        setTraceActiveTab('P3');
        scrollToTrace();
      } catch (e: any) {
        console.error('Product ID traceability failed:', e);
        showToast('error', t('query.errors.searchFailedWithDetail', { detail: String(e?.message || '') || t('query.errors.unknownError') }));
      } finally {
        setLoading(false);
      }
      return;
    }

    // 既有：批號(Lot No)查詢
    setTraceabilityData(null);
    setTraceActiveTab('P3');
    setAdvancedSearchParams(null); // 清除進階搜尋參數
    await searchRecords(keyword);
  };
  
  // 處理進階搜尋
  const handleAdvancedSearch = async (params: AdvancedSearchParams) => {
    if (!effectiveTenantId) {
      showToast('error', t('query.noTenantWarning'));
      return;
    }

    setAdvancedSearchParams(params);
    setSearchKeyword(''); // 清除基本搜尋關鍵字
    await searchRecords('', 1, params);
  };
  
  // 重置進階搜尋
  const handleAdvancedReset = () => {
    setAdvancedSearchParams(null);
    setRecords([]);
    setSearchPerformed(false);
    setTotalCount(0);
  };

  // 處理輸入變化
  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    setSearchKeyword(value);
    if (tenantId) fetchSuggestions(value);
  };

  // 處理建議點擊
  const handleSuggestionClick = (suggestion: string) => {
    setSearchKeyword(suggestion);
    setShowSuggestions(false);
    if (!effectiveTenantId) {
      showToast('error', t('query.noTenantWarning'));
      return;
    }
    searchRecords(suggestion);
  };

  // 處理輸入焦點
  const handleInputFocus = () => {
    if (searchKeyword.trim().length >= 1) {
      if (tenantId) fetchSuggestions(searchKeyword);
    }
  };

  // 處理輸入失焦
  const handleInputBlur = () => {
    setTimeout(() => setShowSuggestions(false), 200);
  };

  // 切換展開狀態
  const toggleExpand = (recordId: string) => {
    setExpandedRecordId(prev => prev === recordId ? null : recordId);
    // 重置收起狀態
    if (expandedRecordId !== recordId) {
      setCollapsedSections({});
    }
  };

  // 切換區塊收起狀態
  const toggleSection = (recordId: string, sectionKey: string) => {
    const key = `${recordId}-${sectionKey}`;
    setCollapsedSections(prev => ({
      ...prev,
      [key]: !prev[key]
    }));
  };

  // 判斷區塊是否收起
  const isSectionCollapsed = (recordId: string, sectionKey: string): boolean => {
    const key = `${recordId}-${sectionKey}`;
    return collapsedSections[key] || false;
  };
  
  // 表格排序處理
  const handleTableSort = (recordId: string, tableType: 'p2' | 'p3', column: string) => {
    const key = `${recordId}-${tableType}`;
    const currentSort = tableSortState[key];
    
    let newDirection: 'asc' | 'desc' = 'asc';
    if (currentSort && currentSort.column === column) {
      // 切換排序方向
      newDirection = currentSort.direction === 'asc' ? 'desc' : 'asc';
    }
    
    setTableSortState({
      ...tableSortState,
      [key]: { column, direction: newDirection }
    });
  };
  
  // 排序表格資料
  const sortTableData = (rows: any[], recordId: string, tableType: 'p2' | 'p3'): any[] => {
    const key = `${recordId}-${tableType}`;
    const sortState = tableSortState[key];
    
    if (!sortState || !rows || rows.length === 0) {
      return rows;
    }
    
    const { column, direction } = sortState;
    const multiplier = direction === 'asc' ? 1 : -1;
    
    return [...rows].sort((a, b) => {
      const isP2WinderSort = tableType === 'p2' && column === '__winder_number__';
      const aVal = isP2WinderSort ? getP2RowWinderNumber(a) : a[column];
      const bVal = isP2WinderSort ? getP2RowWinderNumber(b) : b[column];
      
      // 處理 null/undefined
      if (aVal === null || aVal === undefined) return 1;
      if (bVal === null || bVal === undefined) return -1;
      
      // 數字比較
      if (typeof aVal === 'number' && typeof bVal === 'number') {
        return (aVal - bVal) * multiplier;
      }
      
      // 字串比較
      const aStr = String(aVal).toLowerCase();
      const bStr = String(bVal).toLowerCase();
      return aStr.localeCompare(bStr) * multiplier;
    });
  };

  const renderCollapsibleSection = (
    recordId: string,
    title: string,
    sectionKey: string,
    children: React.ReactNode,
    icon: string = ""
  ) => {
    const isCollapsed = isSectionCollapsed(recordId, sectionKey);
    return (
      <div className="data-section" key={sectionKey}>
        <div className="section-header">
          <div className="section-title-wrapper">
            {icon ? <span className="section-icon">{icon}</span> : <span className="section-icon"></span>}
            <h5>{title}</h5>
          </div>
          <button className="btn-collapse" onClick={() => toggleSection(recordId, sectionKey)}>
            {isCollapsed ? t('common.expand') : t('common.collapse')}
          </button>
        </div>
        {!isCollapsed && <div className="section-content">{children}</div>}
      </div>
    );
  };

  const getFlattenedAdditionalData = (additionalData: { [key: string]: any } | undefined) => {
    if (!additionalData) return {} as { [key: string]: any };
    let displayData: { [key: string]: any } = additionalData;
    if (
      displayData &&
      (displayData as any).rows &&
      Array.isArray((displayData as any).rows) &&
      (displayData as any).rows.length > 0
    ) {
      const { rows, ...rest } = displayData as any;
      const row0 = rows[0];
      if (row0 && typeof row0 === 'object' && !Array.isArray(row0)) {
        displayData = { ...rest, ...row0 };
      } else {
        displayData = { ...rest };
      }
    }
    return displayData;
  };

  const getValueByKeyRegex = (data: { [key: string]: any }, regexes: RegExp[]): any => {
    for (const [k, v] of Object.entries(data)) {
      for (const re of regexes) {
        if (re.test(k)) return v;
      }
    }
    return undefined;
  };

  const formatCell = (value: any) => {
    if (value === null || value === undefined) return '-';
    const s = String(value).trim();
    return s === '' || s === '-' ? '-' : s;
  };

  const renderP1CheckboxGroup = (
    title: string,
    options: string[],
    selectedRaw: any
  ) => {
    const selected = selectedRaw === null || selectedRaw === undefined ? '' : String(selectedRaw).trim();
    const normalizedSelected = selected.replace(/\s+/g, '').toLowerCase();
    const matched = options.find((o) => o.replace(/\s+/g, '').toLowerCase() === normalizedSelected);
    const otherValue = matched ? '' : selected;

    return (
      <div className="p1-paper-checkbox-group">
        <div className="p1-paper-checkbox-title">{title}</div>
        <div className="p1-paper-checkbox-options">
          {options.map((o) => {
            const isChecked = !!matched && o === matched;
            return (
              <div key={o} className={`p1-paper-checkbox ${isChecked ? 'is-checked' : ''}`}>
                <span className="p1-paper-box" aria-hidden="true"></span>
                <span className="p1-paper-checkbox-label">{o}</span>
              </div>
            );
          })}
          <div className={`p1-paper-checkbox ${otherValue ? 'is-checked' : ''}`}>
            <span className="p1-paper-box" aria-hidden="true"></span>
            <span className="p1-paper-checkbox-label">{t('common.other')}</span>
            <span className="p1-paper-checkbox-other">{otherValue || ''}</span>
          </div>
        </div>
      </div>
    );
  };

  const renderP1PaperLayout = (record: QueryRecord) => {
    const data = getFlattenedAdditionalData(record.additional_data);

    // Header fields
    const specValue = getValueByKeyRegex(data, [/^specification$/i, /specification/i]) ?? record.product_name;
    const materialValue = getValueByKeyRegex(data, [/^material$/i, /material/i]);
    const startTime = getValueByKeyRegex(data, [/production\s*time.*start/i, /start\s*time/i, /\bstart\b.*time/i]);
    const endTime = getValueByKeyRegex(data, [/production\s*time.*end/i, /end\s*time/i, /\bend\b.*time/i]);

    // Extrusion temps C1..C16
    const cCols = Array.from({ length: 16 }, (_, i) => i + 1);
    const extrusionActual = cCols.map((i) =>
      getValueByKeyRegex(data, [new RegExp(`^actual\\s*temp.*c${i}\\b`, 'i'), new RegExp(`^actual[_\\s]*temp.*c${i}\\b`, 'i')])
    );
    const extrusionSet = cCols.map((i) =>
      getValueByKeyRegex(data, [new RegExp(`^set\\s*temp.*c${i}\\b`, 'i'), new RegExp(`^set[_\\s]*temp.*c${i}\\b`, 'i')])
    );

    // Dryer buckets A/B/C
    const dryerCols = ['A', 'B', 'C'] as const;
    const dryerActual = dryerCols.map((b) =>
      getValueByKeyRegex(data, [new RegExp(`^actual\\s*temp.*${b}.*bucket`, 'i'), new RegExp(`^actual[_\\s]*temp.*${b}.*bucket`, 'i')])
    );
    const dryerSet = dryerCols.map((b) =>
      getValueByKeyRegex(data, [new RegExp(`^set\\s*temp.*${b}.*bucket`, 'i'), new RegExp(`^set[_\\s]*temp.*${b}.*bucket`, 'i')])
    );

    // Extension wheel temps (Top/Mid/Bottom) -> (A/B/C)
    const extCols = [
      { key: 'Top', label: t('query.p1.paper.extWheel.top') },
      { key: 'Mid', label: t('query.p1.paper.extWheel.mid') },
      { key: 'Bottom', label: t('query.p1.paper.extWheel.bottom') },
    ] as const;
    const extActual = extCols.map((c) =>
      getValueByKeyRegex(data, [new RegExp(`^actual\\s*temp.*${c.key}`, 'i'), new RegExp(`^actual[_\\s]*temp.*${c.key}`, 'i')])
    );
    const extSet = extCols.map((c) =>
      getValueByKeyRegex(data, [new RegExp(`^set\\s*temp.*${c.key}`, 'i'), new RegExp(`^set[_\\s]*temp.*${c.key}`, 'i')])
    );

    // Production params (exclude 成品資料：Semi-finished/Weight)
    const params = [
      {
        label: t('query.p1.paper.params.lineSpeed'),
        value: getValueByKeyRegex(data, [/^line\s*speed/i, /^line_speed/i]),
        unit: 'M/min',
      },
      {
        label: t('query.p1.paper.params.screwPressure'),
        value: getValueByKeyRegex(data, [/^screw\s*pressure/i, /^screw_pressure/i]),
        unit: 'psi',
      },
      {
        label: t('query.p1.paper.params.screwOutput'),
        value: getValueByKeyRegex(data, [/^screw\s*output/i, /^screw_output/i]),
        unit: '%',
      },
      {
        label: t('query.p1.paper.params.leftPadThickness'),
        value: getValueByKeyRegex(data, [/^left\s*pad\s*thickness/i, /^left_pad_thickness/i]),
        unit: 'mm',
      },
      {
        label: t('query.p1.paper.params.rightPadThickness'),
        value: getValueByKeyRegex(data, [/^right\s*pad\s*thickness/i, /^right_pad_thickness/i]),
        unit: 'mm',
      },
      {
        label: t('query.p1.paper.params.current'),
        value: getValueByKeyRegex(data, [/^current\s*\(a\)/i, /^current\(a\)/i, /^current$/i]),
        unit: 'A',
      },
      {
        label: t('query.p1.paper.params.extruderSpeed'),
        value: getValueByKeyRegex(data, [/^extruder\s*speed/i, /^extruder_speed/i]),
        unit: 'rpm',
      },
      {
        label: t('query.p1.paper.params.quantitativePressure'),
        value: getValueByKeyRegex(data, [/^quantitative\s*pressure/i, /^quantitative_pressure/i]),
        unit: 'psi',
      },
      {
        label: t('query.p1.paper.params.quantitativeOutput'),
        value: getValueByKeyRegex(data, [/^quantitative\s*output/i, /^quantitative_output/i]),
        unit: '%',
      },
      {
        label: t('query.p1.paper.params.frame'),
        value: getValueByKeyRegex(data, [/^frame/i, /^carriage/i]),
        unit: 'cm',
      },
      {
        label: t('query.p1.paper.params.filterPressure'),
        value: getValueByKeyRegex(data, [/^filter\s*pressure/i, /^filter_pressure/i]),
        unit: 'psi',
      },
    ];

    return (
      <div className="p1-paper">
        <div className="p1-paper-header">
          <div className="p1-paper-header-item">
            <div className="p1-paper-header-label">{t('query.fields.productionDate')}</div>
            <div className="p1-paper-header-value">{record.production_date ? formatFieldValue('production_date', record.production_date) : '-'}</div>
          </div>
          <div className="p1-paper-header-item">
            <div className="p1-paper-header-label">{t('query.fields.lotNo')}</div>
            <div className="p1-paper-header-value">{record.lot_no}</div>
          </div>
          <div className="p1-paper-header-item">
            <div className="p1-paper-header-label">{t('query.p1.paper.productionTimeStart')}</div>
            <div className="p1-paper-header-value">{formatCell(startTime)}</div>
          </div>
          <div className="p1-paper-header-item">
            <div className="p1-paper-header-label">{t('query.p1.paper.productionTimeEnd')}</div>
            <div className="p1-paper-header-value">{formatCell(endTime)}</div>
          </div>
        </div>

        <div className="p1-paper-header">
          {renderP1CheckboxGroup(t('query.p1.paper.specification'), ['0.30mm','0.32mm','0.33mm','0.35mm','0.40mm','0.44mm','0.45mm','0.50mm','0.60mm'], specValue)}
          {renderP1CheckboxGroup(t('query.p1.paper.material'), ['H2','H8','H5'], materialValue)}
        </div>

        {renderCollapsibleSection(
          record.id,
          t('query.sections.extrusionConditions'),
          'p1_extrusion_paper',
          <div className="table-container">
            <table className="p1-paper-table">
              <thead>
                <tr>
                  <th></th>
                  {cCols.map((i) => (
                    <th key={i}>C{i}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                <tr>
                  <th>{t('query.p1.paper.actualTemp')}</th>
                  {extrusionActual.map((v, idx) => (
                    <td key={idx}>{formatCell(v)}</td>
                  ))}
                </tr>
                <tr>
                  <th>{t('query.p1.paper.setTemp')}</th>
                  {extrusionSet.map((v, idx) => (
                    <td key={idx}>{formatCell(v)}</td>
                  ))}
                </tr>
              </tbody>
            </table>
          </div>
        )}

        {renderCollapsibleSection(
          record.id,
          t('query.p1.paper.sections.dryerTemps'),
          'p1_dryer_paper',
          <div className="table-container">
            <table className="p1-paper-table">
              <thead>
                <tr>
                  <th></th>
                  <th>A</th>
                  <th>B</th>
                  <th>C</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <th>{t('query.p1.paper.actualTemp')}</th>
                  {dryerActual.map((v, idx) => (
                    <td key={idx}>{formatCell(v)}</td>
                  ))}
                </tr>
                <tr>
                  <th>{t('query.p1.paper.setTemp')}</th>
                  {dryerSet.map((v, idx) => (
                    <td key={idx}>{formatCell(v)}</td>
                  ))}
                </tr>
              </tbody>
            </table>
          </div>
        )}

        {renderCollapsibleSection(
          record.id,
          t('query.p1.paper.sections.extWheelTemps'),
          'p1_extwheel_paper',
          <div className="table-container">
            <table className="p1-paper-table">
              <thead>
                <tr>
                  <th></th>
                  {extCols.map((c) => (
                    <th key={c.key}>{c.label}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                <tr>
                  <th>{t('query.p1.paper.actualTemp')}</th>
                  {extActual.map((v, idx) => (
                    <td key={idx}>{formatCell(v)}</td>
                  ))}
                </tr>
                <tr>
                  <th>{t('query.p1.paper.setTemp')}</th>
                  {extSet.map((v, idx) => (
                    <td key={idx}>{formatCell(v)}</td>
                  ))}
                </tr>
              </tbody>
            </table>
          </div>
        )}

        {renderCollapsibleSection(
          record.id,
          t('query.p1.paper.sections.productionParams'),
          'p1_params_paper',
          <div className="table-container">
            <table className="p1-paper-table p1-paper-table-params">
              <thead>
                <tr>
                  <th>{t('query.p1.paper.param')}</th>
                  <th>{t('query.p1.paper.value')}</th>
                  <th>{t('query.p1.paper.unit')}</th>
                </tr>
              </thead>
              <tbody>
                {params.map((p) => (
                  <tr key={p.label}>
                    <td>{p.label}</td>
                    <td>{formatCell(p.value)}</td>
                    <td>{p.unit}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    );
  };

  // 渲染P1展開內容
  const renderP1ExpandedContent = (record: QueryRecord) => {
    if (!record.additional_data) {
      return <p className="no-data">{t('query.noExtraCsvData')}</p>;
    }

    return <div className="grouped-data-container">{renderP1PaperLayout(record)}</div>;
  };

  // 渲染P2展開內容
  const renderP2ExpandedContent = (record: QueryRecord) => {
    if (!record.additional_data) {
      return <p className="no-data">{t('query.noExtraCsvData')}</p>;
    }

    // 檢查是否為 rows 陣列結構
    const rows = record.additional_data.rows || [];
    const sortedRows = sortRowsNgFirst(rows, ['striped results', 'Striped results', '分條結果']);
    // 應用使用者排序
    const displayRows = sortTableData(sortedRows, record.id, 'p2');
    const hasRows = Array.isArray(rows) && rows.length > 0;
    const p2Headers = hasRows
      ? Object.keys(rows[0]).filter((k) => {
          const nk = k.toLowerCase().replace(/[\s_]/g, '');
          return nk !== 'windernumber';
        })
      : [];
    
    // 取得排序狀態
    const sortState = tableSortState[`${record.id}-p2`];

    return (
      <div className="grouped-data-container">
        {/* 基本資料區塊已移除 */}
        
        {hasRows && (
          <div className="data-section">
            <div className="section-header">
              <div className="section-title-wrapper">
                <span className="section-icon"></span>
                <h5>{t('query.sections.inspectionData')}</h5>
                <span className="field-count-badge">{t('query.units.items', { count: rows.length })}</span>
              </div>
              <button
                className="btn-collapse"
                onClick={() => toggleSection(record.id, 'rows_data')}
              >
                {isSectionCollapsed(record.id, 'rows_data') ? t('common.expand') : t('common.collapse')}
              </button>
            </div>
            {!isSectionCollapsed(record.id, 'rows_data') && (
              <div className="section-content">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th
                        onClick={() => handleTableSort(record.id, 'p2', '__winder_number__')}
                        style={{ cursor: 'pointer', userSelect: 'none' }}
                        title={t('query.tableHeaders.clickToSort')}
                      >
                        {t('query.tableHeaders.winder')}
                        {sortState && sortState.column === '__winder_number__' && (
                          <span style={{ marginLeft: '4px' }}>
                            {sortState.direction === 'asc' ? '▲' : '▼'}
                          </span>
                        )}
                      </th>
                      {p2Headers.map(key => (
                        <th 
                          key={key} 
                          onClick={() => handleTableSort(record.id, 'p2', key)}
                          style={{ cursor: 'pointer', userSelect: 'none' }}
                          title={t('query.tableHeaders.clickToSort')}
                        >
                          {key}
                          {sortState && sortState.column === key && (
                            <span style={{ marginLeft: '4px' }}>
                              {sortState.direction === 'asc' ? '▲' : '▼'}
                            </span>
                          )}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {displayRows.map((row: any, idx: number) => (
                      <tr key={idx}>
                        <td>
                          {(() => {
                            const w = getP2RowWinderNumber(row)
                            if (w == null) return '-'
                            return String(w)
                          })()}
                        </td>
                        {p2Headers.map((header: string, vidx: number) => {
                          const rawValue = row?.[header];

                          // P2 分條時間：若只有時間（HH:MM 或 HH:MM:SS），補上本筆 record 的 production_date。
                          if (
                            (header === '分條時間' || header === 'slitting time') &&
                            record.production_date &&
                            typeof rawValue === 'string'
                          ) {
                            const v = rawValue.trim();
                            const timeOnly = /^\d{1,2}:\d{2}(:\d{2})?$/.test(v);
                            const hasLeadingDate = /^\d{3}[\/-]\d{1,2}[\/-]\d{1,2}/.test(v) || /^\d{4}-\d{2}-\d{2}/.test(v);
                            if (timeOnly && !hasLeadingDate) {
                              return (
                                <td key={vidx}>
                                  {`${formatFieldValue('production_date', record.production_date)} ${v}`}
                                </td>
                              );
                            }
                          }

                          return (
                            <td key={vidx}>
                              {formatFieldValue(header, rawValue)}
                            </td>
                          );
                        })}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}
      </div>
    );
  };

  // 渲染P3展開內容
  const renderP3ExpandedContent = (record: QueryRecord) => {
    if (!record.additional_data) {
      return <p className="no-data">{t('query.noExtraCsvData')}</p>;
    }

    // 檢查是否有 rows 陣列
    const rows = record.additional_data.rows || [];
    const sortedRows = sortRowsNgFirst(rows, ['Finish', 'finish']);
    // 應用使用者排序
    const displayRows = sortTableData(sortedRows, record.id, 'p3');
    const rowCount = Array.isArray(rows) ? rows.length : 0;
    
    // 取得排序狀態
    const sortState = tableSortState[`${record.id}-p3`];

    return (
      <div className="grouped-data-container">
        <div className="p3-header">
          <div className="p3-badges">
            <span className="badge badge-primary">{t('query.fields.lotNo')}: {record.lot_no}</span>
            <span className="badge badge-success">{t('query.stats.checkCount')}: {t('query.units.items', { count: rowCount })}</span>
          </div>
          <div className="p3-stats">
            <div className="stat-item">
              <span className="stat-label">{t('query.stats.originalCount')}:</span>
              <span className="stat-value">{rowCount}</span>
            </div>
            <div className="stat-item">
              <span className="stat-label">{t('query.stats.validCount')}:</span>
              <span className="stat-value">{rowCount}</span>
            </div>
          </div>
        </div>

        {/* 基本資料區塊已移除 */}
        
        {/* 渲染檢查項目表格 */}
        {Array.isArray(rows) && rows.length > 0 && (
          <div className="data-section" key="check_items">
            <div className="section-header">
              <div className="section-title-wrapper">
                <span className="section-icon"></span>
                <h5>{t('query.sections.checkItemsDetail')}</h5>
                <span className="field-count-badge">{t('query.units.items', { count: rows.length })}</span>
              </div>
              <button
                className="btn-collapse"
                onClick={() => toggleSection(record.id, 'check_items')}
              >
                {collapsedSections[`${record.id}-check_items`] ? '▼' : '▲'}
              </button>
            </div>
            {!collapsedSections[`${record.id}-check_items`] && (
              <div className="section-content">
                <div className="table-container">
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th className="action-column">{t('query.tableHeaders.linkSearch')}</th>
                        <th 
                          onClick={() => handleTableSort(record.id, 'p3', 'product_id')}
                          style={{ cursor: 'pointer', userSelect: 'none' }}
                          title={t('query.tableHeaders.clickToSort')}
                        >
                          {t('query.fields.productId')}
                          {sortState && sortState.column === 'product_id' && (
                            <span style={{ marginLeft: '4px' }}>
                              {sortState.direction === 'asc' ? '▲' : '▼'}
                            </span>
                          )}
                        </th>
                        {Object.keys(rows[0]).filter(h => h !== 'product_id').map(header => (
                          <th 
                            key={header}
                            onClick={() => handleTableSort(record.id, 'p3', header)}
                            style={{ cursor: 'pointer', userSelect: 'none' }}
                            title={t('query.tableHeaders.clickToSort')}
                          >
                            {header}
                            {sortState && sortState.column === header && (
                              <span style={{ marginLeft: '4px' }}>
                                {sortState.direction === 'asc' ? '▲' : '▼'}
                              </span>
                            )}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {displayRows.map((row: any, idx: number) => {
                        const rowProductId = generateRowProductId(record, row);
                        return (
                          <tr key={idx}>
                            <td className="action-column">
                              <button
                                className="btn-link-search"
                                title={t('query.actions.searchLinkedDataHint')}
                                onClick={() => handleP3LinkSearch(record, row, rowProductId)}
                              >
                                {t('query.actions.linkSearch')}
                              </button>
                            </td>
                            <td className="product-id-cell" title={rowProductId}>
                              {rowProductId}
                            </td>
                            {Object.keys(rows[0]).filter(h => h !== 'product_id').map(header => (
                              <td key={header}>
                                {formatFieldValue(header, row[header])}
                              </td>
                            ))}
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    );
  };

  // 根據資料類型渲染展開內容
  const renderExpandedContent = (record: QueryRecord) => {
    switch (record.data_type) {
      case 'P1':
        return renderP1ExpandedContent(record);
      case 'P2':
        return renderP2ExpandedContent(record);
      case 'P3':
        return renderP3ExpandedContent(record);
      default:
        return <p className="no-data">{t('query.errors.unknownDataType')}</p>;
    }
  };

  // 清除搜尋
  const handleClear = () => {
    setSearchKeyword('');
    setSearchPerformed(false);
    setRecords([]);
    setTotalCount(0);
    setCurrentPage(1);
    setExpandedRecordId(null);
    setCollapsedSections({});
    setShowSuggestions(false);
    setSuggestions([]);
    setTraceabilityData(null);
    setTraceActiveTab('P3');
  };

  // 渲染額外資料欄位
  const renderAdditionalData = (additionalData: { [key: string]: any } | undefined) => {
    if (!additionalData || Object.keys(additionalData).length === 0) {
      return null;
    }

    // 檢查是否有 rows 陣列 (P3 資料格式)
    if (additionalData.rows && Array.isArray(additionalData.rows) && additionalData.rows.length > 0) {
      const rows = additionalData.rows;
      const headers = Object.keys(rows[0]);

      return (
        <div className="additional-data-section">
          <div className="section-title">{t('query.sections.checkItemsDetail')}</div>
          <div className="table-container">
            <table className="data-table">
              <thead>
                <tr>
                  {headers.map(header => (
                    <th key={header}>{header}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((row: any, idx: number) => (
                  <tr key={idx}>
                    {headers.map(header => (
                      <td key={header}>
                        {formatFieldValue(header, row[header])}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      );
    }

    // 一般鍵值對資料顯示 - 移除 "additional-data-section" 區塊，直接返回 null
    // 根據使用者需求：移除前端的"additional-data-section"區塊
    return null;
  };

  // 渲染P1詳細資料
  const renderP1Details = (record: QueryRecord) => {
    return (
      <div className="detail-grid" style={{ gridColumn: '1 / -1' }}>
        {renderP1PaperLayout(record)}
      </div>
    );
  };

  // 渲染P2詳細資料
  const renderP2Details = (record: QueryRecord) => {
    console.log('[Traceability Debug] Rendering P2 details for record:', record);
    
    // 準備要顯示的額外資料
    let displayData: { [key: string]: any } = {};
    
    // 1. 先加入標準欄位
    const standardFields: Array<{ label: string; value: any }> = [
      { label: t('query.p2.fields.slittingMachine'), value: record.slitting_machine_number },
      { label: t('query.p2.fields.winderMachine'), value: record.winder_number },
      { label: t('query.p2.fields.sheetWidth'), value: record.sheet_width },
      { label: t('query.p2.fields.thickness1'), value: record.thickness1 },
      { label: t('query.p2.fields.thickness2'), value: record.thickness2 },
      { label: t('query.p2.fields.thickness3'), value: record.thickness3 },
      { label: t('query.p2.fields.thickness4'), value: record.thickness4 },
      { label: t('query.p2.fields.thickness5'), value: record.thickness5 },
      { label: t('query.p2.fields.thickness6'), value: record.thickness6 },
      { label: t('query.p2.fields.thickness7'), value: record.thickness7 },
      { label: t('query.p2.fields.appearance'), value: record.appearance },
      { label: t('query.p2.fields.roughEdge'), value: record.rough_edge },
      { label: t('query.p2.fields.slittingResult'), value: record.slitting_result },
    ];

    for (const f of standardFields) {
      if (f.value !== undefined && f.value !== null) {
        displayData[f.label] = f.value;
      }
    }

    // 2. 合併額外資料
    // P2 的細項通常在 additional_data.rows（多筆 items）。
    // - 若只有 1 筆：直接展開成 Grid（像 P1 一樣）
    // - 若多筆：Grid 顯示 record-level 欄位，並在下方顯示明細表
    const additional = (record.additional_data || {}) as any;
    const rows = Array.isArray(additional.rows) ? (additional.rows as any[]) : [];
    const { rows: _rowsIgnored, ...additionalWithoutRows } = additional || {};

    if (rows.length === 1 && rows[0] && typeof rows[0] === 'object' && !Array.isArray(rows[0])) {
      displayData = { ...displayData, ...additionalWithoutRows, ...rows[0] };
    } else {
      displayData = { ...displayData, ...additionalWithoutRows };
    }

    const hasItemRows = rows.length > 1;
    const sortedRows = hasItemRows ? sortRowsNgFirst(rows, ['striped results', 'Striped results', '分條結果']) : rows;
    const rowHeaders = hasItemRows && rows[0] && typeof rows[0] === 'object' && !Array.isArray(rows[0])
      ? Object.keys(rows[0])
      : [];

    return (
      <div className="detail-grid">
        <div className="detail-row">
          <strong>{t('query.fields.lotNo')}:</strong>
          <span>{record.lot_no}</span>
        </div>
        {Array.isArray((record as any).winder_numbers) && (record as any).winder_numbers.length > 0 && (
          <div className="detail-row">
          <strong>符合的收卷機（Winder）：</strong>
            <span>{(record as any).winder_numbers.join(', ')}</span>
          </div>
        )}
        <div className="detail-row">
          <strong>{t('query.fields.createdAt')}:</strong>
          <span>{new Date(record.created_at).toLocaleString()}</span>
        </div>
        
        {/* 直接顯示合併後的 displayData，不使用 renderAdditionalData (因為已被禁用) */}
        {Object.entries(displayData).map(([key, value]) => (
            <div key={key} className="detail-row">
              <strong>{key}：</strong>
              <span>{formatFieldValue(key, value)}</span>
            </div>
        ))}

        {hasItemRows && (
          <div className="additional-data-section" style={{ gridColumn: '1 / -1' }}>
            <div className="section-title">{t('query.sections.checkItemsDetail')}</div>
            <div className="table-container">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>#</th>
                    {rowHeaders.map((h) => (
                      <th key={h}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {sortedRows.map((row: any, idx: number) => (
                    <tr key={idx}>
                      <td>{idx + 1}</td>
                      {rowHeaders.map((header: string, vidx: number) => {
                        const rawValue = row?.[header];

                        // P2 分條時間：若只有時間（HH:MM 或 HH:MM:SS），補上本筆 record 的 production_date。
                        if (
                          (header === '分條時間' || header === 'slitting time') &&
                          record.production_date &&
                          typeof rawValue === 'string'
                        ) {
                          const v = rawValue.trim();
                          const timeOnly = /^\d{1,2}:\d{2}(:\d{2})?$/.test(v);
                          const hasLeadingDate = /^\d{3}[\/-]\d{1,2}[\/-]\d{1,2}/.test(v) || /^\d{4}-\d{2}-\d{2}/.test(v);
                          if (timeOnly && !hasLeadingDate) {
                            return (
                              <td key={vidx}>
                                {`${formatFieldValue('production_date', record.production_date)} ${v}`}
                              </td>
                            );
                          }
                        }

                        return (
                          <td key={vidx}>{formatFieldValue(header, rawValue)}</td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    );
  };

  // 渲染P3詳細資料
  const renderP3Details = (record: QueryRecord) => {
    // 準備要顯示的額外資料
    let displayData = record.additional_data || {};

    // 如果 P3 資料包含 rows 且只有一筆，提取出來以 Grid 方式顯示 (像 P1/P2 一樣)
    // 這樣可以顯示單個 row 的所有細項，而不是顯示一個單行的表格
    if (displayData.rows && 
        Array.isArray(displayData.rows) && 
        displayData.rows.length === 1) {
      // 移除 rows，並合併第一筆 row 的資料
      const { rows, ...rest } = displayData;
      displayData = { ...rest, ...rows[0] };
    }

    return (
      <div className="detail-grid">
        <div className="detail-row">
          <strong>{t('query.fields.lotNo')}:</strong>
          <span>{record.lot_no}</span>
        </div>
        <div className="detail-row">
          <strong>{t('query.p3.fields.p3No')}:</strong>
          <span>{record.p3_no}</span>
        </div>
        <div className="detail-row">
          <strong>{t('query.fields.productId')}:</strong>
          <span>{record.product_id || '-'}</span>
        </div>
        
        <div className="detail-row">
          <strong>{t('query.fields.machineNo')}:</strong>
          <span>{record.machine_no || '-'}</span>
        </div>
        <div className="detail-row">
          <strong>{t('query.fields.moldNo')}:</strong>
          <span>{record.mold_no || '-'}</span>
        </div>
        <div className="detail-row">
          <strong>{t('query.fields.specification')}:</strong>
          <span>{record.specification || '-'}</span>
        </div>
        <div className="detail-row">
          <strong>{t('query.fields.bottomTapeLot')}:</strong>
          <span>{record.bottom_tape_lot || '-'}</span>
        </div>
        {record.notes && (
          <div className="detail-row">
            <strong>{t('query.fields.notes')}:</strong>
            <span>{record.notes}</span>
          </div>
        )}
        <div className="detail-row">
          <strong>{t('query.fields.createdAt')}:</strong>
          <span>{new Date(record.created_at).toLocaleString()}</span>
        </div>
        {displayData.rows && Array.isArray(displayData.rows) && displayData.rows.length > 0 ? (
          <div className="additional-data-section">
            <div className="section-title">{t('query.sections.checkItemsDetail')}</div>
            <div className="text-display-container">
              {displayData.rows.map((row: any, idx: number) => {
                const rowProductId = generateRowProductId(record, row);
                return (
                  <div key={idx} className="text-item-row" style={{ marginBottom: '15px', padding: '15px', borderBottom: '1px solid #eee', backgroundColor: '#f9f9f9', borderRadius: '4px' }}>
                    <div style={{ fontWeight: 'bold', marginBottom: '8px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span>{t('query.p3.rowHeader', { index: idx + 1, productId: rowProductId })}</span>
                    </div>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '15px' }}>
                      {Object.keys(row).map(header => (
                        <div key={header} style={{ fontSize: '14px', display: 'flex', flexDirection: 'column' }}>
                          <span style={{ color: '#666', fontSize: '12px', marginBottom: '2px' }}>{header}</span>
                          <span style={{ fontWeight: '500' }}>{formatFieldValue(header, row[header])}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        ) : (
          renderAdditionalData(displayData)
        )}
      </div>
    );
  };

  return (
    <div className="query-page">
      {/* 搜尋區域 */}
      <section className="query-search-section">
        <label className="query-search-label">
          {t('query.title')}
          
          <div className="query-description">
            <p><strong>{t('query.descLotTitle')}</strong>{t('query.descLot')}</p>
            <p><strong>{t('query.descProductTitle')}</strong>{t('query.descProduct')}</p>
            <p><strong>{t('query.descAdvancedTitle')}</strong>{t('query.descAdvanced')}</p>
          </div>

          <div className="query-search-input-wrapper autocomplete-wrapper">
            {!effectiveTenantId && (
              <div
                style={{
                  marginBottom: '10px',
                  padding: '10px 12px',
                  borderRadius: '8px',
                  background: '#fff3cd',
                  border: '1px solid #ffeeba',
                  color: '#856404',
                  fontSize: '14px',
                }}
              >
                {t('query.noTenantWarning')}
              </div>
            )}
            <input
              ref={inputRef}
              type="text"
              className="query-search-input"
              placeholder={t('query.searchPlaceholder')}
              value={searchKeyword}
              onChange={handleInputChange}
              onFocus={handleInputFocus}
              onBlur={handleInputBlur}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  handleSearch();
                } else if (e.key === "Escape") {
                  setShowSuggestions(false);
                }
              }}
            />
            
            {/* 自動完成建議 */}
            {showSuggestions && (
              <div ref={suggestionsRef} className="autocomplete-suggestions">
                {suggestionLoading ? (
                  <div className="suggestion-item loading">{t('query.suggestionLoading')}</div>
                ) : suggestions.length > 0 ? (
                  suggestions.map((suggestion, index) => (
                    <div
                      key={index}
                      className="suggestion-item"
                      onMouseDown={() => handleSuggestionClick(suggestion)}
                    >
                      {suggestion}
                    </div>
                  ))
                ) : (
                  <div className="suggestion-item no-results">{t('query.suggestionNoResults')}</div>
                )}
              </div>
            )}
            
            <button 
              className="btn-primary" 
              onClick={handleSearch}
              disabled={loading || !tenantId}
            >
              {loading ? t('query.searching') : t('query.search')}
            </button>
            
            {/* 清除按鈕 */}
            {searchKeyword && (
              <button 
                className="btn-secondary" 
                onClick={handleClear}
              >
                {t('common.clear')}
              </button>
            )}
            
            {/* 進階搜尋按鈕 */}
            <button 
              className={`btn-secondary advanced-search-toggle ${advancedSearchExpanded ? 'expanded' : ''}`}
              onClick={() => setAdvancedSearchExpanded(!advancedSearchExpanded)}
              type="button"
              title={t('query.advancedSearch')}
              aria-expanded={advancedSearchExpanded}
              aria-controls="advanced-search-panel"
            >
              <span className={`toggle-icon ${advancedSearchExpanded ? 'expanded' : ''}`}>▶</span>
              {t('query.advancedSearch')}
            </button>
          </div>
          
          {/* 進階搜尋面板 */}
          <AdvancedSearch
            onSearch={handleAdvancedSearch}
            onReset={handleAdvancedReset}
            isExpanded={advancedSearchExpanded}
            tenantId={tenantId}
          />
        </label>
      </section>

      {/* 追溯結果（同頁三站 Tabs，預設站3） */}
      {traceabilityData && (
        <section className="query-result-section" ref={traceSectionRef}>
          <div className="records-container">
            <div className="records-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <h3>{traceabilityData.product_id ? `${t('query.traceResult')} - ${traceabilityData.product_id}` : t('query.traceResult')}</h3>
              <button className="btn-secondary" onClick={() => setTraceabilityData(null)}>
                {t('query.clearTraceResult')}
              </button>
            </div>

            <div style={{ display: 'flex', gap: '8px', marginBottom: '12px' }}>
              <button
                className={traceActiveTab === 'P3' ? 'btn-primary' : 'btn-secondary'}
                onClick={() => setTraceActiveTab('P3')}
              >
                P3
              </button>
              <button
                className={traceActiveTab === 'P2' ? 'btn-primary' : 'btn-secondary'}
                onClick={() => setTraceActiveTab('P2')}
              >
                P2
              </button>
              <button
                className={traceActiveTab === 'P1' ? 'btn-primary' : 'btn-secondary'}
                onClick={() => setTraceActiveTab('P1')}
              >
                P1
              </button>
            </div>

            <div className="record-detail">
              {traceActiveTab === 'P3' && (
                (() => {
                  const rec = normalizeTraceRecord('P3', traceabilityData.p3);
                  return rec ? renderP3Details(rec) : <p className="section-empty">{t('common.noData')}</p>;
                })()
              )}
              {traceActiveTab === 'P2' && (
                (() => {
                  const rec = normalizeTraceRecord('P2', traceabilityData.p2);
                  return rec ? renderP2Details(rec) : <p className="section-empty">{t('common.noData')}</p>;
                })()
              )}
              {traceActiveTab === 'P1' && (
                (() => {
                  const rec = normalizeTraceRecord('P1', traceabilityData.p1);
                  return rec ? renderP1Details(rec) : <p className="section-empty">{t('common.noData')}</p>;
                })()
              )}
            </div>
          </div>
        </section>
      )}

      {/* 結果區域 */}
      {searchPerformed && (
        <section className="query-result-section">
          {loading ? (
            <p className="section-empty">{t('common.loading')}</p>
          ) : records.length === 0 ? (
            <p className="section-empty">{t('query.results.noResults')}</p>
          ) : (
            <div className="records-container">
              <div className="records-header">
                <h3>
                  {searchKeyword
                    ? t('query.results.foundCountWithKeyword', { keyword: searchKeyword, count: totalCount })
                    : t('query.results.foundCount', { count: totalCount })}
                </h3>
              </div>

              {(() => {
                const lotNoForDisplay = (advancedSearchParams?.lot_no || searchKeyword || '').trim();
                const isSingleP2LotCard =
                  !!lotNoForDisplay &&
                  !advancedSearchParams?.winder_number &&
                  records.length === 1 &&
                  records[0]?.data_type === 'P2';

                if (isSingleP2LotCard) {
                  const record = records[0];
                  return (
                    <div className="single-record-card">
                      <div className="single-record-card-header">
                        <div className="single-record-card-title">
                          <span className="single-record-lot">{record.lot_no}</span>
                          <span className={`data-type-label ${record.data_type.toLowerCase()}`}>{record.data_type}</span>
                        </div>
                        <div className="single-record-card-meta">
                          <div>{t('query.fields.slittingTime')}: {getP2SlittingTimeForSummary(record) ?? '-'}</div>
                          <div>{t('query.fields.createdAt')}: {new Date(record.created_at).toLocaleString('zh-TW', {
                            year: 'numeric',
                            month: '2-digit',
                            day: '2-digit',
                            hour: '2-digit',
                            minute: '2-digit',
                            hour12: false
                          })}</div>
                        </div>
                        <div className="single-record-card-actions">
                          <button
                            className="btn-expand"
                            title={t('query.actions.expandDetails')}
                            onClick={() => toggleExpand(record.id)}
                          >
                            {expandedRecordId === record.id ? t('common.collapse') : t('common.expand')}
                          </button>
                        </div>
                      </div>

                      {expandedRecordId === record.id && (
                        <div className="single-record-card-body">
                          {renderP2Details(record)}
                        </div>
                      )}
                    </div>
                  );
                }

                return (
                  <table className="records-table">
                    <thead>
                      <tr>
                        <th>{t('query.tableHeaders.lotNo')}</th>
                        <th>{t('query.tableHeaders.dataType')}</th>
                        <th>{t('query.tableHeaders.productionDate')}</th>
                        <th>{t('query.tableHeaders.createdAt')}</th>
                        <th>{t('query.tableHeaders.actions')}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {records.map((record) => (
                        <React.Fragment key={record.id}>
                          <tr>
                            <td>{record.lot_no}</td>
                            <td>
                              <span className={`data-type-label ${record.data_type.toLowerCase()}`}>
                                {record.data_type}
                              </span>
                            </td>
                            <td>
                              {record.data_type === 'P2'
                                ? (getP2SlittingTimeForSummary(record) ?? '-')
                                : formatFieldValue('production_date', record.production_date)}
                            </td>
                            <td>{new Date(record.created_at).toLocaleString('zh-TW', {
                              year: 'numeric',
                              month: '2-digit',
                              day: '2-digit',
                              hour: '2-digit',
                              minute: '2-digit',
                              hour12: false
                            })}</td>
                            <td>
                              <button
                                className="btn-expand"
                                title={t('query.actions.expandCsvData')}
                                onClick={() => toggleExpand(record.id)}
                              >
                                {expandedRecordId === record.id ? t('common.collapse') : t('common.expand')}
                              </button>
                            </td>
                          </tr>

                          {/* 展開行 - 顯示分組資料 */}
                          {expandedRecordId === record.id && (
                            <tr className="expanded-row">
                              <td colSpan={5}>
                                <div className="expanded-data-container">
                                  {renderExpandedContent(record)}
                                </div>
                              </td>
                            </tr>
                          )}
                        </React.Fragment>
                      ))}
                    </tbody>
                  </table>
                );
              })()}
              
              {/* 分頁控制 */}
              {totalCount > pageSize && (
                <div className="pagination">
                  <button
                    onClick={() => searchRecords(searchKeyword, currentPage - 1, advancedSearchParams || undefined)}
                    disabled={currentPage <= 1}
                  >
                    {t('query.pagination.previous')}
                  </button>
                  <span>{t('query.pagination.page', { page: currentPage })}</span>
                  <button
                    onClick={() => searchRecords(searchKeyword, currentPage + 1, advancedSearchParams || undefined)}
                    disabled={currentPage * pageSize >= totalCount}
                  >
                    {t('query.pagination.next')}
                  </button>
                </div>
              )}
            </div>
          )}
        </section>
      )}

      {/* 詳細資料模態框 */}
      <Modal
        open={detailRecord !== null}
        title={t('query.detailModalTitle', { type: String(detailRecord?.data_type || '') })}
        onClose={() => setDetailRecord(null)}
      >
        {detailRecord && (
          <div className="record-detail">
            {detailRecord.data_type === 'P1' && renderP1Details(detailRecord)}
            {detailRecord.data_type === 'P2' && renderP2Details(detailRecord)}
            {detailRecord.data_type === 'P3' && renderP3Details(detailRecord)}
          </div>
        )}
      </Modal>

      <EditRecordModal
        open={editRecord !== null}
        record={editRecord}
        type={editRecord?.data_type as any}
        tenantId={tenantId}
        onClose={() => setEditRecord(null)}
        onSave={(updated) => {
          console.log("Record updated:", updated);
          // Refresh search if needed
        }}
      />
    </div>
  );
}
