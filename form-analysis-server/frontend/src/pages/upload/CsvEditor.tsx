import { useMemo, useCallback } from "react";
import { useTranslation } from "react-i18next";
import type { CsvData, UploadedFile } from "./types";
import { EDIT_ENABLED } from "./types";

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

export function CsvEditor({ file, csv, onCellChange }: CsvEditorProps) {
  const { t } = useTranslation();
  const termMap = useMemo(() => {
    const raw = t('專有名詞對照表', { returnObjects: true }) as Record<string, string> | string;
    if (!raw || typeof raw !== 'object') return {} as Record<string, string>;
    const out: Record<string, string> = {};
    for (const [key, value] of Object.entries(raw)) {
      out[String(key)] = String(value);
    }
    return out;
  }, [t]);
  const termMapLower = useMemo(() => {
    const out: Record<string, string> = {};
    for (const [key, value] of Object.entries(termMap)) {
      out[key.trim().toLowerCase()] = value;
    }
    return out;
  }, [termMap]);
  const getHeaderLabel = useCallback((header: string) => {
    const raw = String(header ?? '');
    if (!raw) return '';
    if (raw.trim().toLowerCase() === 'specification') {
      if (file.type === 'P1') return termMap['P1.Specification'] || 'P1.Specification';
      if (file.type === 'P2') return termMap['P2.Specification'] || 'Specification';
      if (file.type === 'P3') return termMap['P3.Specification'] || 'P3.Specification';
    }
    const direct = termMap[raw];
    if (direct) return direct;
    const normalized = raw.trim().toLowerCase();
    return termMapLower[normalized] || raw;
  }, [file.type, termMap, termMapLower]);

  // 創建錯誤映射表，以便快速查找特定行/列的錯誤
  const errorMap = new Map<string, ValidationError>();
  if (file.validationErrors) {
    file.validationErrors.forEach((error: any) => {
      const key = `${error.row_index}_${error.field}`;
      errorMap.set(key, error);
    });
  }

  const errorRowIndexSet = new Set<number>();
  if (Array.isArray(file.validationErrors)) {
    file.validationErrors.forEach((error: any) => {
      const idx = Number(error?.row_index);
      if (!Number.isNaN(idx)) errorRowIndexSet.add(idx);
    });
  }

  const displayRows = csv.rows
    .map((row, originalRowIndex) => ({ row, originalRowIndex }))
    .sort((a, b) => {
      const ae = errorRowIndexSet.has(a.originalRowIndex) ? 1 : 0;
      const be = errorRowIndexSet.has(b.originalRowIndex) ? 1 : 0;
      if (be !== ae) return be - ae;
      return a.originalRowIndex - b.originalRowIndex;
    });

  const getCellError = (rowIndex: number, colIndex: number): ValidationError | undefined => {
    const fieldName = csv.headers[colIndex];
    if (!fieldName) return undefined;
    const key = `${rowIndex}_${fieldName}`;
    return errorMap.get(key) || errorMap.get(`${rowIndex}_${fieldName.toLowerCase()}`);
  };

  return (
    <div className="csv-editor">
      <div className="csv-editor__header">
        <span>
          {t('upload.csvEditor.header', {
            title: EDIT_ENABLED ? t('upload.csvEditor.titleEdit') : t('upload.csvEditor.titlePreview'),
            fileName: file.name,
            rowCount: csv.rows.length,
            colCount: csv.headers.length,
          })}
        </span>
        {file.validationErrors && file.validationErrors.length > 0 && (
          <div className="csv-editor__error-summary">
            <span style={{ color: '#dc2626', fontWeight: 'bold' }}>
              {t('upload.csvEditor.errorSummary', { count: file.validationErrors.length })}
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
                  {getHeaderLabel(h)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {displayRows.map(({ row, originalRowIndex }) => {
              const hasRowError = errorRowIndexSet.has(originalRowIndex);

              return (
                <tr
                  key={originalRowIndex}
                  style={hasRowError ? { backgroundColor: '#fef2f2' } : {}}
                >
                  {row.map((cell, cIdx) => {
                    const cellError = getCellError(originalRowIndex, cIdx);
                    const hasError = !!cellError;
                    const isStar = csv.starCells?.has(`${originalRowIndex}_${cIdx}`);

                    return (
                      <td
                        key={cIdx}
                        style={{
                          width: `${csv.colWidths[cIdx] ?? 160}px`,
                          position: 'relative'
                        }}
                        title={hasError ? t('upload.csvEditor.cellErrorTitle', { message: cellError.message }) : isStar ? t('upload.csvEditor.starCellTitle', { defaultValue: '此欄位為顯著值 (原始資料含 * 或前後空格)' }) : ''}
                      >
                        <input
                          className={`csv-editor__cell-input ${hasError ? 'csv-editor__cell-input--error' : isStar ? 'csv-editor__cell-input--star' : ''}`}
                          value={cell ?? ''}
                          readOnly={!EDIT_ENABLED}
                          onChange={(e) => {
                            if (!EDIT_ENABLED) return;
                            onCellChange(file.id, originalRowIndex, cIdx, e.target.value);
                          }}
                          style={hasError ? {
                            backgroundColor: '#fecaca',
                            borderColor: '#dc2626',
                            color: '#dc2626'
                          } : isStar ? {
                            backgroundColor: '#fefce8',
                            borderColor: '#eab308',
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
                              title={`${t('upload.csvEditor.errorCodeLabel', { code: cellError.error_code })}\n${cellError.message}`}
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
            ? t('upload.csvEditor.hintEdit')
            : t('upload.csvEditor.hintPreview')}
        </p>
        {file.validationErrors && file.validationErrors.length > 0 ? (
          <p style={{ margin: '0', fontSize: '0.75rem', color: '#dc2626', fontWeight: 'bold' }}>
            {t('upload.csvEditor.hintHasErrors')}
          </p>
        ) : (
          <p style={{ margin: '0', fontSize: '0.75rem', color: '#059669', fontWeight: 'bold' }}>
            {t('upload.csvEditor.hintAllValid')}
          </p>
        )}
      </div>

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
            {t('upload.csvEditor.errorDetailsTitle', { count: file.validationErrors.length })}
          </h4>
          <div className="error-list" style={{ maxHeight: '300px', overflowY: 'auto' }}>
            {[...file.validationErrors]
              .sort((a: any, b: any) => {
                const ar = Number(a?.row_index ?? 0);
                const br = Number(b?.row_index ?? 0);
                if (ar !== br) return ar - br;
                const af = String(a?.field ?? '');
                const bf = String(b?.field ?? '');
                return af.localeCompare(bf);
              })
              .slice(0, 10)
              .map((error: any, index: number) => (
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
                  {t('upload.csvEditor.errorRowField', { row: error.row_index + 1, field: error.field })}
                </div>
                <div style={{ color: '#7f1d1d', marginTop: '4px' }}>
                  {t('upload.csvEditor.errorCodeLabel', { code: error.error_code })}
                </div>
                <div style={{ color: '#374151', marginTop: '4px' }}>
                  {error.message}
                </div>
              </div>
            ))}
            {file.validationErrors.length > 10 && (
              <div style={{ color: '#6b7280', fontStyle: 'italic', textAlign: 'center', padding: '8px' }}>
                {t('upload.csvEditor.moreErrorsHint', { count: file.validationErrors.length - 10 })}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
