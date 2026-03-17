import { useTranslation } from "react-i18next";
import { ProgressBar } from "../../components/common/ProgressBar";
import type { UploadedFile } from "./types";
import { EDIT_ENABLED } from "./types";
import { CsvEditor } from "./CsvEditor";

interface UploadedFileCardProps {
  file: UploadedFile;
  onValidate: () => void;
  onConvertPdf: () => void;
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

export function UploadedFileCard({
  file,
  onValidate,
  onConvertPdf,
  onSaveChanges,
  onToggleExpand,
  onRemove,
  onImport,
  onCellChange,
}: UploadedFileCardProps) {
  const { t } = useTranslation();

  const disabledValidate =
    file.status === "validating" || file.status === "importing";

  const hasValidationErrors = file.validationErrors && file.validationErrors.length > 0;

  const disabledSave =
    !EDIT_ENABLED || !file.csvData || !file.hasUnsavedChanges;

  const isPdf = file.type === 'PDF';

  const pdfStatusText = () => {
    if (!isPdf || !file.isValidated) return '';
    switch (file.pdfConvertStatus) {
      case 'queued':
      case 'uploading':
      case 'processing':
        return t('upload.pdf.status.converting');
      case 'completed':
        return t('upload.pdf.status.converted');
      case 'failed':
        return t('upload.pdf.status.convertFailed');
      case 'not_started':
      default:
        return t('upload.pdf.status.uploadedPendingConvert');
    }
  };

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
                title={t('upload.tooltips.validationErrorsExpand', { count: file.validationErrors.length })}
                onClick={() => {
                  if (!file.expanded) {
                    onToggleExpand();
                  }
                  setTimeout(() => {
                    const errorSection = document.querySelector('.validation-errors-section');
                    if (errorSection) {
                      errorSection.scrollIntoView({ behavior: 'smooth', block: 'center' });
                    }
                  }, 100);
                }}
              >
                 {t('upload.validationErrors.count', { count: file.validationErrors.length })}
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
                title={t('upload.status.validationPassed')}
              >
                 {t('upload.status.validationPassed')}
              </span>
            )}
          </div>
          <div className="uploaded-card__meta">
            <span>{(file.size / 1024).toFixed(1)} KB</span>
            {file.lotNo && <span>{t('upload.lotNoLabel')}: {file.lotNo}</span>}
          </div>
        </div>
        <div className="uploaded-card__actions">
          <button className="icon-button" onClick={onRemove} title={t('upload.actions.remove')}>
            ✕
          </button>
        </div>
      </div>

      <div className="uploaded-card__body">
        <div className="uploaded-card__status">
          {file.status === "uploaded" && (
            <span>{isPdf && file.isValidated ? pdfStatusText() : t('upload.status.pendingValidation')}</span>
          )}
          {file.status === "validating" && (
            <span>{t('upload.status.validating')}</span>
          )}
          {file.status === "validated" && <span>{t('upload.status.validated')}</span>}
          {file.status === "importing" && (
            <span>{t('upload.status.importing')}</span>
          )}
          {file.status === "imported" && <span>{t('upload.status.imported')}</span>}
        </div>

        {file.status === "validating" && (
          <ProgressBar value={file.validateProgress} label={t('upload.progress.validation')} />
        )}
        {file.status === "importing" && (
          <ProgressBar value={file.importProgress} label={t('upload.progress.import')} />
        )}

        {isPdf && file.isValidated && (file.pdfConvertStatus === 'queued' || file.pdfConvertStatus === 'uploading' || file.pdfConvertStatus === 'processing') && (
          <ProgressBar value={file.pdfConvertProgress ?? 0} label={t('upload.progress.pdfConvert')} />
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
                ? t('upload.tooltips.validating')
                : file.status === "importing"
                ? t('upload.tooltips.importing')
                : isPdf
                ? t('upload.tooltips.pdfUploadOnly')
                : hasValidationErrors
                ? t('upload.tooltips.revalidateHasErrors')
                : file.isValidated && !hasValidationErrors
                ? t('upload.tooltips.revalidatePassed')
                : t('upload.tooltips.validate')
            }
          >
            {file.status === "validating"
              ? t('upload.actions.validating')
              : isPdf
              ? (file.isValidated ? t('upload.pdf.upload.uploaded') : t('upload.pdf.upload.upload'))
              : hasValidationErrors
              ? t('upload.actions.revalidate')
              : file.isValidated
              ? t('upload.actions.validated')
              : t('upload.actions.validate')
            }
          </button>

          {isPdf && file.isValidated && (
            <button
              className={`btn-primary ${
                file.pdfConvertStatus === 'queued' || file.pdfConvertStatus === 'uploading' || file.pdfConvertStatus === 'processing'
                  ? 'btn-primary--disabled'
                  : ''
              }`}
              onClick={onConvertPdf}
              disabled={
                file.pdfConvertStatus === 'queued' ||
                file.pdfConvertStatus === 'uploading' ||
                file.pdfConvertStatus === 'processing'
              }
              title={
                file.pdfConvertStatus === 'completed'
                  ? t('upload.tooltips.pdfConvertDone')
                  : t('upload.tooltips.pdfConvertStartAsync')
              }
            >
              {file.pdfConvertStatus === 'completed'
                ? t('upload.pdf.convert.done')
                : file.pdfConvertStatus === 'failed'
                ? t('upload.pdf.convert.retry')
                : t('upload.pdf.convert.start')}
            </button>
          )}

          {!isPdf && (
            <button
              className={`btn-secondary ${
                disabledSave ? "btn-secondary--disabled" : ""
              }`}
              onClick={onSaveChanges}
              disabled={disabledSave}
              title={
                !EDIT_ENABLED
                  ? t('upload.editDisabledNotice')
                  : !file.csvData
                  ? t('upload.tooltips.validateBeforeEdit')
                  : !file.hasUnsavedChanges
                  ? t('upload.tooltips.noUnsavedChanges')
                  : t('upload.tooltips.saveChanges')
              }
            >
              {t('upload.actions.saveChanges')}
            </button>
          )}

          {!isPdf && file.status === "validated" && !hasValidationErrors && !file.hasUnsavedChanges && (
            <button
              className="btn-primary"
              onClick={() => onImport(file.id)}
              title={t('upload.tooltips.importToDb')}
            >
              {t('upload.actions.importFile')}
            </button>
          )}

          {!isPdf && file.status === "validated" && !hasValidationErrors && !file.hasUnsavedChanges && (
            <span className="status-badge status-badge--ready">
              {t('upload.badges.readyToImport')}
            </span>
          )}

          {!isPdf && file.status === "validated" && hasValidationErrors && (
            <span className="status-badge" style={{
              backgroundColor: '#fef2f2',
              color: '#dc2626',
              border: '1px solid #fecaca'
            }}>
               {t('upload.badges.needsFix')}
            </span>
          )}

          {!isPdf && (
            <button className="btn-text" onClick={onToggleExpand}>
              {file.expanded ? t('upload.actions.collapse') : t('upload.actions.expand')} CSV 內容
            </button>
          )}
        </div>

        {isPdf && file.isValidated && file.pdfConvertStatus === 'failed' && file.pdfConvertError && (
          <div style={{ marginTop: '8px', color: '#dc2626', fontSize: '14px' }}>
            轉檔失敗原因：{file.pdfConvertError}
          </div>
        )}
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
