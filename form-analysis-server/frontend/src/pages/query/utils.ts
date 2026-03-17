import type { DataType } from '../../types/common'
import type { QueryRecord } from './types'

export const normalizeMaybeNumber = (v: any): number | null => {
  if (v === null || v === undefined) return null;
  if (typeof v === 'number' && Number.isFinite(v)) return v;
  const s = String(v).trim();
  if (!s) return null;
  const n = Number(s);
  return Number.isFinite(n) ? n : null;
};

export const getP2RowWinderNumber = (row: any): number | null => {
  if (!row || typeof row !== 'object') return null;
  return (
    normalizeMaybeNumber(row.winder_number) ??
    normalizeMaybeNumber(row['winder_number']) ??
    normalizeMaybeNumber(row['Winder number']) ??
    normalizeMaybeNumber(row['Winder Number'])
  );
};

export const mergeP2RecordsForLotNo = (records: QueryRecord[], lotNo: string): QueryRecord[] => {
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

export const isLikelyProductId = (value: string): boolean => {
  const v = value.trim();
  return /^\d{8}_.+_.+_.+/.test(v);
};

export const getRowFieldValue = (row: any, keys: string[]): any => {
  for (const key of keys) {
    if (row && Object.prototype.hasOwnProperty.call(row, key)) {
      const val = row[key];
      if (val !== undefined && val !== null && val !== '') return val;
    }
  }
  return undefined;
};

export const isNgLike = (formatted: string): boolean => {
  const v = (formatted || '').toString().trim().toUpperCase();
  return v === 'X' || v.includes('NG');
};

export const normalizeTraceRecord = (type: DataType, record: any): QueryRecord | null => {
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

export const formatFieldValue = (header: string, value: any, t?: (key: string, opts?: any) => string): string => {
  if (value === null || value === undefined) return '-';

  if (Array.isArray(value)) {
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

  if (header === '10Po' || header === '10PO') {
    if (typeof value === 'boolean') return value ? 'V' : 'X';
    if (value === 1 || value === '1' || value === true) return 'V';
    if (value === 0 || value === '0' || value === false) return 'X';
  }

  const p3BooleanFields = ['shift', 'iron', 'mold', 'rubber wheel', 'finish', 'Shift', 'Iron', 'Mold', 'Rubber wheel', 'Finish'];
  if (p3BooleanFields.includes(header)) {
    if (typeof value === 'boolean') return value ? 'V' : 'X';
    if (value === 1 || value === '1' || value === true) return 'V';
    if (value === 0 || value === '0' || value === false) return 'X';
  }

  const p2BooleanFields = ['appearance', 'rough edge', 'striped results', 'Appearance', 'Rough edge', 'Striped results', '外觀', '毛邊', '分條結果'];
  if (p2BooleanFields.includes(header)) {
    if (typeof value === 'boolean') return value ? 'V' : 'X';
    if (value === 1 || value === '1' || value === true) return 'V';
    if (value === 0 || value === '0' || value === false) return 'X';
  }

  if (header === '分條時間' || header === 'slitting time') {
    if (value && typeof value === 'string') {
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

  if (header === 'Slitting machine' || header === 'slitting machine' || header === 'slitting_machine_number') {
    if (t) {
      if (value === 1 || value === '1') return t('query.p2.slittingMachineDisplay.points1');
      if (value === 2 || value === '2') return t('query.p2.slittingMachineDisplay.points2');
    }
  }

  if (header === 'Production Date' || header === 'production_date') {
    if (!value) return '-';

    if (typeof value === 'number') {
      const numStr = value.toString();
      if (numStr.length === 6) {
        const year = '20' + numStr.substring(0, 2);
        const month = numStr.substring(2, 4);
        const day = numStr.substring(4, 6);
        return `${year}-${month}-${day}`;
      }
    }

    if (typeof value === 'string') {
      if (/^\d{4}-\d{2}-\d{2}$/.test(value)) return value;

      if (/^\d{6}$/.test(value)) {
        const year = '20' + value.substring(0, 2);
        const month = value.substring(2, 4);
        const day = value.substring(4, 6);
        return `${year}-${month}-${day}`;
      }

      if (value.includes('/')) {
        const parts = value.split('/');
        if (parts.length === 3) {
          let year = parts[0];
          const month = parts[1].padStart(2, '0');
          const day = parts[2].padStart(2, '0');
          if (year.length === 2) year = '20' + year;
          return `${year}-${month}-${day}`;
        }
      }
    }
  }

  if (typeof value === 'number') return value.toLocaleString();
  return value === '' ? '-' : String(value);
};

export const formatP2SlittingTimeValue = (rawValue: any, productionDate?: any): string => {
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

export const getP2SlittingTimeForSummary = (record: QueryRecord): string | null => {
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

export const generateRowProductId = (record: QueryRecord, row: any): string => {
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

  let dateStr = '';
  if (record.production_date) {
    dateStr = record.production_date.replace(/\D/g, '');
    if (dateStr.length > 8) dateStr = dateStr.substring(0, 8);
  } else {
    const dateObj = new Date(record.created_at);
    const year = dateObj.getFullYear();
    const month = String(dateObj.getMonth() + 1).padStart(2, '0');
    const day = String(dateObj.getDate()).padStart(2, '0');
    dateStr = `${year}${month}${day}`;
  }

  const machine = record.machine_no || row['Machine NO'] || row['Machine No'] || row['machine'] || row['Machine'] || 'Unknown';
  const mold = record.mold_no || row['Mold NO'] || row['Mold No'] || row['mold'] || row['Mold'] || 'Unknown';
  const lotRaw = row['lot'] || row['Lot'] || row['production_lot'] || row['Production Lot'] || row['lot_no'] || row['Lot No'] || '0';
  const lot = normalizeLotToken(lotRaw) || '0';

  const providedId = String(row['product_id'] || '').trim();
  if (providedId) {
    const suffix = providedId.split('_').pop() || '';
    if (!lot || suffix === lot) {
      return providedId;
    }
  }

  return `${dateStr}_${machine}_${mold}_${lot}`;
};

export const getFlattenedAdditionalData = (additionalData: { [key: string]: any } | undefined) => {
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

export const getValueByKeyRegex = (data: { [key: string]: any }, regexes: RegExp[]): any => {
  for (const [k, v] of Object.entries(data)) {
    for (const re of regexes) {
      if (re.test(k)) return v;
    }
  }
  return undefined;
};

export const formatCell = (value: any) => {
  if (value === null || value === undefined) return '-';
  const s = String(value).trim();
  return s === '' || s === '-' ? '-' : s;
};
