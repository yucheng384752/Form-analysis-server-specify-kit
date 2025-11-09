import { useState, useRef, DragEvent, ChangeEvent } from "react";
import { Upload, File, X, AlertCircle, CheckCircle2 } from "lucide-react";
import { Button } from "./ui/button";
import { Progress } from "./ui/progress";
import { toast } from "sonner@2.0.3";
import { CSVEditor } from "./CSVEditor";

interface UploadedFile {
  name: string;
  size: number;
  type: string;
  progress: number;
  id: string;
  isValidated?: boolean;
  file?: File;
  fileType?: 'p1' | 'p2' | 'p3';
  lotNo?: string;
  csvData?: string[][];
}

export function FileUpload() {
  const [isDragging, setIsDragging] = useState(false);
  const [files, setFiles] = useState<UploadedFile[]>([]);
  const [isValidating, setIsValidating] = useState(false);
  const [validationProgress, setValidationProgress] = useState(0);
  const [csvData, setCsvData] = useState<string[][] | null>(null);
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

  const addFiles = (newFiles: File[]) => {
    newFiles.forEach((file) => {
      // Check file type - only allow CSV
      const fileExtension = file.name.split('.').pop()?.toLowerCase();
      if (fileExtension !== 'csv' && file.type !== 'text/csv') {
        toast.error(`檔案 "${file.name}" 格式不符`, {
          description: '僅支援 CSV 檔案格式',
        });
        return;
      }

      // Check file size
      if (file.size > MAX_FILE_SIZE) {
        toast.error(`檔案 "${file.name}" 超過 10MB 限制`, {
          description: `檔案大小: ${formatFileSize(file.size)}`,
        });
        return;
      }

      // Determine file type based on filename
      const fileName = file.name.toLowerCase();
      let fileType: 'p1' | 'p2' | 'p3' | undefined;
      if (fileName.startsWith('p1_') || fileName.startsWith('p1.')) {
        fileType = 'p1';
      } else if (fileName.startsWith('p2_') || fileName.startsWith('p2.')) {
        fileType = 'p2';
      } else if (fileName.startsWith('p3_') || fileName.startsWith('p3.')) {
        fileType = 'p3';
      }

      // Extract and normalize lot_no for p1 and p2
      let lotNo: string | undefined;
      if (fileType === 'p1' || fileType === 'p2') {
        lotNo = extractAndNormalizeLotNo(file.name);
      }

      const fileData: UploadedFile = {
        name: file.name,
        size: file.size,
        type: file.type,
        progress: 0,
        id: Math.random().toString(36).substring(7),
        file: file, // Store the actual file object
        fileType: fileType,
        lotNo: lotNo,
      };

      setFiles((prev) => [...prev, fileData]);

      // Simulate upload progress
      simulateUpload(fileData.id);
    });
  };

  const simulateUpload = (fileId: string) => {
    let progress = 0;
    const interval = setInterval(() => {
      progress += Math.random() * 30;
      if (progress >= 100) {
        progress = 100;
        clearInterval(interval);
        toast.success("檔案上傳完成");
      }
      setFiles((prev) =>
        prev.map((file) =>
          file.id === fileId ? { ...file, progress } : file
        )
      );
    }, 300);
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

  const handleValidation = async () => {
    setIsValidating(true);
    setValidationProgress(0);

    // Simulate validation progress
    const totalSteps = 100;
    for (let i = 0; i <= totalSteps; i++) {
      await new Promise((resolve) => setTimeout(resolve, 30));
      setValidationProgress(i);
    }

    // Mark all files as validated
    setFiles((prev) =>
      prev.map((file) => ({ ...file, isValidated: true }))
    );

    setIsValidating(false);
    toast.success("檔案驗證完成", {
      description: "所有檔案已通過驗證",
    });

    // Read and parse CSV files
    await parseCSVFiles();
  };

  const parseCSVFiles = async () => {
    // Parse all validated files
    const parsePromises = files.map((fileItem) => {
      return new Promise<void>((resolve) => {
        if (!fileItem.file) {
          resolve();
          return;
        }

        const reader = new FileReader();
        reader.onload = (e) => {
          const text = e.target?.result as string;
          const rows = text.split('\n').map(row => {
            // Simple CSV parsing - handles basic comma-separated values
            const values: string[] = [];
            let currentValue = '';
            let insideQuotes = false;

            for (let i = 0; i < row.length; i++) {
              const char = row[i];
              
              if (char === '"') {
                insideQuotes = !insideQuotes;
              } else if (char === ',' && !insideQuotes) {
                values.push(currentValue.trim());
                currentValue = '';
              } else {
                currentValue += char;
              }
            }
            values.push(currentValue.trim());
            return values;
          }).filter(row => row.some(cell => cell.length > 0)); // Remove empty rows

          // Store CSV data for this file
          setFiles((prev) =>
            prev.map((f) =>
              f.id === fileItem.id ? { ...f, csvData: rows } : f
            )
          );

          // For p3 files, extract lot_no from P3_No. column
          if (fileItem.fileType === 'p3' && rows.length > 0) {
            const headers = rows[0];
            const p3NoIndex = headers.findIndex(h => 
              h.toLowerCase().includes('p3_no') || h.toLowerCase() === 'p3_no.'
            );
            
            if (p3NoIndex !== -1 && rows.length > 1) {
              const p3NoValue = rows[1][p3NoIndex]; // Get first data row's P3_No.
              // Normalize P3_No. to 7+2 format (e.g., 2411012_03_05_301 -> 2411012_03)
              const normalizedLotNo = normalizeP3LotNo(p3NoValue);
              setFiles((prev) =>
                prev.map((f) =>
                  f.id === fileItem.id ? { ...f, lotNo: normalizedLotNo } : f
                )
              );
            }
          }

          resolve();
        };
        reader.readAsText(fileItem.file);
      });
    });

    await Promise.all(parsePromises);
  };

  const normalizeP3LotNo = (p3No: string): string => {
    // Split by underscore and take first two parts
    const parts = p3No.split('_');
    
    if (parts.length >= 2) {
      const part1 = parts[0];
      const part2 = parts[1];
      
      // Normalize to 7+2 format
      const normalizedPart1 = part1.padStart(7, '0').slice(-7);
      const normalizedPart2 = part2.padStart(2, '0').slice(-2);
      
      return `${normalizedPart1}_${normalizedPart2}`;
    }
    
    return p3No; // Return original if pattern not suitable
  };

  const allFilesUploaded = files.length > 0 && files.every((file) => file.progress === 100);
  const allFilesValidated = files.length > 0 && files.every((file) => file.isValidated);

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
          accept=".csv"
          onChange={handleFileSelect}
          className="hidden"
        />
        
        <div className="flex flex-col items-center gap-4">
          <div className={`
            p-4 rounded-full transition-colors
            ${isDragging ? "bg-blue-100" : "bg-gray-100"}
          `}>
            <Upload className={`w-12 h-12 ${isDragging ? "text-blue-500" : "text-gray-400"}`} />
          </div>
          
          <div>
            <p className={`mb-2 ${isDragging ? "text-blue-600" : "text-gray-600"}`}>
              拖曳上傳或是選擇檔案
            </p>
            <p className="text-gray-400 text-sm">
              僅支援csv檔案類型，檔案大小限制 10MB
            </p>
          </div>
        </div>
      </div>

      {files.length > 0 && (
        <div className="bg-white rounded-lg p-6 shadow-sm">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-gray-700">已上傳檔案</h2>
            <Button
              onClick={handleValidation}
              disabled={!allFilesUploaded || isValidating}
              className="flex items-center gap-2"
            >
              <CheckCircle2 className="w-4 h-4" />
              {isValidating ? "驗證中..." : "確認驗證"}
            </Button>
          </div>

          {isValidating && (
            <div className="mb-4 p-4 bg-blue-50 rounded-lg">
              <p className="text-blue-700 mb-2">正在驗證檔案...</p>
              <Progress value={validationProgress} className="h-2" />
              <p className="text-blue-600 text-sm mt-2">
                驗證進度: {Math.round(validationProgress)}%
              </p>
            </div>
          )}

          <div className="space-y-2">
            {files.map((file, index) => (
              <div
                key={file.id}
                className="flex items-center justify-between p-3 bg-gray-50 rounded-lg hover:bg-gray-100 transition-colors"
              >
                <div className="flex items-center gap-3 flex-1 min-w-0">
                  <File className="w-5 h-5 text-blue-500 flex-shrink-0" />
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <p className="text-gray-700 truncate">{file.name}</p>
                      {file.fileType && (
                        <span className="px-2 py-0.5 bg-blue-100 text-blue-700 rounded text-xs">
                          {file.fileType.toUpperCase()}
                        </span>
                      )}
                    </div>
                    {/* {file.lotNo && (
                      <p className="text-blue-600 text-sm mt-1">
                        Lot No: {file.lotNo}
                      </p>
                    )} */}
                    <p className="text-gray-400 text-sm">{formatFileSize(file.size)}</p>
                    {file.progress < 100 && (
                      <div className="mt-2">
                        <Progress value={file.progress} className="h-1" />
                        <p className="text-gray-400 text-xs mt-1">
                          上傳中... {Math.round(file.progress)}%
                        </p>
                      </div>
                    )}
                    {file.progress === 100 && !file.isValidated && (
                      <p className="text-green-600 text-xs mt-1">✓ 上傳完成</p>
                    )}
                    {file.isValidated && (
                      <p className="text-green-600 text-xs mt-1">✓ 已驗證</p>
                    )}
                  </div>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={(e) => {
                    e.stopPropagation();
                    removeFile(index);
                  }}
                  className="flex-shrink-0"
                  disabled={isValidating}
                >
                  <X className="w-4 h-4" />
                </Button>
              </div>
            ))}
          </div>
        </div>
      )}

      {allFilesValidated && files.map((file) => 
        file.csvData ? (
          <CSVEditor 
            key={file.id}
            fileName={file.name}
            data={file.csvData} 
            onDataChange={(newData) => {
              setFiles((prev) =>
                prev.map((f) =>
                  f.id === file.id ? { ...f, csvData: newData } : f
                )
              );
            }} 
          />
        ) : null
      )}
    </div>
  );
}

const extractAndNormalizeLotNo = (fileName: string): string => {
  // Remove file extension
  const nameWithoutExt = fileName.replace(/\.csv$/i, '');
  
  // Extract lot_no pattern (numbers and underscore)
  // Looking for pattern like: 2503033_03 or similar
  const match = nameWithoutExt.match(/(\d+)_(\d+)/);
  
  if (match) {
    const part1 = match[1];
    const part2 = match[2];
    
    // Normalize to 7+2 format
    const normalizedPart1 = part1.padStart(7, '0').slice(-7);
    const normalizedPart2 = part2.padStart(2, '0').slice(-2);
    
    return `${normalizedPart1}_${normalizedPart2}`;
  }
  
  return nameWithoutExt; // Return original if pattern not found
};