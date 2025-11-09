import { useState, useRef, DragEvent, ChangeEvent } from "react";

interface UploadedFile {
  name: string;
  size: number;
  type: string;
  progress: number;
  id: string;
  isValidated?: boolean;
  file?: File;
  fileType?: 'p1' | 'p2' | 'p3' | undefined;
  lotNo?: string;
  csvData?: string[][];
}

// Simple upload icon SVG
const UploadIcon = ({ className }: { className?: string }) => (
  <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
  </svg>
);

// Simple file icon SVG
const FileIcon = ({ className }: { className?: string }) => (
  <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
  </svg>
);

// Simple X icon SVG
const XIcon = ({ className }: { className?: string }) => (
  <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
  </svg>
);

// Simple check circle icon SVG
const CheckCircleIcon = ({ className }: { className?: string }) => (
  <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
  </svg>
);

// Simple progress component
const Progress = ({ value, className }: { value: number; className?: string }) => (
  <div className={`bg-gray-200 rounded-full overflow-hidden ${className}`}>
    <div 
      className="bg-blue-600 h-full transition-all duration-300" 
      style={{ width: `${value}%` }}
    />
  </div>
);

export function FileUpload() {
  const [isDragging, setIsDragging] = useState(false);
  const [files, setFiles] = useState<UploadedFile[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10MB in bytes

  const handleDragOver = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragging(false);

    const droppedFiles = Array.from(e.dataTransfer.files);
    addFiles(droppedFiles);
  };

  const handleFileSelect = (e: ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      const selectedFiles = Array.from(e.target.files);
      addFiles(selectedFiles);
    }
  };

  const addFiles = async (newFiles: File[]) => {
    for (const file of newFiles) {
      // Check file type - only allow CSV and Excel files
      const fileExtension = file.name.split('.').pop()?.toLowerCase();
      if (fileExtension !== 'csv' && fileExtension !== 'xlsx' && fileExtension !== 'xls' && file.type !== 'text/csv') {
        alert(`檔案 "${file.name}" 格式不符，僅支援 CSV 和 Excel 檔案格式`);
        continue;
      }

      // Check file size
      if (file.size > MAX_FILE_SIZE) {
        alert(`檔案 "${file.name}" 超過 10MB 限制，檔案大小: ${formatFileSize(file.size)}`);
        continue;
      }

      const fileData: UploadedFile = {
        name: file.name,
        size: file.size,
        type: file.type,
        progress: 0,
        id: Math.random().toString(36).substring(7),
        file: file,
      };

      setFiles((prev) => [...prev, fileData]);

      // Upload to API
      await uploadFile(fileData.id, file);
    }
  };

  const importData = async (processId: string, fileId: string) => {
    try {
      const response = await fetch('http://localhost:8000/api/import', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ process_id: processId }),
      });

      if (response.ok) {
        const result = await response.json();
        setFiles((prev) =>
          prev.map((f) =>
            f.id === fileId ? { ...f, progress: 100, isValidated: true } : f
          )
        );
        console.log('Import successful:', result);
        alert(`資料匯入成功！匯入了 ${result.imported_rows} 筆資料`);
      } else {
        const errorData = await response.json();
        console.error('Import failed:', errorData);
        throw new Error(errorData.detail || 'Import failed');
      }
    } catch (error) {
      console.error('Import failed:', error);
      alert('資料匯入失敗');
    }
  };

  const uploadFile = async (fileId: string, file: File) => {
    try {
      const formData = new FormData();
      formData.append('file', file);
      
      // Update progress
      setFiles((prev) =>
        prev.map((f) =>
          f.id === fileId ? { ...f, progress: 50 } : f
        )
      );

      const response = await fetch('http://localhost:8000/api/upload', {
        method: 'POST',
        body: formData,
      });

      if (response.ok) {
        const result = await response.json();
        console.log('Upload successful:', result);
        
        // 上傳成功後，自動匯入資料
        await importData(result.process_id, fileId);
      } else {
        const errorData = await response.json();
        console.error('Upload failed:', errorData);
        throw new Error(errorData.detail || 'Upload failed');
      }
    } catch (error) {
      console.error('Upload failed:', error);
      setFiles((prev) =>
        prev.map((f) =>
          f.id === fileId ? { ...f, progress: 0 } : f
        )
      );
      alert('檔案上傳失敗');
    }
  };

  const removeFile = (index: number) => {
    setFiles((prev) => prev.filter((_, i) => i !== index));
  };

  const formatFileSize = (bytes: number) => {
    if (bytes === 0) return "0 Bytes";
    const k = 1024;
    const sizes = ["Bytes", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + " " + sizes[i];
  };

  const handleClick = () => {
    fileInputRef.current?.click();
  };

  const allFilesUploaded = files.length > 0 && files.every((file) => file.progress === 100);

  return (
    <div className="space-y-6">
      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={handleClick}
        className={`
          relative border-2 border-dashed rounded-lg p-12 text-center cursor-pointer
          transition-all duration-200 ease-in-out
          ${
            isDragging
              ? "border-blue-500 bg-blue-50"
              : "border-gray-300 bg-white hover:border-blue-400 hover:bg-gray-50"
          }
        `}
      >
        <input
          ref={fileInputRef}
          type="file"
          multiple
          accept=".csv,.xlsx,.xls"
          onChange={handleFileSelect}
          className="hidden"
        />
        
        <div className="flex flex-col items-center gap-4">
          <div className={`
            p-4 rounded-full transition-colors
            ${isDragging ? "bg-blue-100" : "bg-gray-100"}
          `}>
            <UploadIcon className={`w-12 h-12 ${isDragging ? "text-blue-500" : "text-gray-400"}`} />
          </div>
          
          <div>
            <p className={`text-lg font-medium mb-2 ${isDragging ? "text-blue-600" : "text-gray-600"}`}>
              拖曳上傳或是選擇檔案
            </p>
            <p className="text-gray-400 text-sm">
              支援 CSV 和 Excel 檔案格式，檔案大小限制 10MB
            </p>
          </div>
        </div>
      </div>

      {files.length > 0 && (
        <div className="bg-white rounded-lg p-6 shadow-sm">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-gray-700">已上傳檔案</h2>
            {allFilesUploaded && (
              <span className="text-green-600 font-medium flex items-center gap-2">
                <CheckCircleIcon className="w-4 h-4" />
                所有檔案上傳完成
              </span>
            )}
          </div>

          <div className="space-y-2">
            {files.map((file, index) => (
              <div
                key={file.id}
                className="flex items-center justify-between p-3 bg-gray-50 rounded-lg hover:bg-gray-100 transition-colors"
              >
                <div className="flex items-center gap-3 flex-1 min-w-0">
                  <FileIcon className="w-5 h-5 text-blue-500 flex-shrink-0" />
                  <div className="min-w-0 flex-1">
                    <p className="text-gray-700 truncate font-medium">{file.name}</p>
                    <p className="text-gray-400 text-sm">{formatFileSize(file.size)}</p>
                    {file.progress > 0 && file.progress < 100 && (
                      <div className="mt-2">
                        <Progress value={file.progress} className="h-1" />
                        <p className="text-gray-400 text-xs mt-1">
                          上傳中... {Math.round(file.progress)}%
                        </p>
                      </div>
                    )}
                    {file.progress === 100 && (
                      <p className="text-green-600 text-xs mt-1">✓ 上傳完成</p>
                    )}
                  </div>
                </div>
                <button
                  onClick={(e: React.MouseEvent) => {
                    e.stopPropagation();
                    removeFile(index);
                  }}
                  className="flex-shrink-0 p-1 text-gray-400 hover:text-red-500 transition-colors"
                  disabled={file.progress > 0 && file.progress < 100}
                >
                  <XIcon className="w-4 h-4" />
                </button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}