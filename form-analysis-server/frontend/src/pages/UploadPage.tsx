// src/pages/UploadPage.tsx
import { useState, useRef, useEffect } from "react";
import { useToast } from "../components/common/ToastContext";
import { ProgressBar } from "../components/common/ProgressBar";
import { Modal } from "../components/common/Modal";
import "./../styles/upload-page.css";

const EDIT_ENABLED = false; // 第一版：不提供編輯（僅預覽 + 重傳）

const TENANT_STORAGE_KEY = "form_analysis_tenant_id";

type FileType = "P1" | "P2" | "P3";

export interface CsvData {
  headers: string[];
  rows: string[][];
  colWidths: number[];
}

export interface UploadedFile {
  id: string;
  file: File;
  name: string;
  size: number;
  type: FileType;
  lotNo: string;
  status: "uploaded" | "validating" | "validated" | "importing" | "imported";
  uploadProgress: number;
  validateProgress: number;
  importProgress: number;
  csvData: CsvData | undefined;
  expanded: boolean;
  hasUnsavedChanges: boolean;
  processId: string | undefined;  // 後端返回的 process_id
  isValidated: boolean; // 是否已驗證過
  validationErrors: any[] | undefined; // 驗證錯誤
}

const MAX_SIZE_BYTES = 10 * 1024 * 1024;

function detectFileType(name: string): FileType {
  if (name.startsWith("P1_")) return "P1";
  if (name.startsWith("P2_")) return "P2";
  return "P3";
}

// P1 / P2: 由檔名取 lot_no，例如 P1_2503033_02.csv -> 2503033_02
function deriveLotNoFromFilename(name: string): string {
  const base = name.replace(/\.csv$/i, "");
  const parts = base.split("_");
  // 移除 P1 / P2 / P3 前綴
  const meaningful = parts.slice(1); // [2503033, 02] or [2503033, 2]
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

function normalize7Digits(x: string): string {
  const digits = x.replace(/\D/g, "");
  return digits.padStart(7, "0").slice(-7);
}

export function normalizeLotNo(raw: string): string {
  // 用於一般情況：把"2503033_3" -> 2503033_03
  const [a, b] = raw.split("_");
  const head = normalize7Digits(a ?? raw);
  if (!b) return head;
  const tailDigits = b.replace(/\D/g, "");
  const tail = tailDigits.padStart(2, "0").slice(-2);
  return `${head}_${tail}`;
}

// 簡單 CSV parser（未處理引號逗號，之後可換成 PapaParse）
async function parseCsv(file: File): Promise<CsvData> {
  const text = await file.text();
  const lines = text.split(/\r?\n/).filter((l) => l.trim().length > 0);
  if (!lines.length) {
    return { headers: [], rows: [], colWidths: [] };
  }
  const rows = lines.map((line) => line.split(","));
  const headers = rows[0];
  const dataRows = rows.slice(1);

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

  return { headers, rows: dataRows, colWidths: pixelWidths };
}

export function UploadPage() {
  const [files, setFiles] = useState<UploadedFile[]>([]);
  const [confirmTargetId, setConfirmTargetId] = useState<string | null>(null);
  const [showBatchImportConfirm, setShowBatchImportConfirm] = useState(false);
  const { showToast } = useToast();

  const [tenantId, setTenantId] = useState<string>("");

  // 使用 ref 追蹤最新的 files 狀態，以解決在非同步操作（如 setTimeout）中存取過時狀態的問題
  // 同時避免在 setFiles 的 updater function 中執行副作用（如 showToast）
  const filesRef = useRef(files);
  useEffect(() => {
    filesRef.current = files;
  }, [files]);

  useEffect(() => {
    const storedTenantId = window.localStorage.getItem(TENANT_STORAGE_KEY);
    if (storedTenantId) {
      setTenantId(storedTenantId);
      return;
    }

    // v2 import/query 需要 tenant header；這裡先用第一個 tenant 當預設（最少改動）。
    fetch('/api/tenants')
      .then((res) => res.json())
      .then((data) => {
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
      .catch(() => {
        // 不阻斷 UI；若後端無法自動解析 tenant，後續 v2 呼叫會回 422。
      });
  }, []);

  const buildTenantHeaders = (): HeadersInit => {
    return tenantId ? { 'X-Tenant-Id': tenantId } : {};
  };

  const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

  const toValidateProgress = (jobStatus: string): number => {
    switch (jobStatus) {
      case 'UPLOADED':
        return 25;
      case 'PARSING':
        return 45;
      case 'VALIDATING':
        return 75;
      case 'READY':
        return 100;
      case 'FAILED':
        return 100;
      default:
        return 30;
    }
  };

  const toImportProgress = (jobStatus: string): number => {
    switch (jobStatus) {
      case 'COMMITTING':
        return 60;
      case 'COMPLETED':
        return 100;
      case 'FAILED':
        return 100;
      default:
        return 30;
    }
  };

  const fetchImportJob = async (jobId: string) => {
    const res = await fetch(`/api/v2/import/jobs/${jobId}`, {
      headers: buildTenantHeaders(),
    });
    if (!res.ok) {
      const errorData = await res.json().catch(() => ({ detail: '取得匯入狀態失敗' }));
      const message = typeof errorData.detail === 'string' ? errorData.detail : (errorData.detail?.detail || '取得匯入狀態失敗');
      throw new Error(message);
    }
    return res.json();
  };

  const handleFiles = (fileList: FileList | null) => {
    if (!fileList) return;

    const newFiles: UploadedFile[] = [];
    Array.from(fileList).forEach((file) => {
      if (!file.name.toLowerCase().endsWith(".csv")) {
        showToast("error", "僅支援 csv 檔案類型");
        return;
      }
      
      // 檢查是否重複上傳
      if (files.some(f => f.name === file.name) || newFiles.some(f => f.name === file.name)) {
        showToast("info", `檔案 ${file.name} 已存在列表中，略過上傳`);
        return;
      }

      if (file.size > MAX_SIZE_BYTES) {
        showToast("error", "檔案大小超過 10MB 限制");
        return;
      }
      const type = detectFileType(file.name);
      const lotNo =
        type === "P1" || type === "P2" ? deriveLotNoFromFilename(file.name) : "";

      const id = `${file.name}-${Date.now()}-${Math.random().toString(36).slice(2)}`;
      newFiles.push({
        id,
        file,
        name: file.name,
        size: file.size,
        type,
        lotNo,
        status: "uploaded",
        uploadProgress: 100, // 本地成功就視為100%
        validateProgress: 0,
        importProgress: 0,
        expanded: true, // 默認上傳完畢直接展開
        csvData: undefined,
        hasUnsavedChanges: false,
        processId: undefined,
        isValidated: false,
        validationErrors: undefined,
      });
    });

    if (newFiles.length) {
      setFiles((prev) => [...prev, ...newFiles]);
      showToast("success", `已加入 ${newFiles.length} 個檔案`);
    }
  };

  const buildCsvText = (csv: CsvData): string => {
    const escapeCell = (cell: string) => {
      const value = cell ?? "";
      if (/[\r\n,"]/.test(value)) {
        return `"${value.replace(/"/g, '""')}"`;
      }
      return value;
    };

    const lines: string[] = [];
    lines.push(csv.headers.map((c) => escapeCell(c ?? "")).join(","));
    csv.rows.forEach((row) => {
      lines.push(row.map((c) => escapeCell(c ?? "")).join(","));
    });
    return lines.join("\n");
  };

  const handleValidate = async (fileId: string) => {
    const target = files.find((f) => f.id === fileId);
    if (!target) return;

    if (!EDIT_ENABLED && target.hasUnsavedChanges) {
      showToast("info", "此版本不提供編輯，請修正 CSV 後重新上傳");
      return;
    }
    
    // 允許重複驗證，特別是有錯誤的檔案
    // 不再阻止重複驗證，讓用戶可以修改後重新驗證

    setFiles((prev) =>
      prev.map((f) =>
        f.id === fileId
          ? { ...f, status: "validating", validateProgress: 10 }
          : f
      )
    );

    try {
      // v2：建立 import job，後端背景進行 parse + validate
      const formData = new FormData();
      formData.append('table_code', target.type);
      formData.append('allow_duplicate', 'true');
      formData.append('files', target.file, target.name);

      setFiles((prev) => prev.map((f) => (f.id === fileId ? { ...f, validateProgress: 25 } : f)));

      const createJobResponse = await fetch('/api/v2/import/jobs', {
        method: 'POST',
        headers: buildTenantHeaders(),
        body: formData,
      });

      if (!createJobResponse.ok) {
        const errorData = await createJobResponse.json().catch(() => ({ detail: '上傳失敗' }));
        const message = typeof errorData.detail === 'string' ? errorData.detail : (errorData.detail?.detail || '檔案上傳失敗');
        throw new Error(message);
      }

      const createdJob = await createJobResponse.json();
      
      setFiles((prev) =>
        prev.map((f) =>
          f.id === fileId ? { ...f, validateProgress: 40 } : f
        )
      );

      // 2. 解析CSV內容以供編輯
      const csvData = await parseCsv(target.file);

      setFiles((prev) =>
        prev.map((f) =>
          f.id === fileId ? { ...f, validateProgress: 90 } : f
        )
      );

      // 3. 更新檔案狀態
      setFiles((prev) =>
        prev.map((f) =>
          f.id === fileId
            ? {
                ...f,
                status: "validating",
                validateProgress: 50,
                csvData,
                expanded: true,
                // 沿用原欄位：把 v2 job_id 存到 processId（避免大改）
                processId: createdJob.id,
                isValidated: false,
                validationErrors: undefined,
                hasUnsavedChanges: false,
              }
            : f
        )
      );

      // 4. 輪詢 job 狀態直到 READY / FAILED
      const jobId = createdJob.id as string;
      let lastJob: any = createdJob;
      for (let i = 0; i < 120; i++) {
        await sleep(1000);
        lastJob = await fetchImportJob(jobId);

        setFiles((prev) =>
          prev.map((f) =>
            f.id === fileId
              ? {
                  ...f,
                  status: lastJob.status === 'READY' || lastJob.status === 'FAILED' ? 'validated' : 'validating',
                  validateProgress: toValidateProgress(lastJob.status),
                }
              : f
          )
        );

        if (lastJob.status === 'READY' || lastJob.status === 'FAILED') break;
      }

      if (!lastJob || (lastJob.status !== 'READY' && lastJob.status !== 'FAILED')) {
        throw new Error('驗證逾時，請稍後再試或重新驗證');
      }

      if (lastJob.status === 'FAILED') {
        const message = lastJob.error_summary?.error || '驗證失敗';
        setFiles((prev) =>
          prev.map((f) =>
            f.id === fileId
              ? {
                  ...f,
                  status: 'validated',
                  isValidated: true,
                  validationErrors: [{ row_index: 0, field: 'system', error_code: 'FAILED', message }],
                }
              : f
          )
        );
        showToast('error', `${target.name} 驗證失敗：${message}`);
        return;
      }

      const totalRows = Number(lastJob.total_rows || 0);
      const errorCount = Number(lastJob.error_count || 0);

      if (errorCount > 0) {
        // 只在有錯誤時抓 errors（避免大量資料傳輸）
        const errorsRes = await fetch(`/api/v2/import/jobs/${jobId}/errors?page=1&page_size=200`, {
          headers: buildTenantHeaders(),
        });
        const errorRows = errorsRes.ok ? await errorsRes.json() : [];

        const flattenedErrors = (Array.isArray(errorRows) ? errorRows : []).flatMap((row: any) => {
          const rowIndex0 = Math.max(0, Number(row.row_index || 1) - 1); // v2 staging row_index 是 1-based
          const errs = Array.isArray(row.errors) ? row.errors : [];
          if (errs.length === 0) {
            return [{ row_index: rowIndex0, field: 'row', error_code: 'INVALID', message: 'Row is invalid' }];
          }
          return errs.map((e: any) => ({
            row_index: rowIndex0,
            field: String(e.field ?? e.column ?? 'row'),
            error_code: String(e.error_code ?? 'INVALID'),
            message: String(e.message ?? JSON.stringify(e)),
          }));
        });

        setFiles((prev) =>
          prev.map((f) =>
            f.id === fileId
              ? {
                  ...f,
                  status: 'validated',
                  validateProgress: 100,
                  isValidated: true,
                  validationErrors: flattenedErrors,
                  hasUnsavedChanges: false,
                }
              : f
          )
        );

        showToast(
          'error',
          `${target.name} 驗證完成：共 ${totalRows} 行，無效 ${errorCount} 行。此版本不提供編輯，請修正 CSV 後重新上傳。`
        );
      } else {
        setFiles((prev) =>
          prev.map((f) =>
            f.id === fileId
              ? {
                  ...f,
                  status: 'validated',
                  validateProgress: 100,
                  isValidated: true,
                  validationErrors: [],
                  hasUnsavedChanges: false,
                }
              : f
          )
        );

        showToast('success', `${target.name} 驗證通過：共 ${totalRows} 行全部有效`);
      }
      
    } catch (err) {
      console.error('驗證錯誤:', err);
      const errorMessage = err instanceof Error ? err.message : '驗證過程發生錯誤';
      showToast("error", errorMessage);
      
      setFiles((prev) =>
        prev.map((f) =>
          f.id === fileId 
            ? { ...f, status: "uploaded", validateProgress: 0 } 
            : f
        )
      );
    }
  };

  const updateCell = (
    fileId: string,
    rowIndex: number,
    colIndex: number,
    value: string
  ) => {
    if (!EDIT_ENABLED) return;
    setFiles((prev) =>
      prev.map((f) => {
        if (f.id !== fileId || !f.csvData) return f;
        const rows = f.csvData.rows.map((row, rIdx) =>
          rIdx === rowIndex
            ? row.map((cell, cIdx) => (cIdx === colIndex ? value : cell))
            : row
        );
        return {
          ...f,
          csvData: { ...f.csvData, rows },
          hasUnsavedChanges: true,
        };
      })
    );
  };

  const handleSaveChanges = async (fileId: string) => {
    if (!EDIT_ENABLED) {
      showToast("info", "此版本上傳流程不提供編輯，請修正 CSV 後重新上傳");
      return;
    }
    const target = files.find((f) => f.id === fileId);
    if (!target || !target.csvData || !target.hasUnsavedChanges) return;

    if (!target.processId) {
      showToast("error", "缺少 process_id，請先驗證檔案後再儲存修改");
      return;
    }

    try {
      const csv_text = buildCsvText(target.csvData);

      const res = await fetch(`/api/upload/${target.processId}/content`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ csv_text }),
      });

      if (!res.ok) {
        const errorData = await res.json().catch(() => ({ detail: '儲存失敗' }));
        const errorMessage = typeof errorData.detail === 'string'
          ? errorData.detail
          : errorData.detail?.detail || '儲存失敗';
        throw new Error(errorMessage);
      }

      const result = await res.json();
      
      setFiles((prev) =>
        prev.map((f) =>
          f.id === fileId
            ? {
                ...f,
                hasUnsavedChanges: false,
                isValidated: true,
                status: "validated",
                // 後端只回 sample_errors（前10筆），但足夠用來決定是否可匯入
                validationErrors: result.sample_errors || [],
              }
            : f
        )
      );

      if (result.invalid_rows && result.invalid_rows > 0) {
        showToast("info", `修改已儲存，但仍有 ${result.invalid_rows} 行無效，請繼續修正`);
      } else {
        showToast("success", "修改已儲存，且驗證通過");
      }
    } catch (err) {
      console.error('儲存錯誤:', err);
      const errorMessage = err instanceof Error ? err.message : '儲存修改時發生錯誤';
      showToast("error", errorMessage);
    }
  };

  const handleToggleExpand = (fileId: string) => {
    setFiles((prev) =>
      prev.map((f) =>
        f.id === fileId ? { ...f, expanded: !f.expanded } : f
      )
    );
  };

  // 批次匯入所有已驗證的檔案
  const handleBatchImportClick = () => {
    const validatedFiles = files.filter(f => 
      f.status === "validated" && 
      f.processId && 
      (!f.validationErrors || f.validationErrors.length === 0)
    );
    
    if (validatedFiles.length === 0) {
      const filesWithErrors = files.filter(f => 
        f.status === "validated" && 
        f.validationErrors && 
        f.validationErrors.length > 0
      );
      const unvalidatedFiles = files.filter(f => f.status === "uploaded");
      
      if (filesWithErrors.length > 0) {
        showToast("error", `有 ${filesWithErrors.length} 個檔案包含驗證錯誤，請修正後再匯入`);
      } else if (unvalidatedFiles.length > 0) {
        showToast("error", `有 ${unvalidatedFiles.length} 個檔案尚未驗證，請先驗證檔案`);
      } else {
        showToast("error", "沒有已驗證的檔案可供匯入");
      }
      return;
    }
    
    // 顯示確認彈窗
    setShowBatchImportConfirm(true);
  };

  const performBatchImport = async () => {
    setShowBatchImportConfirm(false);
    
    const totalFiles = files.length;
    
    // 只允許匯入沒有驗證錯誤的檔案
    const validatedFiles = files.filter(f => 
      f.status === "validated" && 
      f.processId && 
      (!f.validationErrors || f.validationErrors.length === 0)
    );
    
    const filesWithErrors = files.filter(f => 
      f.status === "validated" && 
      f.validationErrors && 
      f.validationErrors.length > 0
    );
    
    const unvalidatedFiles = files.filter(f => f.status === "uploaded");
    
    if (validatedFiles.length === 0) {
      if (filesWithErrors.length > 0) {
        showToast("error", `有 ${filesWithErrors.length} 個檔案包含驗證錯誤，請修正後再匯入`);
      } else if (unvalidatedFiles.length > 0) {
        showToast("error", `有 ${unvalidatedFiles.length} 個檔案尚未驗證，請先驗證檔案`);
      } else {
        showToast("error", "沒有已驗證的檔案可供匯入");
      }
      return;
    }
    
    // 區分單檔和多檔情況
    const isSingleFile = totalFiles === 1;
    
    if (!isSingleFile && filesWithErrors.length > 0) {
      showToast("info", `多檔上傳：已跳過 ${filesWithErrors.length} 個有錯誤的檔案，只匯入 ${validatedFiles.length} 個有效檔案`);
    } else if (isSingleFile) {
      showToast("info", "開始匯入檔案...");
    } else {
      showToast("info", `開始批次匯入 ${validatedFiles.length} 個檔案...`);
    }

    // 設置所有檔案為匯入中狀態
    setFiles(prev => 
      prev.map(f => 
        validatedFiles.some(vf => vf.id === f.id)
          ? { ...f, status: "importing", importProgress: 10 }
          : f
      )
    );

    try {
      let totalImported = 0;
      
      for (const [index, file] of validatedFiles.entries()) {
        const progress = Math.round((index / validatedFiles.length) * 80) + 10;
        
        setFiles(prev => 
          prev.map(f => 
            f.id === file.id 
              ? { ...f, importProgress: progress }
              : f
          )
        );

        const jobId = file.processId as string;
        const commitResponse = await fetch(`/api/v2/import/jobs/${jobId}/commit`, {
          method: 'POST',
          headers: buildTenantHeaders(),
        });

        if (!commitResponse.ok) {
          const errorData = await commitResponse.json().catch(() => ({ detail: '匯入失敗' }));
          const errorMessage = typeof errorData.detail === 'string'
            ? errorData.detail
            : errorData.detail?.detail || '匯入失敗';
          throw new Error(`檔案 ${file.name} 匯入失敗: ${errorMessage}`);
        }

        // 輪詢到 COMPLETED / FAILED
        let committedJob = await commitResponse.json();
        for (let i = 0; i < 300; i++) {
          await sleep(1000);
          committedJob = await fetchImportJob(jobId);
          setFiles(prev => prev.map(f => f.id === file.id ? { ...f, importProgress: toImportProgress(committedJob.status) } : f));
          if (committedJob.status === 'COMPLETED' || committedJob.status === 'FAILED') break;
        }

        if (committedJob.status !== 'COMPLETED') {
          const message = committedJob.error_summary?.error || '匯入失敗';
          throw new Error(`檔案 ${file.name} 匯入失敗: ${message}`);
        }

        totalImported += Number(committedJob.total_rows || 0);

        setFiles(prev => 
          prev.map(f => 
            f.id === file.id 
              ? { ...f, status: "imported", importProgress: 100 }
              : f
          )
        );
      }
      
      showToast("success", 
        `${isSingleFile ? '檔案' : '批次'}匯入完成！共匯入 ${validatedFiles.length} 個檔案，總計 ${totalImported} 筆資料`
      );
      
      // 處理匯入後的檔案清理 - 統一只移除已匯入的檔案，不區分單檔或多檔
      setTimeout(() => {
        // 使用 ref 獲取最新狀態
        const currentFiles = filesRef.current;
        const remainingFiles = currentFiles.filter(f => 
          !validatedFiles.some(vf => vf.id === f.id)
        );

        // 移除已匯入的檔案，保留其他檔案（包括有錯誤的或待驗證的）
        setFiles(remainingFiles);
        
        if (remainingFiles.length > 0) {
          const errorCount = remainingFiles.filter(f => 
            f.validationErrors && f.validationErrors.length > 0
          ).length;
          const unvalidatedCount = remainingFiles.filter(f => f.status === "uploaded").length;
          
          let message = `已匯入檔案已移除，剩餘 ${remainingFiles.length} 個檔案：`;
          if (errorCount > 0) message += ` ${errorCount} 個需修正錯誤`;
          if (unvalidatedCount > 0) {
            if (errorCount > 0) message += "，";
            message += ` ${unvalidatedCount} 個待驗證`;
          }
          showToast("info", message);
        } else {
          showToast("info", "所有檔案處理完成，可以繼續上傳新檔案");
        }
      }, 2000);
      
    } catch (err) {
      console.error('批次匯入錯誤:', err);
      const errorMessage = err instanceof Error ? err.message : '批次匯入時發生錯誤';
      showToast("error", errorMessage);
      
      // 重置匯入狀態
      setFiles(prev => 
        prev.map(f => 
          validatedFiles.some(vf => vf.id === f.id)
            ? { ...f, status: "validated", importProgress: 0 }
            : f
        )
      );
    }
  };

  const performImport = async () => {
    if (!confirmTargetId) return;
    const id = confirmTargetId;
    setConfirmTargetId(null);

    const target = files.find((f) => f.id === id);
    if (!target || !target.processId) {
      showToast("error", "找不到檔案或缺少 job_id");
      return;
    }

    setFiles((prev) =>
      prev.map((f) =>
        f.id === id
          ? { ...f, status: "importing", importProgress: 20 }
          : f
      )
    );

    try {
      const jobId = target.processId as string;
      const commitResponse = await fetch(`/api/v2/import/jobs/${jobId}/commit`, {
        method: 'POST',
        headers: buildTenantHeaders(),
      });

      setFiles((prev) =>
        prev.map((f) =>
          f.id === id ? { ...f, importProgress: 60 } : f
        )
      );

      if (!commitResponse.ok) {
        const errorData = await commitResponse.json().catch(() => ({ detail: '匯入失敗' }));
        const errorMessage = typeof errorData.detail === 'string' 
          ? errorData.detail 
          : errorData.detail?.detail || '資料匯入失敗';
        throw new Error(errorMessage);
      }

      // 輪詢到 COMPLETED / FAILED
      let committedJob = await commitResponse.json();
      for (let i = 0; i < 300; i++) {
        await sleep(1000);
        committedJob = await fetchImportJob(jobId);
        setFiles((prev) =>
          prev.map((f) => (f.id === id ? { ...f, importProgress: toImportProgress(committedJob.status) } : f))
        );
        if (committedJob.status === 'COMPLETED' || committedJob.status === 'FAILED') break;
      }

      if (committedJob.status !== 'COMPLETED') {
        const message = committedJob.error_summary?.error || '資料匯入失敗';
        throw new Error(message);
      }

      setFiles((prev) =>
        prev.map((f) =>
          f.id === id
            ? { ...f, status: "imported", importProgress: 100 }
            : f
        )
      );

      showToast("success", 
        `${target.name} 匯入完成`
      );
      
      // 延遲後根據檔案數量決定行為
      setTimeout(() => {
        // 使用 ref 獲取最新狀態，避免在 updater 中執行副作用
        const currentFiles = filesRef.current;
        const remainingFiles = currentFiles.filter(f => f.id !== id);
        
        // 如果原本只有一個檔案，重置整個頁面
        if (currentFiles.length === 1) {
          showToast("info", "頁面已重置，可以繼續上傳新檔案");
          setFiles([]);
        } 
        // 如果有多個檔案，只移除已匯入的檔案
        else {
          showToast("info", `已移除匯入檔案，剩餘 ${remainingFiles.length} 個檔案`);
          setFiles(remainingFiles);
        }
      }, 2000);
      
    } catch (err) {
      console.error('匯入錯誤:', err);
      const errorMessage = err instanceof Error ? err.message : '匯入時發生錯誤';
      showToast("error", errorMessage);
      
      setFiles((prev) =>
        prev.map((f) =>
          f.id === id ? { ...f, status: "validated", importProgress: 0 } : f
        )
      );
    }
  };

  const handleRemoveFile = (fileId: string) => {
    setFiles((prev) => prev.filter((f) => f.id !== fileId));
  };

  return (
    <div className="upload-page">
      {/* 拖曳/選擇檔案區 */}
      <section className="upload-drop-section">
        <FileDropArea onFiles={handleFiles} />
      </section>

      {/* 已上傳檔案列表 */}
      <section className="uploaded-list-section">
        {!EDIT_ENABLED && (
          <div style={{
            margin: '8px 0 12px 0',
            padding: '10px 12px',
            border: '1px solid #fde68a',
            backgroundColor: '#fffbeb',
            borderRadius: '6px',
            color: '#92400e',
            fontSize: '14px'
          }}>
            此版本上傳流程不提供編輯；如需修正請修改 CSV 後重新上傳。
          </div>
        )}
        <div className="section-header">
          <h2 className="section-title">已上傳檔案</h2>
          {files.length > 0 && (
            <div className="batch-actions">
              {(() => {
                const validatedFiles = files.filter(f => f.status === "validated" && f.processId);
                const validFilesWithoutErrors = validatedFiles.filter(f => !f.validationErrors || f.validationErrors.length === 0);
                const filesWithErrors = validatedFiles.filter(f => f.validationErrors && f.validationErrors.length > 0);
                const isDisabled = validFilesWithoutErrors.length === 0;
                
                let buttonText = `批次匯入全部 (${validFilesWithoutErrors.length})`;
                let buttonTitle = "";
                
                if (isDisabled) {
                  if (filesWithErrors.length > 0) {
                    buttonTitle = `有 ${filesWithErrors.length} 個檔案包含驗證錯誤，請修正後再匯入`;
                  } else {
                    buttonTitle = "沒有已驗證的檔案可供匯入";
                  }
                } else {
                  buttonTitle = `批次匯入 ${validFilesWithoutErrors.length} 個有效檔案`;
                  if (filesWithErrors.length > 0) {
                    buttonTitle += `（將跳過 ${filesWithErrors.length} 個有錯誤的檔案）`;
                  }
                }
                
                return (
                  <button
                    className={`btn-primary batch-import-btn ${isDisabled ? "btn-primary--disabled" : ""}`}
                    onClick={handleBatchImportClick}
                    disabled={isDisabled}
                    title={buttonTitle}
                  >
                    {buttonText}
                    {filesWithErrors.length > 0 && (
                      <span style={{ color: '#f59e0b', marginLeft: '8px' }}>
                         {filesWithErrors.length} 個錯誤
                      </span>
                    )}
                  </button>
                );
              })()}
            </div>
          )}
        </div>
        
        {files.length === 0 && (
          <p className="section-empty">尚未上傳任何檔案</p>
        )}

        <div className="uploaded-list">
          {files.map((f) => (
            <UploadedFileCard
              key={f.id}
              file={f}
              onValidate={() => handleValidate(f.id)}
              onSaveChanges={() => handleSaveChanges(f.id)}
              onToggleExpand={() => handleToggleExpand(f.id)}
              onRemove={() => handleRemoveFile(f.id)}
              onImport={(fileId) => setConfirmTargetId(fileId)}
              onCellChange={updateCell}
            />
          ))}
        </div>
      </section>

      <Modal
        open={confirmTargetId !== null}
        title=" 是否確認上傳"
        onClose={() => setConfirmTargetId(null)}
        onConfirm={performImport}
        confirmText="確認匯入"
      >
        <p>匯入資料庫中後，資料將無法直接還原，請再次確認內容是否正確。</p>
      </Modal>

      <Modal
        open={showBatchImportConfirm}
        title=" 是否確認批次匯入"
        onClose={() => setShowBatchImportConfirm(false)}
        onConfirm={performBatchImport}
        confirmText="確認批次匯入"
      >
        {(() => {
          const validFilesWithoutErrors = files.filter(f => 
            f.status === "validated" && 
            f.processId && 
            (!f.validationErrors || f.validationErrors.length === 0)
          );
          const filesWithErrors = files.filter(f => 
            f.status === "validated" && 
            f.validationErrors && 
            f.validationErrors.length > 0
          );
          
          return (
            <div>
              <p style={{ marginBottom: '12px' }}>
                即將批次匯入 <strong style={{ color: '#059669' }}>{validFilesWithoutErrors.length}</strong> 個已驗證的檔案到資料庫。
              </p>
              <p style={{ marginBottom: '12px', color: '#dc2626', fontWeight: 'bold' }}>
                匯入後資料將無法直接還原，請再次確認所有檔案內容是否正確。
              </p>
              {filesWithErrors.length > 0 && (
                <p style={{ 
                  padding: '8px 12px', 
                  backgroundColor: '#fef2f2', 
                  border: '1px solid #fecaca',
                  borderRadius: '4px',
                  color: '#7f1d1d',
                  fontSize: '14px'
                }}>
                   注意：有 {filesWithErrors.length} 個檔案因包含錯誤將被跳過
                </p>
              )}
              {validFilesWithoutErrors.length > 0 && (
                <div style={{ marginTop: '12px' }}>
                  <p style={{ fontWeight: 'bold', marginBottom: '8px' }}>待匯入檔案：</p>
                  <ul style={{ margin: 0, paddingLeft: '20px', fontSize: '14px' }}>
                    {validFilesWithoutErrors.map(f => (
                      <li key={f.id} style={{ marginBottom: '4px' }}>
                        <span style={{ color: '#6366f1', fontWeight: 'bold' }}>{f.type}</span> - {f.name}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          );
        })()}
      </Modal>
    </div>
  );
}

/* ------------ 子元件：拖曳上傳區 ------------ */

interface FileDropAreaProps {
  onFiles: (files: FileList | null) => void;
}

function FileDropArea({ onFiles }: FileDropAreaProps) {
  const [dragging, setDragging] = useState(false);

  const handleDrop: React.DragEventHandler<HTMLDivElement> = (e) => {
    e.preventDefault();
    setDragging(false);
    onFiles(e.dataTransfer.files);
  };

  const handleDragOver: React.DragEventHandler<HTMLDivElement> = (e) => {
    e.preventDefault();
    setDragging(true);
  };

  const handleDragLeave: React.DragEventHandler<HTMLDivElement> = (e) => {
    e.preventDefault();
    setDragging(false);
  };

  const handleChange: React.ChangeEventHandler<HTMLInputElement> = (e) => {
    onFiles(e.target.files);
    e.target.value = "";
  };

  return (
    <div className="upload-drop-wrapper">
      <div
        className={`upload-drop-area ${
          dragging ? "upload-drop-area--dragging" : ""
        }`}
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
      >
        <div className="upload-drop-icon">⬆</div>
        <p className="upload-drop-main-text">拖曳上傳或是選擇檔案</p>
        <p className="upload-drop-sub-text">
          僅支援 csv 檔案類型，檔案大小限制 10MB
        </p>
        <label className="upload-drop-button">
          選擇檔案
          <input type="file" accept=".csv" multiple onChange={handleChange} />
        </label>
      </div>
    </div>
  );
}

/* ------------ 子元件：已上傳檔案卡片 + CSV 編輯 ------------ */

interface UploadedFileCardProps {
  file: UploadedFile;
  onValidate: () => void;
  onSaveChanges: () => void;
  onToggleExpand: () => void;
  onRemove: () => void;
  onImport: (fileId: string) => void;
  onCellChange: (
    fileId: string,
    rowIndex: number,
    colIndex: number,
    value: string
  ) => void;
}

function UploadedFileCard({
  file,
  onValidate,
  onSaveChanges,
  onToggleExpand,
  onRemove,
  onImport,
  onCellChange,
}: UploadedFileCardProps) {
  
  // 驗證按鈕是否可用：未驗證過且不在驗證中
  const disabledValidate = 
    file.status === "validating" || file.status === "importing";
  
  // 檢查檔案是否有驗證錯誤
  const hasValidationErrors = file.validationErrors && file.validationErrors.length > 0;
    
  // 儲存按鈕是否可用：必須有CSV資料且有未儲存變更
  const disabledSave =
    !EDIT_ENABLED || !file.csvData || !file.hasUnsavedChanges;

  return (
    <div className="uploaded-card">
      <div className="uploaded-card__header">
        <div className="uploaded-card__info">
          <div className="uploaded-card__filename">
            <span className="filetype-tag">{file.type}</span>
            {file.name}
            {hasValidationErrors && file.validationErrors && (
              <span 
                className="error-indicator" 
                style={{
                  marginLeft: '8px',
                  color: '#dc2626',
                  fontWeight: 'bold',
                  fontSize: '14px',
                  cursor: 'pointer',
                  textDecoration: 'underline'
                }}
                title={`發現 ${file.validationErrors.length} 個驗證錯誤，點擊展開查看詳情`}
                onClick={() => {
                  if (!file.expanded) {
                    onToggleExpand();
                  }
                  // 添加視覺提示，滾動到錯誤區域
                  setTimeout(() => {
                    const errorSection = document.querySelector('.validation-errors-section');
                    if (errorSection) {
                      errorSection.scrollIntoView({ behavior: 'smooth', block: 'center' });
                    }
                  }, 100);
                }}
              >
                 {file.validationErrors.length} 個錯誤
              </span>
            )}
            {file.isValidated && !hasValidationErrors && (
              <span 
                className="success-indicator"
                style={{
                  marginLeft: '8px',
                  color: '#059669',
                  fontWeight: 'bold',
                  fontSize: '14px'
                }}
                title="驗證通過"
              >
                 驗證通過
              </span>
            )}
          </div>
          <div className="uploaded-card__meta">
            <span>{(file.size / 1024).toFixed(1)} KB</span>
            {file.lotNo && <span>Lot No: {file.lotNo}</span>}
          </div>
        </div>
        <div className="uploaded-card__actions">
          <button className="icon-button" onClick={onRemove} title="移除">
            ✕
          </button>
        </div>
      </div>

      <div className="uploaded-card__body">
        <div className="uploaded-card__status">
          {file.status === "uploaded" && <span>待驗證</span>}
          {file.status === "validating" && (
            <span>驗證中...</span>
          )}
          {file.status === "validated" && <span>已驗證</span>}
          {file.status === "importing" && (
            <span>匯入資料庫中...請稍後...</span>
          )}
          {file.status === "imported" && <span>已完成匯入</span>}
        </div>

        {file.status === "validating" && (
          <ProgressBar value={file.validateProgress} label="驗證進度" />
        )}
        {file.status === "importing" && (
          <ProgressBar value={file.importProgress} label="匯入進度" />
        )}

        <div className="uploaded-card__buttons">
          <button
            className={`btn-secondary ${
              disabledValidate ? "btn-secondary--disabled" : ""
            }`}
            onClick={onValidate}
            disabled={disabledValidate}
            title={
              file.status === "validating" 
                ? "驗證中..." 
                : file.status === "importing"
                ? "匯入中..."
                : hasValidationErrors
                ? "發現驗證錯誤，點擊重新驗證"
                : file.isValidated && !hasValidationErrors
                ? "驗證通過，點擊可重新驗證"
                : "點擊驗證檔案"
            }
          >
            {file.status === "validating" 
              ? "驗證中..." 
              : hasValidationErrors 
              ? "重新驗證" 
              : file.isValidated 
              ? "已驗證 ✓" 
              : "驗證檔案"
            }
          </button>

          <button
            className={`btn-secondary ${
              disabledSave ? "btn-secondary--disabled" : ""
            }`}
            onClick={onSaveChanges}
            disabled={disabledSave}
            title={
              !EDIT_ENABLED
                ? "此版本不提供編輯，請修正 CSV 後重新上傳"
                : !file.csvData
                ? "請先驗證檔案"
                : !file.hasUnsavedChanges
                ? "沒有未儲存的變更"
                : "儲存修改"
            }
          >
            儲存修改
          </button>

          {/* 個別檔案匯入按鈕 */}
          {file.status === "validated" && !hasValidationErrors && (
            <button
              className="btn-primary"
              onClick={() => onImport(file.id)}
              title="匯入此檔案到資料庫"
            >
              匯入檔案
            </button>
          )}

          {/* 已驗證檔案顯示準備好的狀態 */}
          {file.status === "validated" && !hasValidationErrors && (
            <span className="status-badge status-badge--ready">
              ✓ 準備匯入
            </span>
          )}
          
          {/* 有驗證錯誤時顯示錯誤狀態 */}
          {file.status === "validated" && hasValidationErrors && (
            <span className="status-badge" style={{
              backgroundColor: '#fef2f2',
              color: '#dc2626',
              border: '1px solid #fecaca'
            }}>
               需要修正
            </span>
          )}

          <button className="btn-text" onClick={onToggleExpand}>
            {file.expanded ? "收起" : "展開"} CSV 內容
          </button>
        </div>
      </div>

      {file.expanded && file.csvData && (
        <CsvEditor
          file={file}
          csv={file.csvData}
          onCellChange={onCellChange}
        />
      )}
    </div>
  );
}

/* ------------ 子元件：CSV 編輯器 ------------ */

interface ValidationError {
  row_index: number;
  field: string;
  error_code: string;
  message: string;
}

interface CsvEditorProps {
  file: UploadedFile;
  csv: CsvData;
  onCellChange: (
    fileId: string,
    rowIndex: number,
    colIndex: number,
    value: string
  ) => void;
}

function CsvEditor({ file, csv, onCellChange }: CsvEditorProps) {
  // 創建錯誤映射表，以便快速查找特定行/列的錯誤
  const errorMap = new Map<string, ValidationError>();
  if (file.validationErrors) {
    file.validationErrors.forEach((error: any) => {
      const key = `${error.row_index}_${error.field}`;
      errorMap.set(key, error);
    });
  }

  // 檢查特定單元格是否有錯誤
  const getCellError = (rowIndex: number, colIndex: number): ValidationError | undefined => {
    const fieldName = csv.headers[colIndex];
    const key = `${rowIndex}_${fieldName}`;
    return errorMap.get(key) || errorMap.get(`${rowIndex}_${fieldName.toLowerCase()}`);
  };

  return (
    <div className="csv-editor">
      <div className="csv-editor__header">
        <span>
          {EDIT_ENABLED ? 'CSV 內容編輯' : 'CSV 內容預覽'} - {file.name}（共 {csv.rows.length} 行，{csv.headers.length}{" "}
          個欄位）
        </span>
        {file.validationErrors && file.validationErrors.length > 0 && (
          <div className="csv-editor__error-summary">
            <span style={{ color: '#dc2626', fontWeight: 'bold' }}>
              發現 {file.validationErrors.length} 個驗證錯誤
            </span>
          </div>
        )}
      </div>

      <div className="csv-editor__table-wrapper">
        <table className="csv-editor__table">
          <thead>
            <tr>
              {csv.headers.map((h, idx) => (
                <th
                  key={idx}
                  style={{ width: `${csv.colWidths[idx]}px` }}
                >
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {csv.rows.map((row, rIdx) => {
              const hasRowError = file.validationErrors?.some((error: any) => error.row_index === rIdx);
              
              return (
                <tr 
                  key={rIdx}
                  style={hasRowError ? { backgroundColor: '#fef2f2' } : {}}
                >
                  {row.map((cell, cIdx) => {
                    const cellError = getCellError(rIdx, cIdx);
                    const hasError = !!cellError;
                    
                    return (
                      <td
                        key={cIdx}
                        style={{ 
                          width: `${csv.colWidths[cIdx]}px`,
                          position: 'relative'
                        }}
                        title={hasError ? `錯誤：${cellError.message}` : ''}
                      >
                        <input
                          className={`csv-editor__cell-input ${hasError ? 'csv-editor__cell-input--error' : ''}`}
                          value={cell}
                          readOnly={!EDIT_ENABLED}
                          onChange={(e) => {
                            if (!EDIT_ENABLED) return;
                            onCellChange(file.id, rIdx, cIdx, e.target.value);
                          }}
                          style={hasError ? {
                            backgroundColor: '#fecaca',
                            borderColor: '#dc2626',
                            color: '#dc2626'
                          } : {}}
                        />
                        {hasError && (
                          <div
                            className="csv-editor__error-indicator"
                            style={{
                              position: 'absolute',
                              top: '2px',
                              right: '2px',
                              width: '8px',
                              height: '8px',
                              backgroundColor: '#dc2626',
                              borderRadius: '50%',
                              fontSize: '10px',
                              color: 'white',
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'center',
                              cursor: 'help'
                            }}
                            title={`錯誤程式碼: ${cellError.error_code}\n${cellError.message}`}
                          >
                            !
                          </div>
                        )}
                      </td>
                    );
                  })}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <div className="csv-editor__hint">
        <p style={{ margin: '0 0 4px 0', fontSize: '0.75rem', color: '#6b7280' }}>
          {EDIT_ENABLED
            ? '提示：點擊任意儲存格即可直接編輯內容'
            : '提示：此版本不提供編輯；如需修正請修改 CSV 後重新上傳'}
        </p>
        {file.validationErrors && file.validationErrors.length > 0 ? (
          <p style={{ margin: '0', fontSize: '0.75rem', color: '#dc2626', fontWeight: 'bold' }}>
             紅色高亮的單元格表示有驗證錯誤，將滑鼠懸停查看詳情。請修正 CSV 後重新上傳再驗證。
          </p>
        ) : (
          <p style={{ margin: '0', fontSize: '0.75rem', color: '#059669', fontWeight: 'bold' }}>
             所有資料驗證通過，可以匯入資料庫
          </p>
        )}
      </div>

      {/* 顯示驗證錯誤詳情 - 在CSV表格下方顯示 */}
      {file.validationErrors && file.validationErrors.length > 0 && (
        <div className="validation-errors-section" style={{
          backgroundColor: '#fef2f2',
          border: '2px solid #f87171',
          borderRadius: '8px',
          padding: '16px',
          margin: '12px 0 0 0',
          boxShadow: '0 2px 4px rgba(220, 38, 38, 0.1)'
        }}>
          <h4 style={{ color: '#dc2626', marginBottom: '12px', fontSize: '16px', fontWeight: 'bold' }}>
             驗證錯誤詳情 ({file.validationErrors.length} 個錯誤)
          </h4>
          <div className="error-list" style={{ maxHeight: '300px', overflowY: 'auto' }}>
            {file.validationErrors.slice(0, 10).map((error: any, index: number) => (
              <div 
                key={index} 
                className="error-item" 
                style={{
                  backgroundColor: '#ffffff',
                  border: '1px solid #f87171',
                  borderRadius: '4px',
                  padding: '8px 12px',
                  marginBottom: '8px',
                  fontSize: '14px'
                }}
              >
                <div style={{ color: '#dc2626', fontWeight: 'bold' }}>
                  第 {error.row_index + 1} 行 • {error.field} 欄位
                </div>
                <div style={{ color: '#7f1d1d', marginTop: '4px' }}>
                  錯誤程式碼: {error.error_code}
                </div>
                <div style={{ color: '#374151', marginTop: '4px' }}>
                  {error.message}
                </div>
              </div>
            ))}
            {file.validationErrors.length > 10 && (
              <div style={{ color: '#6b7280', fontStyle: 'italic', textAlign: 'center', padding: '8px' }}>
                ...還有 {file.validationErrors.length - 10} 個錯誤（請修正上述錯誤後重新驗證）
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
