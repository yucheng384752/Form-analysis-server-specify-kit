import type { CsvData, FileType } from './types';

export function detectFileType(name: string): FileType {
  if (name.toLowerCase().endsWith(".pdf")) return "PDF";
  if (name.startsWith("P1_")) return "P1";
  if (name.startsWith("P2_")) return "P2";
  return "P3";
}

// P1 / P2: 由檔名取 lot_no，例如 P1_2503033_02.csv -> 2503033_02
export function deriveLotNoFromFilename(name: string): string {
  const base = name.replace(/\.csv$/i, "");
  const parts = base.split("_");
  const meaningful = parts.slice(1);
  if (meaningful.length === 0) return "";
  if (meaningful.length === 1) return normalizeLotNo(meaningful[0]);
  const head = normalize7Digits(meaningful[0]);
  const tailDigits = meaningful[1].replace(/\D/g, "");
  const tail = tailDigits.padStart(2, "0").slice(-2);
  return `${head}_${tail}`;
}

// P3: 由 P3_No. 欄位取 lot_no：2411012_03_05_301 -> 2411012_03
export function normalizeP3LotNo(value: string): string {
  const parts = value.split("_");
  if (parts.length < 2) return normalizeLotNo(value);
  const head = normalize7Digits(parts[0]);
  const tailDigits = parts[1].replace(/\D/g, "");
  const tail = tailDigits.padStart(2, "0").slice(-2);
  return `${head}_${tail}`;
}

export function normalize7Digits(x: string): string {
  const digits = x.replace(/\D/g, "");
  return digits.padStart(7, "0").slice(-7);
}

export function normalizeLotNo(raw: string): string {
  const [a, b] = raw.split("_");
  const head = normalize7Digits(a ?? raw);
  if (!b) return head;
  const tailDigits = b.replace(/\D/g, "");
  const tail = tailDigits.padStart(2, "0").slice(-2);
  return `${head}_${tail}`;
}

// 簡單 CSV parser（未處理引號逗號，之後可換成 PapaParse）
export async function parseCsv(file: File): Promise<CsvData> {
  const text = await file.text();
  const lines = text.split(/\r?\n/).filter((l) => l.trim().length > 0);
  if (!lines.length) {
    return { headers: [], rows: [], colWidths: [], starCells: new Set() };
  }
  const rows = lines.map((line) => line.split(","));
  const headers = rows[0];
  const dataRows = rows.slice(1);

  // 偵測帶 * 或前後空格的儲存格，標記為顯著值
  const starCells = new Set<string>();
  for (let r = 0; r < dataRows.length; r++) {
    for (let c = 0; c < dataRows[r].length; c++) {
      const raw = dataRows[r][c];
      if (!raw) continue;
      let marked = false;
      let cleaned = raw;
      if (cleaned.includes('*')) {
        marked = true;
        cleaned = cleaned.replace(/\*/g, '');
      }
      if (cleaned !== cleaned.trim()) {
        marked = true;
      }
      if (marked) {
        starCells.add(`${r}_${c}`);
        dataRows[r][c] = cleaned;
      }
    }
  }

  const colCount = headers.length;
  const colWidths = new Array(colCount).fill(0);

  const updateWidth = (col: number, value: string) => {
    const length = value.length;
    colWidths[col] = Math.max(colWidths[col], length);
  };

  headers.forEach((h, i) => updateWidth(i, h));
  dataRows.forEach((row) =>
    row.forEach((cell, i) => updateWidth(i, cell ?? ""))
  );

  const pixelWidths = colWidths.map((len) =>
    Math.max(80, Math.min(len * 10, 260))
  );

  return { headers, rows: dataRows, colWidths: pixelWidths, starCells };
}
