// src/pages/QueryPage.tsx
import React, { useState, useRef } from "react";
import { Modal } from "../components/common/Modal";
import { AdvancedSearch, AdvancedSearchParams } from "../components/AdvancedSearch";
import { EditRecordModal } from "../components/EditRecordModal";
import "../styles/query-page.css";

// 資料類型枚舉
type DataType = 'P1' | 'P2' | 'P3';

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

export function QueryPage() {
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
  
  // 表格排序狀態: { 'recordId-tableType': { column: 'columnName', direction: 'asc'|'desc' } }
  const [tableSortState, setTableSortState] = useState<{ [key: string]: { column: string; direction: 'asc' | 'desc' } }>({});

  React.useEffect(() => {
    const storedTenantId = window.localStorage.getItem(TENANT_STORAGE_KEY);
    if (storedTenantId) {
      setTenantId(storedTenantId);
      return;
    }

    fetch('/api/tenants')
      .then(res => res.json())
      .then(data => {
        if (data && data.length > 0) {
          const id = data[0].id;
          setTenantId(id);
          try {
            window.localStorage.setItem(TENANT_STORAGE_KEY, id);
          } catch {
            // ignore
          }
        }
      })
      .catch(err => console.error("Failed to fetch tenants", err));
  }, []);

  const mergeTenantHeaders = (headers?: HeadersInit): HeadersInit => {
    const tenantHeaders: Record<string, string> = tenantId ? { 'X-Tenant-Id': tenantId } : {};

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
        return '分1Points 1';
      }
      if (value === 2 || value === '2') {
        return '分2Points 2';
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

  // 搜尋記錄 (支援基本搜尋和進階搜尋)
  const searchRecords = async (search: string, page: number = 1, advancedParams?: AdvancedSearchParams) => {
    setLoading(true);
    try {
      let apiUrl = '/api/v2/query/records';
      const params = new URLSearchParams({
        page: page.toString(),
        page_size: pageSize.toString()
      });
      
      // 優先使用進階搜尋參數
      if (advancedParams) {
        apiUrl = '/api/v2/query/records/advanced';
        if (advancedParams.lot_no) params.append('lot_no', advancedParams.lot_no);
        if (advancedParams.production_date_from) params.append('production_date_from', advancedParams.production_date_from);
        if (advancedParams.production_date_to) params.append('production_date_to', advancedParams.production_date_to);
        if (advancedParams.machine_no) params.append('machine_no', advancedParams.machine_no);
        if (advancedParams.mold_no) params.append('mold_no', advancedParams.mold_no);
        if (advancedParams.product_id) params.append('product_id', advancedParams.product_id);
        if (advancedParams.specification) params.append('specification', advancedParams.specification);
        if (advancedParams.winder_number) params.append('winder_number', advancedParams.winder_number);
        if (advancedParams.data_type) params.append('data_type', advancedParams.data_type);
      } else if (search) {
        params.append('lot_no', search);
      }
      
      const response = await fetchWithTenant(`${apiUrl}?${params}`);
      if (response.ok) {
        const data: QueryResponse = await response.json();
        setRecords(data.records);
        setTotalCount(data.total_count);
        setCurrentPage(data.page);
        setSearchPerformed(true);
      } else {
        console.error("搜尋記錄時出錯:", response.status);
      }
    } catch (error) {
      console.error("搜尋記錄時出錯:", error);
    } finally {
      setLoading(false);
    }
  };

  // 輔助函數：產生 P3 Row 的 Product ID
  const generateRowProductId = (record: QueryRecord, row: any): string => {
    // 如果後端已經提供了 product_id，直接使用
    if (row['product_id']) {
      return row['product_id'];
    }

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
    const machine = record.machine_no || row['machine'] || row['Machine'] || 'Unknown';

    // 3. 模具號碼
    const mold = record.mold_no || row['mold'] || row['Mold'] || 'Unknown';

    // 4. Lot (優先使用 row 中的 lot 資訊)
    const lot = row['lot'] || row['Lot'] || row['production_lot'] || row['Production Lot'] || row['lot_no'] || row['Lot No'] || '0';

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
            
            console.log('從 P3_No 解析成功:', { p3No, baseLotNo, sourceWinder });
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
              console.log('從 lot no 欄位解析成功:', { lotNoVal, baseLotNo, sourceWinder });
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
        alert('無法取得批號資訊');
        return;
      }
      
      if (!sourceWinder) {
        alert('無法從 P3 資料中提取卷收機編號 (Winder Number)，無法進行關聯查詢。\n請確認 P3_No 格式 (Lot_Winder_Batch) 或欄位中包含 Winder 資訊。');
        return;
      }
      
      console.log('P3 關聯查詢執行:', {
        baseLotNo,
        sourceWinder,
        message: '使用解析出的批號 + winder_number 搜尋 P2'
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
           alert(`未找到對應的 P2 記錄（Lot: ${baseLotNo}, Winder: ${sourceWinder}）`);
           setLoading(false);
           return;
        }
        throw new Error(`追溯查詢失敗: ${traceResponse.statusText}`);
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
      console.error('P3 關聯查詢失敗:', error);
      alert(`查詢失敗: ${error.message || '未知錯誤'}`);
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
        console.error("獲取建議時出錯:", response.status);
        setSuggestions([]);
        setShowSuggestions(false);
      }
    } catch (error) {
      console.error("獲取建議時出錯:", error);
      setSuggestions([]);
      setShowSuggestions(false);
    } finally {
      setSuggestionLoading(false);
    }
  };

  // 處理基本搜尋
  const handleSearch = async () => {
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
            alert('查無此產品');
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
        console.error('Product ID 追溯查詢失敗:', e);
        alert(`查詢失敗: ${e?.message || '未知錯誤'}`);
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
    fetchSuggestions(value);
  };

  // 處理建議點擊
  const handleSuggestionClick = (suggestion: string) => {
    setSearchKeyword(suggestion);
    setShowSuggestions(false);
    searchRecords(suggestion);
  };

  // 處理輸入焦點
  const handleInputFocus = () => {
    if (searchKeyword.trim().length >= 1) {
      fetchSuggestions(searchKeyword);
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
      const aVal = a[column];
      const bVal = b[column];
      
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

  // 分組資料的輔助函數
  const groupDataByPrefix = (data: { [key: string]: any }) => {
    const groups: { [key: string]: { [key: string]: any } } = {
      actual_temp: {},
      set_temp: {},
      other: {}
    };

    Object.entries(data).forEach(([key, value]) => {
      // 統一轉為小寫並移除空格進行判斷
      const normalizedKey = key.toLowerCase().replace(/\s+/g, '_');
      
      if (normalizedKey.startsWith('actual_temp')) {
        groups.actual_temp[key] = value;
      } else if (normalizedKey.startsWith('set_temp')) {
        groups.set_temp[key] = value;
      } else {
        groups.other[key] = value;
      }
    });

    return groups;
  };

  // 渲染分組區塊
  const renderGroupedSection = (
    recordId: string,
    title: string,
    sectionKey: string,
    data: { [key: string]: any },
    icon: string = "ℹ",
    vertical: boolean = false
  ) => {
    const isCollapsed = isSectionCollapsed(recordId, sectionKey);
    const fieldCount = Object.keys(data).length;

    return (
      <div className="data-section" key={sectionKey}>
        <div className="section-header">
          <div className="section-title-wrapper">
            <span className="section-icon">{icon}</span>
            <h5>{title}</h5>
            <span className="field-count-badge">{fieldCount}</span>
          </div>
          <button
            className="btn-collapse"
            onClick={() => toggleSection(recordId, sectionKey)}
          >
            {isCollapsed ? '展開' : '收起'}
          </button>
        </div>
        {!isCollapsed && (
          <div className="section-content">
            {vertical ? (
              <table className="data-table data-table-vertical">
                <tbody>
                  {Object.entries(data).map(([key, value]) => (
                    <tr key={key}>
                      <th>{key}</th>
                      <td>{formatFieldValue(key, value)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <table className="data-table">
                <thead>
                  <tr>
                    {Object.keys(data).map(key => (
                      <th key={key}>{key}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    {Object.keys(data).map((key) => (
                      <td key={key}>{formatFieldValue(key, data[key])}</td>
                    ))}
                  </tr>
                </tbody>
              </table>
            )}
          </div>
        )}
      </div>
    );
  };

  // 渲染P1展開內容
  const renderP1ExpandedContent = (record: QueryRecord) => {
    if (!record.additional_data) {
      return <p className="no-data">此記錄沒有額外的CSV資料</p>;
    }

    // P1 的 additional_data 通常包含 rows（陣列）。
    // 展開顯示時應以 rows[0] 的扁平欄位為主，避免把 rows 陣列直接渲染成 [object Object]。
    let p1DisplayData: { [key: string]: any } = record.additional_data;
    if (
      p1DisplayData &&
      (p1DisplayData as any).rows &&
      Array.isArray((p1DisplayData as any).rows) &&
      (p1DisplayData as any).rows.length > 0
    ) {
      const { rows, ...rest } = p1DisplayData as any;
      const row0 = rows[0];
      if (row0 && typeof row0 === 'object' && !Array.isArray(row0)) {
        p1DisplayData = { ...rest, ...row0 };
      } else {
        p1DisplayData = { ...rest };
      }
    }

    // 分組其他資料
    const grouped = groupDataByPrefix(p1DisplayData);

    // 合併 actual_temp 和 set_temp 作為押出機生產條件
    const extrusionConditions = {
      ...grouped.actual_temp,
      ...grouped.set_temp
    };

    return (
      <div className="grouped-data-container">
        {/* 基本資料區塊已移除 */}
        
        {Object.keys(extrusionConditions).length > 0 && 
          renderGroupedSection(record.id, '押出機生產條件', 'extrusion', extrusionConditions, '', true)}
        
        {Object.keys(grouped.other).length > 0 && 
          renderGroupedSection(record.id, '其他參數', 'other', grouped.other, '')}
      </div>
    );
  };

  // 渲染P2展開內容
  const renderP2ExpandedContent = (record: QueryRecord) => {
    if (!record.additional_data) {
      return <p className="no-data">此記錄沒有額外的CSV資料</p>;
    }

    // 檢查是否為 rows 陣列結構
    const rows = record.additional_data.rows || [];
    const sortedRows = sortRowsNgFirst(rows, ['striped results', 'Striped results', '分條結果']);
    // 應用使用者排序
    const displayRows = sortTableData(sortedRows, record.id, 'p2');
    const hasRows = Array.isArray(rows) && rows.length > 0;
    
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
                <h5>檢測資料</h5>
                <span className="field-count-badge">{rows.length} 筆</span>
              </div>
              <button
                className="btn-collapse"
                onClick={() => toggleSection(record.id, 'rows_data')}
              >
                {isSectionCollapsed(record.id, 'rows_data') ? '展開' : '收起'}
              </button>
            </div>
            {!isSectionCollapsed(record.id, 'rows_data') && (
              <div className="section-content">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>#</th>
                      {Object.keys(rows[0]).map(key => (
                        <th 
                          key={key} 
                          onClick={() => handleTableSort(record.id, 'p2', key)}
                          style={{ cursor: 'pointer', userSelect: 'none' }}
                          title="點擊排序"
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
                        <td>{idx + 1}</td>
                        {Object.keys(rows[0]).map((header: string, vidx: number) => {
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
      return <p className="no-data">此記錄沒有額外的CSV資料</p>;
    }

    // 基本資料
    const basicData = {
      lot_no: record.lot_no,
      // p3_no: record.p3_no || '-',
      // product_id: record.product_id || '-',
      // machine_no: record.machine_no || '-',
      // mold_no: record.mold_no || '-',
      // specification: record.specification || '-',
      // bottom_tape_lot: record.bottom_tape_lot || '-',
      updated_at: new Date(record.created_at).toLocaleString('zh-TW'),
      created_at: new Date(record.created_at).toLocaleString('zh-TW')
    };

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
            <span className="badge badge-primary">批號: {record.lot_no}</span>
            <span className="badge badge-success">檢查筆數: {rowCount}筆</span>
          </div>
          <div className="p3-stats">
            <div className="stat-item">
              <span className="stat-label">原始筆數:</span>
              <span className="stat-value">{rowCount}</span>
            </div>
            <div className="stat-item">
              <span className="stat-label">有效筆數:</span>
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
                <h5>檢查項目明細</h5>
                <span className="field-count-badge">{rows.length} 筆</span>
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
                        <th className="action-column">關聯查詢</th>
                        <th 
                          onClick={() => handleTableSort(record.id, 'p3', 'product_id')}
                          style={{ cursor: 'pointer', userSelect: 'none' }}
                          title="點擊排序"
                        >
                          Product ID
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
                            title="點擊排序"
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
                                title="查詢對應的 P2 和 P1 資料"
                                onClick={() => handleP3LinkSearch(record, row, rowProductId)}
                              >
                                查詢
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
        return <p className="no-data">未知的資料類型</p>;
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
          <div className="section-title">檢查項目明細</div>
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
    // 定義要排除的系統欄位
    const excludedKeys = [
      'id', 'lot_no', 'data_type', 'created_at', 'updated_at', 
      'additional_data', 'notes', 'display_name', 'production_date',
      'product_name', 'quantity'
    ];

    // 獲取所有非系統欄位的鍵值對 (包含後端展開的 additional_data 欄位)
    const detailFields = Object.entries(record).filter(([key, value]) => {
      return !excludedKeys.includes(key) && 
             value !== null && 
             value !== undefined && 
             typeof value !== 'object'; // 排除物件類型
    });

    return (
      <div className="detail-grid">
        <div className="detail-row">
          <strong>批號：</strong>
          <span>{record.lot_no}</span>
        </div>
        {record.product_name && (
           <div className="detail-row">
            <strong>產品名稱：</strong>
            <span>{record.product_name}</span>
          </div>
        )}
        {record.quantity !== undefined && (
           <div className="detail-row">
            <strong>數量：</strong>
            <span>{record.quantity}</span>
          </div>
        )}
        {record.production_date && (
           <div className="detail-row">
            <strong>生產日期：</strong>
            <span>{formatFieldValue('production_date', record.production_date)}</span>
          </div>
        )}
        {record.notes && (
          <div className="detail-row">
            <strong>備註：</strong>
            <span>{record.notes}</span>
          </div>
        )}
        <div className="detail-row">
          <strong>建立時間：</strong>
          <span>{new Date(record.created_at).toLocaleString()}</span>
        </div>
        
        {/* 動態渲染其他欄位 */}
        {detailFields.map(([key, value]) => (
          <div className="detail-row" key={key}>
            <strong>{key}：</strong>
            <span>{formatFieldValue(key, value)}</span>
          </div>
        ))}
        
        {renderAdditionalData(record.additional_data)}
        
        {/* P0: 暫時移除 P1 詳情的編輯入口（避免 422） */}
      </div>
    );
  };

  // 渲染P2詳細資料
  const renderP2Details = (record: QueryRecord) => {
    console.log('[Traceability Debug] Rendering P2 details for record:', record);
    
    // 準備要顯示的額外資料
    let displayData: { [key: string]: any } = {};
    
    // 1. 先加入標準欄位
    const standardFields: { [key: string]: any } = {
      '分條機': record.slitting_machine_number,
      '收卷機': record.winder_number,
      '片材寬度': record.sheet_width,
      '厚度1': record.thickness1,
      '厚度2': record.thickness2,
      '厚度3': record.thickness3,
      '厚度4': record.thickness4,
      '厚度5': record.thickness5,
      '厚度6': record.thickness6,
      '厚度7': record.thickness7,
      '外觀': record.appearance,
      '毛邊': record.rough_edge,
      '分條結果': record.slitting_result,
    };

    // 過濾掉 undefined/null 的標準欄位
    Object.entries(standardFields).forEach(([key, value]) => {
      if (value !== undefined && value !== null) {
        displayData[key] = value;
      }
    });

    // 2. 合併額外資料
    // 如果 P2 資料包含 rows 且只有一筆，提取出來以 Grid 方式顯示 (像 P1 一樣)
    // 這樣可以顯示單個 row 的所有細項
    if (record.additional_data && 
        record.additional_data.rows && 
        Array.isArray(record.additional_data.rows) && 
        record.additional_data.rows.length === 1) {
      displayData = { ...displayData, ...record.additional_data.rows[0] };
    } else if (record.additional_data) {
      displayData = { ...displayData, ...record.additional_data };
    }

    // 移除 rows 屬性，避免在 renderAdditionalData 中被誤判為表格顯示
    if (displayData.rows) {
        delete displayData.rows;
    }

    return (
      <div className="detail-grid">
        <div className="detail-row">
          <strong>批號：</strong>
          <span>{record.lot_no}</span>
        </div>
        <div className="detail-row">
          <strong>建立時間：</strong>
          <span>{new Date(record.created_at).toLocaleString()}</span>
        </div>
        
        {/* 直接顯示合併後的 displayData，不使用 renderAdditionalData (因為已被禁用) */}
        {Object.entries(displayData).map(([key, value]) => (
            <div key={key} className="detail-row">
              <strong>{key}：</strong>
              <span>{formatFieldValue(key, value)}</span>
            </div>
        ))}
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
          <strong>批號：</strong>
          <span>{record.lot_no}</span>
        </div>
        <div className="detail-row">
          <strong>P3編號：</strong>
          <span>{record.p3_no}</span>
        </div>
        <div className="detail-row">
          <strong>Product ID：</strong>
          <span>{record.product_id || '-'}</span>
        </div>
        
        <div className="detail-row">
          <strong>機台：</strong>
          <span>{record.machine_no || '-'}</span>
        </div>
        <div className="detail-row">
          <strong>模具：</strong>
          <span>{record.mold_no || '-'}</span>
        </div>
        <div className="detail-row">
          <strong>規格：</strong>
          <span>{record.specification || '-'}</span>
        </div>
        <div className="detail-row">
          <strong>下膠編號：</strong>
          <span>{record.bottom_tape_lot || '-'}</span>
        </div>
        {record.notes && (
          <div className="detail-row">
            <strong>備註：</strong>
            <span>{record.notes}</span>
          </div>
        )}
        <div className="detail-row">
          <strong>建立時間：</strong>
          <span>{new Date(record.created_at).toLocaleString()}</span>
        </div>
        {displayData.rows && Array.isArray(displayData.rows) && displayData.rows.length > 0 ? (
          <div className="additional-data-section">
            <div className="section-title">檢查項目明細</div>
            <div className="text-display-container">
              {displayData.rows.map((row: any, idx: number) => {
                const rowProductId = generateRowProductId(record, row);
                return (
                  <div key={idx} className="text-item-row" style={{ marginBottom: '15px', padding: '15px', borderBottom: '1px solid #eee', backgroundColor: '#f9f9f9', borderRadius: '4px' }}>
                    <div style={{ fontWeight: 'bold', marginBottom: '8px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span>#{idx + 1} - Product ID: {rowProductId}</span>
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
          資料查詢
          
          <div className="query-description">
            <p><strong>批號查詢：</strong>輸入批號進行模糊搜尋，查詢後可查看 P1/P2/P3 分類資料</p>
            <p><strong>產品編號查詢：</strong>直接輸入 Product ID 會顯示該筆的 P1/P2/P3 追溯結果</p>
            <p><strong>進階搜尋：</strong>可依日期範圍、機台號碼、下膠編號、產品編號、P3規格等條件進行多條件組合搜尋</p>
          </div>

          <div className="query-search-input-wrapper autocomplete-wrapper">
            <input
              ref={inputRef}
              type="text"
              className="query-search-input"
              placeholder="輸入 Lot No(批號) 或 Product ID 查詢"
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
                  <div className="suggestion-item loading">載入建議中...</div>
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
                  <div className="suggestion-item no-results">沒有找到相符的建議</div>
                )}
              </div>
            )}
            
            <button 
              className="btn-primary" 
              onClick={handleSearch}
              disabled={loading}
            >
              {loading ? "查詢中..." : "查詢"}
            </button>
            
            {/* 清除按鈕 */}
            {searchKeyword && (
              <button 
                className="btn-secondary" 
                onClick={handleClear}
              >
                清除
              </button>
            )}
            
            {/* 進階搜尋按鈕 */}
            <button 
              className="advanced-search-toggle"
              onClick={() => setAdvancedSearchExpanded(!advancedSearchExpanded)}
              type="button"
              title="進階搜尋"
            >
              <span className={`toggle-icon ${advancedSearchExpanded ? 'expanded' : ''}`}>▶</span>
              進階搜尋
            </button>
          </div>
          
          {/* 進階搜尋面板 */}
          <AdvancedSearch
            onSearch={handleAdvancedSearch}
            onReset={handleAdvancedReset}
            isExpanded={advancedSearchExpanded}
            onToggle={() => setAdvancedSearchExpanded(!advancedSearchExpanded)}
            tenantId={tenantId}
          />
        </label>
      </section>

      {/* 追溯結果（同頁三站 Tabs，預設站3） */}
      {traceabilityData && (
        <section className="query-result-section" ref={traceSectionRef}>
          <div className="records-container">
            <div className="records-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <h3>{traceabilityData.product_id ? `追溯結果 - ${traceabilityData.product_id}` : '追溯結果'}</h3>
              <button className="btn-secondary" onClick={() => setTraceabilityData(null)}>
                清除追溯結果
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
                  return rec ? renderP3Details(rec) : <p className="section-empty">查無資料</p>;
                })()
              )}
              {traceActiveTab === 'P2' && (
                (() => {
                  const rec = normalizeTraceRecord('P2', traceabilityData.p2);
                  return rec ? renderP2Details(rec) : <p className="section-empty">查無資料</p>;
                })()
              )}
              {traceActiveTab === 'P1' && (
                (() => {
                  const rec = normalizeTraceRecord('P1', traceabilityData.p1);
                  return rec ? renderP1Details(rec) : <p className="section-empty">查無資料</p>;
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
            <p className="section-empty">載入中...</p>
          ) : records.length === 0 ? (
            <p className="section-empty">沒有找到符合條件的資料</p>
          ) : (
            <div className="records-container">
              <div className="records-header">
                <h3>{searchKeyword ? `${searchKeyword} - ` : ''}共找到 {totalCount} 筆資料</h3>
              </div>
              
              <table className="records-table">
                <thead>
                  <tr>
                    <th>Lot No</th>
                    <th>資料類型</th>
                    <th>生產日期</th>
                    <th>建立時間</th>
                    <th>操作</th>
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
                        <td>{formatFieldValue('production_date', record.production_date)}</td>
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
                            title="展開查看CSV資料"
                            onClick={() => toggleExpand(record.id)}
                          >
                            {expandedRecordId === record.id ? '收起' : '展開'}
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
              
              {/* 分頁控制 */}
              {totalCount > pageSize && (
                <div className="pagination">
                  <button
                    onClick={() => searchRecords(searchKeyword, currentPage - 1, advancedSearchParams || undefined)}
                    disabled={currentPage <= 1}
                  >
                    上一頁
                  </button>
                  <span>第 {currentPage} 頁</span>
                  <button
                    onClick={() => searchRecords(searchKeyword, currentPage + 1, advancedSearchParams || undefined)}
                    disabled={currentPage * pageSize >= totalCount}
                  >
                    下一頁
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
        title={`${detailRecord?.data_type} 資料詳情`}
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
