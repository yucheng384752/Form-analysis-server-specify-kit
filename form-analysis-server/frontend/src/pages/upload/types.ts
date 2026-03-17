export type FileType = "P1" | "P2" | "P3" | "PDF";

export interface CsvData {
  headers: string[];
  rows: string[][];
  colWidths: number[];
  starCells: Set<string>;
}

export interface UploadedFile {
  id: string;
  file: File;
  name: string;
  size: number;
  type: FileType;
  lotNo: string;
  status: "uploaded" | "validating" | "validated" | "importing" | "imported";
  jobBackend: "import_v2" | "pdf";
  uploadProgress: number;
  validateProgress: number;
  importProgress: number;
  csvData: CsvData | undefined;
  expanded: boolean;
  hasUnsavedChanges: boolean;
  processId: string | undefined;
  isValidated: boolean;
  validationErrors: any[] | undefined;

  // PDF 轉檔狀態（PDF 專用）
  pdfConvertStatus: "not_started" | "queued" | "uploading" | "processing" | "completed" | "failed" | undefined;
  pdfConvertJobId: string | undefined;
  pdfConvertProgress: number | undefined;
  pdfConvertError: string | undefined;
}

export const MAX_SIZE_BYTES = 10 * 1024 * 1024;

export const EDIT_ENABLED =
  String((import.meta as any).env?.VITE_ENABLE_CSV_EDIT ?? "true").toLowerCase() === "true";
