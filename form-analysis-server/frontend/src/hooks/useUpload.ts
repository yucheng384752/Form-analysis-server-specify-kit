import { useState, useCallback } from 'react';
import { FilePreview, FileValidationError, UploadStatus } from '../types/api';
import { apiClient } from '../lib/api';

export interface UseUploadOptions {
  maxFileSize?: number; // in bytes
  allowedTypes?: string[];
  onSuccess?: (preview: FilePreview) => void;
  onError?: (error: string) => void;
}

export function useUpload(options: UseUploadOptions = {}) {
  const {
    maxFileSize = 10 * 1024 * 1024, // 10MB
    allowedTypes = ['text/csv', 'application/vnd.ms-excel'],
    onSuccess,
    onError,
  } = options;

  const [status, setStatus] = useState<UploadStatus>('idle');
  const [progress, setProgress] = useState(0);
  const [preview, setPreview] = useState<FilePreview | null>(null);
  const [errors, setErrors] = useState<FileValidationError[]>([]);
  const [processId, setProcessId] = useState<string | null>(null);

  const validateFile = useCallback((file: File): string | null => {
    if (file.size > maxFileSize) {
      return `檔案大小超過限制 (${(maxFileSize / 1024 / 1024).toFixed(1)}MB)`;
    }
    
    if (!allowedTypes.some(type => file.type === type || file.name.endsWith(type.split('/')[1]))) {
      return `不支援的檔案類型：${file.type}`;
    }

    return null;
  }, [maxFileSize, allowedTypes]);

  const uploadFile = useCallback(async (file: File) => {
    // 驗證檔案
    const validationError = validateFile(file);
    if (validationError) {
      onError?.(validationError);
      return;
    }

    try {
      setStatus('uploading');
      setProgress(0);
      setErrors([]);
      
      // 模擬上傳進度
      const progressInterval = setInterval(() => {
        setProgress(prev => {
          if (prev >= 90) {
            clearInterval(progressInterval);
            return prev;
          }
          return prev + Math.random() * 10;
        });
      }, 200);

      // 上傳檔案
      const uploadResponse = await apiClient.uploadFile('/api/upload/files', file);
      
      clearInterval(progressInterval);
      setProgress(100);

      if (!uploadResponse.success) {
        throw new Error(uploadResponse.message || '上傳失敗');
      }

      setStatus('validating');
      
      // 獲取預覽資料
      const previewData = uploadResponse.data as FilePreview;
      setPreview(previewData);
      setErrors(previewData.errors || []);
      setProcessId(previewData.id);

      setStatus('success');
      onSuccess?.(previewData);
      
    } catch (error) {
      setStatus('error');
      const errorMessage = error instanceof Error ? error.message : '未知錯誤';
      setErrors([{ 
        row: 0, 
        column: 'file', 
        message: errorMessage, 
        severity: 'error' 
      }]);
      onError?.(errorMessage);
    }
  }, [validateFile, onSuccess, onError]);

  const uploadFiles = useCallback(async (files: File[]) => {
    try {
      setStatus('uploading');
      setProgress(0);
      setErrors([]);

      const response = await apiClient.uploadFiles('/api/upload/files', files);
      
      if (!response.success) {
        throw new Error(response.message || '批次上傳失敗');
      }

      setStatus('success');
      setProgress(100);
      
    } catch (error) {
      setStatus('error');
      const errorMessage = error instanceof Error ? error.message : '未知錯誤';
      onError?.(errorMessage);
    }
  }, [onError]);

  const confirmUpload = useCallback(async () => {
    if (!processId) return;

    try {
      setStatus('uploading');
      
      const response = await apiClient.post(`/api/upload/confirm?process_id=${processId}`);
      
      if (!response.success) {
        throw new Error(response.message || '確認上傳失敗');
      }

      setStatus('success');
      
    } catch (error) {
      setStatus('error');
      const errorMessage = error instanceof Error ? error.message : '未知錯誤';
      onError?.(errorMessage);
    }
  }, [processId, onError]);

  const reset = useCallback(() => {
    setStatus('idle');
    setProgress(0);
    setPreview(null);
    setErrors([]);
    setProcessId(null);
  }, []);

  return {
    status,
    progress,
    preview,
    errors,
    processId,
    uploadFile,
    uploadFiles,
    confirmUpload,
    reset,
  };
}