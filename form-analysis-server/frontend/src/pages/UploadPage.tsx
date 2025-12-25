// src/pages/UploadPage.tsx
import { useState } from "react";
import { useToast } from "../components/common/ToastContext";
import { ProgressBar } from "../components/common/ProgressBar";
import { Modal } from "../components/common/Modal";
import "./../styles/upload-page.css";

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

  const handleFiles = (fileList: FileList | null) => {
    if (!fileList) return;

    const newFiles: UploadedFile[] = [];
    Array.from(fileList).forEach((file) => {
      if (!file.name.toLowerCase().endsWith(".csv")) {
        showToast("error", "僅支援 csv 檔案類型");
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

  const handleValidate = async (fileId: string) => {
    const target = files.find((f) => f.id === fileId);
    if (!target) return;
    
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
      // 1. 呼叫後端 API 進行檔案上傳和驗證
      const formData = new FormData();
      formData.append('file', target.file);

      setFiles((prev) =>
        prev.map((f) =>
          f.id === fileId ? { ...f, validateProgress: 30 } : f
        )
      );

      const uploadResponse = await fetch('/api/upload', {
        method: 'POST',
        body: formData,
      });

      if (!uploadResponse.ok) {
        const errorData = await uploadResponse.json().catch(() => ({ detail: '上傳失敗' }));
        throw new Error(errorData.detail || '檔案上傳失敗');
      }

      const uploadResult = await uploadResponse.json();
      
      setFiles((prev) =>
        prev.map((f) =>
          f.id === fileId ? { ...f, validateProgress: 60 } : f
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
                status: "validated",
                validateProgress: 100,
                csvData,
                expanded: uploadResult.sample_errors && uploadResult.sample_errors.length > 0 ? true : true, // 有錯誤時自動展開
                processId: uploadResult.process_id,
                isValidated: true,
                validationErrors: uploadResult.sample_errors || [],
                hasUnsavedChanges: false, // 剛驗證完成，無未儲存變更
              }
            : f
        )
      );

      // 顯示驗證結果
      if (uploadResult.invalid_rows > 0) {
        // 基本統計信息
        showToast("info", 
          `${target.name} 驗證完成：共 ${uploadResult.total_rows} 行，` +
          `有效 ${uploadResult.valid_rows} 行，無效 ${uploadResult.invalid_rows} 行`
        );

        // 如果有錯誤樣本，顯示詳細錯誤信息
        if (uploadResult.sample_errors && uploadResult.sample_errors.length > 0) {
          interface ValidationError {
            row_index: number;
            field: string;
            error_code: string;
            message: string;
          }
          
          const errorSummary = (uploadResult.sample_errors as ValidationError[]).slice(0, 3).map(error => 
            `第 ${error.row_index + 1} 行 ${error.field} 欄位：${error.message}`
          ).join('\n');
          
          const moreErrors = uploadResult.sample_errors.length > 3 ? 
            `\n...還有 ${uploadResult.sample_errors.length - 3} 個錯誤` : '';
          
          const fileType = target.name.match(/^P[123]/) ? target.name.match(/^P[123]/)?.[0] : '檔案';
          
          showToast("error", 
            `${fileType} 驗證錯誤詳情：\n${errorSummary}${moreErrors}\n請展開檔案查看完整錯誤列表並修正後重新驗證`
          );
        }
      } else {
        showToast("success", 
          `${target.name} 驗證完成：共 ${uploadResult.total_rows} 行全部有效`
        );
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
    const target = files.find((f) => f.id === fileId);
    if (!target || !target.csvData || !target.hasUnsavedChanges) return;

    try {
      // TODO: 實作將修改後的資料發送到後端的邏輯
      // 這裡可以發送修改後的 csvData 到後端進行暫存
      // 目前先在前端標記為已儲存
      
      setFiles((prev) =>
        prev.map((f) =>
          f.id === fileId ? { ...f, hasUnsavedChanges: false } : f
        )
      );
      showToast("success", "修改已儲存");
    } catch (err) {
      console.error('儲存錯誤:', err);
      showToast("error", "儲存修改時發生錯誤");
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

        const importResponse = await fetch('/api/import', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            process_id: file.processId,
          }),
        });

        if (!importResponse.ok) {
          const errorData = await importResponse.json().catch(() => ({ detail: '匯入失敗' }));
          const errorMessage = typeof errorData.detail === 'string' 
            ? errorData.detail 
            : errorData.detail?.detail || '匯入失敗';
          throw new Error(`檔案 ${file.name} 匯入失敗: ${errorMessage}`);
        }

        const importResult = await importResponse.json();
        totalImported += importResult.imported_rows || 0;

        setFiles(prev => 
          prev.map(f => 
            f.id === file.id 
              ? { ...f, status: "imported", importProgress: 100 }
              : f
          )
        );
      }

      const remainingFiles = files.filter(f => 
        !validatedFiles.some(vf => vf.id === f.id)
      );
      
      showToast("success", 
        `${isSingleFile ? '檔案' : '批次'}匯入完成！共匯入 ${validatedFiles.length} 個檔案，總計 ${totalImported} 筆資料`
      );
      
      // 處理匯入後的檔案清理 - 統一只移除已匯入的檔案，不區分單檔或多檔
      setTimeout(() => {
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
      showToast("error", "找不到檔案或缺少 process_id");
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
      // 呼叫後端匯入API
      const importResponse = await fetch('/api/import', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          process_id: target.processId,
        }),
      });

      setFiles((prev) =>
        prev.map((f) =>
          f.id === id ? { ...f, importProgress: 60 } : f
        )
      );

      if (!importResponse.ok) {
        const errorData = await importResponse.json().catch(() => ({ detail: '匯入失敗' }));
        const errorMessage = typeof errorData.detail === 'string' 
          ? errorData.detail 
          : errorData.detail?.detail || '資料匯入失敗';
        throw new Error(errorMessage);
      }

      const importResult = await importResponse.json();

      setFiles((prev) =>
        prev.map((f) =>
          f.id === id
            ? { ...f, status: "imported", importProgress: 100 }
            : f
        )
      );

      showToast("success", 
        `${target.name} 匯入完成：匯入 ${importResult.imported_rows} 行資料`
      );
      
      // 延遲後根據檔案數量決定行為
      setTimeout(() => {
        setFiles((currentFiles) => {
          const remainingFiles = currentFiles.filter(f => f.id !== id);
          
          // 如果原本只有一個檔案，重置整個頁面
          if (currentFiles.length === 1) {
            showToast("info", "頁面已重置，可以繼續上傳新檔案");
            return [];
          } 
          // 如果有多個檔案，只移除已匯入的檔案
          else {
            showToast("info", `已移除匯入檔案，剩餘 ${remainingFiles.length} 個檔案`);
            return remainingFiles;
          }
        });
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
    !file.csvData || !file.hasUnsavedChanges;

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
              !file.csvData 
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
          CSV 內容編輯 - {file.name}（共 {csv.rows.length} 行，{csv.headers.length}{" "}
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
                          onChange={(e) =>
                            onCellChange(
                              file.id,
                              rIdx,
                              cIdx,
                              e.target.value
                            )
                          }
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
          提示：點擊任意儲存格即可直接編輯內容
        </p>
        {file.validationErrors && file.validationErrors.length > 0 ? (
          <p style={{ margin: '0', fontSize: '0.75rem', color: '#dc2626', fontWeight: 'bold' }}>
             紅色高亮的單元格表示有驗證錯誤，將滑鼠懸停查看詳情。修正錯誤後請重新驗證檔案。
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
