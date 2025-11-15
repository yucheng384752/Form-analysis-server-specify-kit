/**
 * 日誌管理服務
 * 提供日誌查看、搜尋、統計等功能
 */

import { apiRequest } from './api';

export interface LogEntry {
  line_number: number;
  timestamp: string;
  level: string;
  message: string;
  extra_data: Record<string, any>;
  is_json: boolean;
  raw_line: string;
  highlighted_message?: string;
}

export interface LogFile {
  name: string;
  size: number;
  size_mb: number;
  modified: string;
  path: string;
}

export interface LogViewResponse {
  logs: LogEntry[];
  pagination: {
    total: number;
    limit: number;
    offset: number;
    has_more: boolean;
  };
  filters: {
    log_type: string;
    level?: string;
    search?: string;
    hours?: number;
    start_time?: string;
    end_time?: string;
  };
}

export interface LogStats {
  files: Record<string, LogFile>;
  total_size: number;
  total_size_mb: number;
  level_distribution: Record<string, number>;
  api_usage: Record<string, number>;
  recent_activity: Array<{
    timestamp: string;
    level: string;
    message: string;
  }>;
}

export interface LogSearchResponse {
  results: LogEntry[];
  query: string;
  log_type: string;
  total_matches: number;
  case_sensitive: boolean;
  truncated: boolean;
}

export interface LogViewFilters {
  limit?: number;
  offset?: number | undefined;
  level?: string | undefined;
  search?: string | undefined;
  hours?: number | undefined;
  start_time?: string | undefined;
  end_time?: string | undefined;
}

class LogService {
  private readonly baseUrl = '/api/logs';

  /**
   * 獲取所有可用的日誌檔案
   */
  async getLogFiles(): Promise<Record<string, LogFile>> {
    const response = await apiRequest<{ files: Record<string, LogFile> }>({
      url: `${this.baseUrl}/files`,
      method: 'GET',
    });
    return response.files;
  }

  /**
   * 查看指定類型的日誌
   */
  async viewLogs(logType: string, filters: LogViewFilters = {}): Promise<LogViewResponse> {
    const params = new URLSearchParams();
    
    if (filters.limit) params.append('limit', filters.limit.toString());
    if (filters.offset) params.append('offset', filters.offset.toString());
    if (filters.level) params.append('level', filters.level);
    if (filters.search) params.append('search', filters.search);
    if (filters.hours) params.append('hours', filters.hours.toString());
    if (filters.start_time) params.append('start_time', filters.start_time);
    if (filters.end_time) params.append('end_time', filters.end_time);

    return await apiRequest<LogViewResponse>({
      url: `${this.baseUrl}/view/${logType}?${params.toString()}`,
      method: 'GET',
    });
  }

  /**
   * 獲取日誌統計資訊
   */
  async getLogStats(): Promise<LogStats> {
    return await apiRequest<LogStats>({
      url: `${this.baseUrl}/stats`,
      method: 'GET',
    });
  }

  /**
   * 搜尋日誌內容
   */
  async searchLogs(
    query: string, 
    logType: string = 'app',
    options: {
      limit?: number;
      caseSensitive?: boolean;
    } = {}
  ): Promise<LogSearchResponse> {
    const params = new URLSearchParams({
      query,
      log_type: logType,
    });
    
    if (options.limit) params.append('limit', options.limit.toString());
    if (options.caseSensitive !== undefined) {
      params.append('case_sensitive', options.caseSensitive.toString());
    }

    return await apiRequest<LogSearchResponse>({
      url: `${this.baseUrl}/search?${params.toString()}`,
      method: 'GET',
    });
  }

  /**
   * 清理舊的日誌備份檔案
   */
  async cleanupOldLogs(): Promise<{
    message: string;
    cleaned_files: Array<{
      name: string;
      size: number;
      size_mb: number;
    }>;
    total_size_freed: number;
    total_size_freed_mb: number;
  }> {
    return await apiRequest({
      url: `${this.baseUrl}/cleanup`,
      method: 'DELETE',
    });
  }

  /**
   * 下載日誌檔案
   */
  async downloadLogFile(logType: string): Promise<void> {
    try {
      const API_BASE_URL = (import.meta.env?.VITE_API_URL as string) || 'http://localhost:8000';
      const response = await fetch(`${API_BASE_URL}${this.baseUrl}/download/${logType}`);
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.style.display = 'none';
      a.href = url;
      
      // 從 Content-Disposition header 獲取檔案名稱
      const contentDisposition = response.headers.get('content-disposition');
      let filename = `${logType}_${new Date().toISOString().split('T')[0]}.log`;
      
      if (contentDisposition) {
        const filenameMatch = contentDisposition.match(/filename="(.+)"/);
        if (filenameMatch) {
          filename = filenameMatch[1];
        }
      }
      
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (error) {
      console.error('Download failed:', error);
      throw new Error('下載日誌檔案失敗');
    }
  }

  /**
   * 格式化檔案大小
   */
  formatFileSize(bytes: number): string {
    if (bytes === 0) return '0 Bytes';
    
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  }

  /**
   * 格式化時間戳
   */
  formatTimestamp(timestamp: string): string {
    if (!timestamp) return '';
    
    try {
      const date = new Date(timestamp);
      return date.toLocaleString('zh-TW', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
      });
    } catch (error) {
      return timestamp;
    }
  }

  /**
   * 獲取日誌級別的顏色類名
   */
  getLogLevelColor(level: string): string {
    switch (level.toUpperCase()) {
      case 'ERROR':
      case 'CRITICAL':
        return 'text-red-600 bg-red-50';
      case 'WARNING':
      case 'WARN':
        return 'text-yellow-600 bg-yellow-50';
      case 'INFO':
        return 'text-blue-600 bg-blue-50';
      case 'DEBUG':
        return 'text-gray-600 bg-gray-50';
      default:
        return 'text-gray-600 bg-gray-50';
    }
  }

  /**
   * 獲取日誌級別的圖示
   */
  getLogLevelIcon(level: string): string {
    switch (level.toUpperCase()) {
      case 'ERROR':
      case 'CRITICAL':
        return '';
      case 'WARNING':
      case 'WARN':
        return '';
      case 'INFO':
        return '';
      case 'DEBUG':
        return '';
      default:
        return '';
    }
  }
}

export const logService = new LogService();
export default logService;