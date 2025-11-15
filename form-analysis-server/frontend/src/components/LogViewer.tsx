/**
 * 日誌查看頁面
 * 提供日誌檢視、搜尋、過濾和下載功能
 */

import React, { useState, useEffect, useCallback } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { 
  Download,
  RefreshCw,
  Search,
  Trash2,
  FileText,
  AlertCircle,
  Info,
  X,
  Clock
} from 'lucide-react';

import logService, { LogEntry, LogFile, LogStats, LogViewFilters } from '@/services/logService';

interface LogViewerProps {
  className?: string;
}

const LogViewer: React.FC<LogViewerProps> = ({ className }) => {
  // State management
  const [logFiles, setLogFiles] = useState<Record<string, LogFile>>({});
  const [selectedLogType, setSelectedLogType] = useState<string>('app');
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [stats, setStats] = useState<LogStats | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  // Filter states
  const [filters, setFilters] = useState<LogViewFilters>({
    limit: 100,
    offset: 0,
    hours: 24,
  });
  
  // Pagination state
  const [pagination, setPagination] = useState({
    total: 0,
    hasMore: false,
  });

  // Search state
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<LogEntry[]>([]);
  const [isSearchMode, setIsSearchMode] = useState(false);

  /**
   * 載入日誌檔案列表
   */
  const loadLogFiles = useCallback(async () => {
    try {
      setError(null);
      const files = await logService.getLogFiles();
      setLogFiles(files);
      
      // 如果當前選擇的檔案不存在，選擇第一個可用的
      if (!files[selectedLogType] && Object.keys(files).length > 0) {
        const firstFile = Object.keys(files)[0];
        setSelectedLogType(firstFile);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : '載入日誌檔案失敗');
    }
  }, [selectedLogType]);

  /**
   * 載入日誌內容
   */
  const loadLogs = useCallback(async (resetOffset = true) => {
    if (!selectedLogType || !logFiles[selectedLogType]) return;
    
    try {
      setLoading(true);
      setError(null);
      setIsSearchMode(false);

      const currentFilters = {
        ...filters,
        offset: resetOffset ? 0 : (filters.offset || 0),
      };

      const response = await logService.viewLogs(selectedLogType, currentFilters);
      
      if (resetOffset) {
        setLogs(response.logs);
        setFilters(prev => ({ ...prev, offset: 0 }));
      } else {
        setLogs(prev => [...prev, ...response.logs]);
      }
      
      setPagination({
        total: response.pagination.total,
        hasMore: response.pagination.has_more,
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : '載入日誌失敗');
    } finally {
      setLoading(false);
    }
  }, [selectedLogType, logFiles, filters]);

  /**
   * 載入更多日誌
   */
  const loadMoreLogs = useCallback(() => {
    if (!pagination.hasMore || loading) return;
    
    setFilters(prev => ({
      ...prev,
      offset: (prev.offset || 0) + (prev.limit || 100),
    }));
    
    // loadLogs will be called automatically by useEffect when filters change
    loadLogs(false);
  }, [pagination.hasMore, loading, loadLogs]);

  /**
   * 搜尋日誌
   */
  const searchLogs = useCallback(async () => {
    if (!searchQuery.trim()) {
      setIsSearchMode(false);
      await loadLogs();
      return;
    }

    try {
      setLoading(true);
      setError(null);
      setIsSearchMode(true);

      const response = await logService.searchLogs(searchQuery, selectedLogType, {
        limit: 200,
        caseSensitive: false,
      });
      
      setSearchResults(response.results);
    } catch (err) {
      setError(err instanceof Error ? err.message : '搜尋失敗');
    } finally {
      setLoading(false);
    }
  }, [searchQuery, selectedLogType, loadLogs]);

  /**
   * 載入統計資訊
   */
  const loadStats = useCallback(async () => {
    try {
      const statsData = await logService.getLogStats();
      setStats(statsData);
    } catch (err) {
      console.error('載入統計失敗:', err);
    }
  }, []);

  /**
   * 清理舊日誌
   */
  const cleanupLogs = useCallback(async () => {
    if (!window.confirm('確定要清理所有舊的日誌備份檔案嗎？')) {
      return;
    }

    try {
      setLoading(true);
      await logService.cleanupOldLogs();
      await loadLogFiles();
      await loadStats();
      alert('日誌清理完成');
    } catch (err) {
      setError(err instanceof Error ? err.message : '清理失敗');
    } finally {
      setLoading(false);
    }
  }, [loadLogFiles, loadStats]);

  /**
   * 下載日誌檔案
   */
  const downloadLog = useCallback(async (logType: string) => {
    try {
      await logService.downloadLogFile(logType);
    } catch (err) {
      setError(err instanceof Error ? err.message : '下載失敗');
    }
  }, []);

  // Effects
  useEffect(() => {
    loadLogFiles();
  }, [loadLogFiles]);

  useEffect(() => {
    if (Object.keys(logFiles).length > 0) {
      loadLogs();
      loadStats();
    }
  }, [selectedLogType, logFiles]);

  // 當過濾器變化時重新載入
  useEffect(() => {
    if (!isSearchMode) {
      loadLogs();
    }
  }, [filters.level, filters.hours, filters.search]);

  /**
   * 渲染單個日誌條目
   */
  const renderLogEntry = (entry: LogEntry, index: number) => {
    const levelColor = logService.getLogLevelColor(entry.level);
    const levelIcon = logService.getLogLevelIcon(entry.level);
    const timestamp = logService.formatTimestamp(entry.timestamp);

    return (
      <div key={`${entry.line_number}-${index}`} className="border-b border-gray-100 py-3 hover:bg-gray-50">
        <div className="flex items-start gap-3">
          <div className="flex-shrink-0">
            <Badge className={`${levelColor} font-mono text-xs`}>
              {levelIcon} {entry.level}
            </Badge>
          </div>
          
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 text-xs text-gray-500 mb-1">
              {timestamp && (
                <span className="flex items-center gap-1">
                  <Clock className="w-3 h-3" />
                  {timestamp}
                </span>
              )}
              <span className="flex items-center gap-1">
                <FileText className="w-3 h-3" />
                Line {entry.line_number}
              </span>
            </div>
            
            <div className="font-mono text-sm text-gray-800 break-all">
              {entry.highlighted_message ? (
                <div dangerouslySetInnerHTML={{ __html: entry.highlighted_message }} />
              ) : (
                entry.message
              )}
            </div>
            
            {entry.extra_data && Object.keys(entry.extra_data).length > 0 && (
              <div className="mt-2 text-xs text-gray-600">
                <details>
                  <summary className="cursor-pointer hover:text-gray-800">
                    額外資料 ({Object.keys(entry.extra_data).length} 項)
                  </summary>
                  <pre className="mt-1 p-2 bg-gray-100 rounded text-xs overflow-x-auto">
                    {JSON.stringify(entry.extra_data, null, 2)}
                  </pre>
                </details>
              </div>
            )}
          </div>
        </div>
      </div>
    );
  };

  return (
    <div className={`space-y-6 ${className}`}>
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">日誌管理</h1>
          <p className="text-gray-600 mt-1">查看、搜尋和管理系統日誌</p>
        </div>
        
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              loadLogFiles();
              loadLogs();
              loadStats();
            }}
            disabled={loading}
          >
            <RefreshCw className={`w-4 h-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
            重新整理
          </Button>
          
          <Button
            variant="outline"
            size="sm"
            onClick={cleanupLogs}
            disabled={loading}
          >
            <Trash2 className="w-4 h-4 mr-2" />
            清理舊日誌
          </Button>
        </div>
      </div>

      {/* Error Alert */}
      {error && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <Tabs defaultValue="logs" className="space-y-4">
        <TabsList>
          <TabsTrigger value="logs">日誌查看</TabsTrigger>
          <TabsTrigger value="stats">統計資訊</TabsTrigger>
        </TabsList>

        {/* Logs Tab */}
        <TabsContent value="logs" className="space-y-4">
          {/* Controls */}
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">日誌控制</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Log file selection */}
              <div className="flex gap-4 items-end">
                <div className="flex-1">
                  <label className="text-sm font-medium mb-2 block">日誌檔案</label>
                  <Select value={selectedLogType} onValueChange={setSelectedLogType}>
                    <SelectTrigger>
                      <SelectValue placeholder="選擇日誌檔案" />
                    </SelectTrigger>
                    <SelectContent>
                      {Object.entries(logFiles).map(([key, file]) => (
                        <SelectItem key={key} value={key}>
                          {key} ({logService.formatFileSize(file.size)})
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => downloadLog(selectedLogType)}
                  disabled={!selectedLogType || loading}
                >
                  <Download className="w-4 h-4 mr-2" />
                  下載
                </Button>
              </div>

              {/* Filters */}
              <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                <div>
                  <label className="text-sm font-medium mb-2 block">日誌級別</label>
                  <Select 
                    value={filters.level || ''} 
                    onValueChange={(value: string) => setFilters(prev => ({ ...prev, level: value || undefined }))}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="全部級別" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="">全部級別</SelectItem>
                      <SelectItem value="DEBUG">DEBUG</SelectItem>
                      <SelectItem value="INFO">INFO</SelectItem>
                      <SelectItem value="WARNING">WARNING</SelectItem>
                      <SelectItem value="ERROR">ERROR</SelectItem>
                      <SelectItem value="CRITICAL">CRITICAL</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                
                <div>
                  <label className="text-sm font-medium mb-2 block">時間範圍</label>
                  <Select 
                    value={filters.hours?.toString() || ''} 
                    onValueChange={(value: string) => setFilters(prev => ({ ...prev, hours: value ? parseInt(value) : undefined }))}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="選擇時間範圍" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="1">最近 1 小時</SelectItem>
                      <SelectItem value="6">最近 6 小時</SelectItem>
                      <SelectItem value="24">最近 24 小時</SelectItem>
                      <SelectItem value="168">最近 1 週</SelectItem>
                      <SelectItem value="">全部時間</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                
                <div>
                  <label className="text-sm font-medium mb-2 block">顯示數量</label>
                  <Select 
                    value={filters.limit?.toString() || '100'} 
                    onValueChange={(value: string) => setFilters(prev => ({ ...prev, limit: parseInt(value) }))}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="50">50 條</SelectItem>
                      <SelectItem value="100">100 條</SelectItem>
                      <SelectItem value="200">200 條</SelectItem>
                      <SelectItem value="500">500 條</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>

              {/* Search */}
              <div className="flex gap-2">
                <div className="flex-1">
                  <Input
                    placeholder="搜尋日誌內容..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    onKeyPress={(e) => e.key === 'Enter' && searchLogs()}
                  />
                </div>
                <Button onClick={searchLogs} disabled={loading}>
                  <Search className="w-4 h-4 mr-2" />
                  搜尋
                </Button>
                {isSearchMode && (
                  <Button 
                    variant="outline" 
                    onClick={() => {
                      setIsSearchMode(false);
                      setSearchQuery('');
                      loadLogs();
                    }}
                  >
                    <X className="w-4 h-4 mr-2" />
                    清除
                  </Button>
                )}
              </div>

              {/* Status Info */}
              <div className="flex justify-between text-sm text-gray-600">
                <span>
                  {isSearchMode 
                    ? `搜尋結果: ${searchResults.length} 條`
                    : `顯示: ${logs.length} / ${pagination.total} 條日誌`
                  }
                </span>
                <span>
                  檔案: {selectedLogType} 
                  {logFiles[selectedLogType] && ` (${logService.formatFileSize(logFiles[selectedLogType].size)})`}
                </span>
              </div>
            </CardContent>
          </Card>

          {/* Logs Display */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <FileText className="w-5 h-5" />
                日誌內容
                {isSearchMode && <Badge variant="secondary">搜尋模式</Badge>}
              </CardTitle>
            </CardHeader>
            <CardContent>
              {loading && logs.length === 0 ? (
                <div className="text-center py-8">
                  <RefreshCw className="w-8 h-8 animate-spin mx-auto mb-2 text-gray-400" />
                  <p className="text-gray-600">載入中...</p>
                </div>
              ) : (
                <ScrollArea className="h-[600px]">
                  <div className="space-y-0">
                    {(isSearchMode ? searchResults : logs).map((entry, index) => 
                      renderLogEntry(entry, index)
                    )}
                    
                    {!isSearchMode && pagination.hasMore && (
                      <div className="text-center py-4">
                        <Button 
                          variant="outline" 
                          onClick={loadMoreLogs}
                          disabled={loading}
                        >
                          {loading ? (
                            <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
                          ) : (
                            '載入更多'
                          )}
                        </Button>
                      </div>
                    )}
                    
                    {(isSearchMode ? searchResults : logs).length === 0 && !loading && (
                      <div className="text-center py-8 text-gray-500">
                        <Info className="w-8 h-8 mx-auto mb-2" />
                        <p>{isSearchMode ? '沒有找到匹配的日誌' : '沒有日誌資料'}</p>
                      </div>
                    )}
                  </div>
                </ScrollArea>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Stats Tab */}
        <TabsContent value="stats">
          {stats && (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* File Stats */}
              <Card>
                <CardHeader>
                  <CardTitle>檔案資訊</CardTitle>
                  <CardDescription>
                    總大小: {logService.formatFileSize(stats.total_size)}
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="space-y-3">
                    {Object.entries(stats.files).map(([name, file]) => (
                      <div key={name} className="flex justify-between items-center">
                        <span className="font-medium">{name}</span>
                        <div className="text-sm text-gray-600">
                          {logService.formatFileSize(file.size)}
                        </div>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>

              {/* Level Distribution */}
              <Card>
                <CardHeader>
                  <CardTitle>日誌級別分佈</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-3">
                    {Object.entries(stats.level_distribution).map(([level, count]) => {
                      const levelColor = logService.getLogLevelColor(level);
                      const icon = logService.getLogLevelIcon(level);
                      return (
                        <div key={level} className="flex justify-between items-center">
                          <div className="flex items-center gap-2">
                            <Badge className={`${levelColor} text-xs`}>
                              {icon} {level}
                            </Badge>
                          </div>
                          <span className="font-medium">{count.toLocaleString()}</span>
                        </div>
                      );
                    })}
                  </div>
                </CardContent>
              </Card>

              {/* API Usage */}
              <Card>
                <CardHeader>
                  <CardTitle>API 使用統計</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-3">
                    {Object.entries(stats.api_usage).map(([api, count]) => (
                      <div key={api} className="flex justify-between items-center">
                        <span className="capitalize">{api}</span>
                        <span className="font-medium">{count.toLocaleString()}</span>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>

              {/* Recent Activity */}
              <Card>
                <CardHeader>
                  <CardTitle>最近活動</CardTitle>
                  <CardDescription>最新的系統活動記錄</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="space-y-3">
                    {stats.recent_activity.slice(0, 10).map((activity, index) => {
                      const levelColor = logService.getLogLevelColor(activity.level);
                      const icon = logService.getLogLevelIcon(activity.level);
                      return (
                        <div key={index} className="border-b border-gray-100 pb-2 last:border-0">
                          <div className="flex items-start gap-2">
                            <Badge className={`${levelColor} text-xs flex-shrink-0`}>
                              {icon}
                            </Badge>
                            <div className="flex-1 min-w-0">
                              <p className="text-sm text-gray-800 truncate">{activity.message}</p>
                              <p className="text-xs text-gray-500">
                                {logService.formatTimestamp(activity.timestamp)}
                              </p>
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </CardContent>
              </Card>
            </div>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
};

export default LogViewer;