/**
 * 簡化版日誌查看組件
 * 使用基本 HTML 元素，不依賴複雜的 UI 庫
 */

import React, { useState, useEffect, useCallback } from 'react';
import logService, { LogEntry, LogFile, LogStats, LogViewFilters } from '@/services/logService';

interface LogViewerProps {
  className?: string;
}

const LogViewer: React.FC<LogViewerProps> = ({ className = '' }) => {
  // State management
  const [logFiles, setLogFiles] = useState<Record<string, LogFile>>({});
  const [selectedLogType, setSelectedLogType] = useState<string>('app');
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [stats, setStats] = useState<LogStats | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'logs' | 'stats'>('logs');
  
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
      <div key={`${entry.line_number}-${index}`} className="log-entry">
        <div className="log-entry-header">
          <span className={`log-level-badge ${levelColor}`}>
            {levelIcon} {entry.level}
          </span>
          
          <div className="log-meta">
            {timestamp && (
              <span className="log-timestamp">
                 {timestamp}
              </span>
            )}
            <span className="log-line">
               Line {entry.line_number}
            </span>
          </div>
        </div>
        
        <div className="log-message">
          {entry.highlighted_message ? (
            <div dangerouslySetInnerHTML={{ __html: entry.highlighted_message }} />
          ) : (
            entry.message
          )}
        </div>
        
        {entry.extra_data && Object.keys(entry.extra_data).length > 0 && (
          <details className="log-extra-data">
            <summary>額外資料 ({Object.keys(entry.extra_data).length} 項)</summary>
            <pre>{JSON.stringify(entry.extra_data, null, 2)}</pre>
          </details>
        )}
      </div>
    );
  };

  return (
    <div className={`log-viewer ${className}`}>
      <style>{`
        .log-viewer {
          max-width: 1200px;
          margin: 0 auto;
          padding: 20px;
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        }
        
        .log-viewer h1 {
          font-size: 2.5rem;
          font-weight: bold;
          color: #1f2937;
          margin-bottom: 0.5rem;
        }
        
        .log-viewer .subtitle {
          color: #6b7280;
          margin-bottom: 1.5rem;
        }
        
        .log-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 2rem;
        }
        
        .log-actions {
          display: flex;
          gap: 0.5rem;
        }
        
        .btn {
          padding: 0.5rem 1rem;
          border: 1px solid #d1d5db;
          border-radius: 0.375rem;
          background: white;
          cursor: pointer;
          font-size: 0.875rem;
          display: inline-flex;
          align-items: center;
          gap: 0.5rem;
        }
        
        .btn:hover {
          background: #f9fafb;
        }
        
        .btn:disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }
        
        .btn-primary {
          background: #3b82f6;
          color: white;
          border-color: #3b82f6;
        }
        
        .btn-primary:hover {
          background: #2563eb;
        }
        
        .error-alert {
          background: #fef2f2;
          border: 1px solid #fecaca;
          color: #dc2626;
          padding: 1rem;
          border-radius: 0.375rem;
          margin-bottom: 1rem;
        }
        
        .tabs {
          margin-bottom: 1rem;
        }
        
        .tab-list {
          display: flex;
          border-bottom: 1px solid #e5e7eb;
          margin-bottom: 1rem;
        }
        
        .tab-button {
          padding: 0.75rem 1.5rem;
          border: none;
          background: white;
          color: #6b7280;
          cursor: pointer;
          border-bottom: 2px solid transparent;
          font-weight: 500;
          border-radius: 0.375rem 0.375rem 0 0;
          transition: all 0.2s ease;
        }
        
        .tab-button:hover {
          background-color: #f9fafb;
          color: #374151;
        }
        
        .tab-button.active {
          border-bottom-color: #3b82f6;
          color: #3b82f6;
          background: white;
        }
        
        .card {
          background: white;
          border: 1px solid #e5e7eb;
          border-radius: 0.5rem;
          padding: 1.5rem;
          margin-bottom: 1rem;
          box-shadow: 0 1px 3px 0 rgb(0 0 0 / 0.1);
        }
        
        .card-title {
          font-size: 1.25rem;
          font-weight: 600;
          margin-bottom: 1rem;
        }
        
        .form-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
          gap: 1rem;
          margin-bottom: 1rem;
        }
        
        .form-group {
          display: flex;
          flex-direction: column;
        }
        
        .form-label {
          font-size: 0.875rem;
          font-weight: 500;
          margin-bottom: 0.5rem;
        }
        
        .form-select,
        .form-input {
          padding: 0.5rem;
          border: 1px solid #d1d5db;
          border-radius: 0.375rem;
          font-size: 0.875rem;
        }
        
        .search-group {
          display: flex;
          gap: 0.5rem;
          margin-bottom: 1rem;
        }
        
        .search-group input {
          flex: 1;
        }
        
        .status-info {
          display: flex;
          justify-content: space-between;
          font-size: 0.875rem;
          color: #6b7280;
          margin-bottom: 1rem;
        }
        
        .logs-container {
          background: white;
          border: 1px solid #e5e7eb;
          border-radius: 0.5rem;
          max-height: 600px;
          overflow-y: auto;
        }
        
        .log-entry {
          padding: 1rem;
          border-bottom: 1px solid #f3f4f6;
        }
        
        .log-entry:last-child {
          border-bottom: none;
        }
        
        .log-entry:hover {
          background: #f9fafb;
        }
        
        .log-entry-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 0.5rem;
        }
        
        .log-level-badge {
          padding: 0.25rem 0.5rem;
          border-radius: 0.25rem;
          font-size: 0.75rem;
          font-weight: 600;
          font-family: 'Courier New', monospace;
        }
        
        .text-red-600 {
          color: #dc2626;
          background: #fef2f2;
        }
        
        .text-yellow-600 {
          color: #d97706;
          background: #fffbeb;
        }
        
        .text-blue-600 {
          color: #2563eb;
          background: #eff6ff;
        }
        
        .text-gray-600 {
          color: #4b5563;
          background: #f9fafb;
        }
        
        .log-meta {
          display: flex;
          gap: 1rem;
          font-size: 0.75rem;
          color: #6b7280;
        }
        
        .log-message {
          font-family: 'Courier New', monospace;
          font-size: 0.875rem;
          color: #1f2937;
          word-break: break-all;
          line-height: 1.4;
        }
        
        .log-extra-data {
          margin-top: 0.5rem;
          font-size: 0.75rem;
          color: #6b7280;
        }
        
        .log-extra-data pre {
          margin-top: 0.5rem;
          padding: 0.5rem;
          background: #f3f4f6;
          border-radius: 0.25rem;
          font-size: 0.75rem;
          overflow-x: auto;
        }
        
        .loading-spinner {
          display: flex;
          flex-direction: column;
          align-items: center;
          padding: 2rem;
          color: #6b7280;
        }
        
        .spinner {
          width: 2rem;
          height: 2rem;
          border: 2px solid #f3f4f6;
          border-top: 2px solid #3b82f6;
          border-radius: 50%;
          animation: spin 1s linear infinite;
          margin-bottom: 0.5rem;
        }
        
        @keyframes spin {
          0% { transform: rotate(0deg); }
          100% { transform: rotate(360deg); }
        }
        
        .empty-state {
          text-align: center;
          padding: 2rem;
          color: #6b7280;
        }
        
        .stats-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
          gap: 1rem;
        }
        
        .stat-item {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 0.75rem 0;
          border-bottom: 1px solid #f3f4f6;
        }
        
        .stat-item:last-child {
          border-bottom: none;
        }
      `}</style>
      
      {/* Header */}
      <div className="log-header">
        <div>
          <h1>日誌管理</h1>
          <p className="subtitle">查看、搜尋和管理系統日誌</p>
        </div>
        
        <div className="log-actions">
          <button
            className="btn"
            onClick={() => {
              loadLogFiles();
              loadLogs();
              loadStats();
            }}
            disabled={loading}
          >
            {loading ? <div className="spinner" /> : ''} 重新整理
          </button>
          
          <button
            className="btn"
            onClick={cleanupLogs}
            disabled={loading}
          >
             清理舊日誌
          </button>
        </div>
      </div>

      {/* Error Alert */}
      {error && (
        <div className="error-alert">
           {error}
        </div>
      )}

      <div className="tabs">
        <div className="tab-list">
          <button
            className={`tab-button ${activeTab === 'logs' ? 'active' : ''}`}
            onClick={() => setActiveTab('logs')}
          >
            日誌查看
          </button>
          <button
            className={`tab-button ${activeTab === 'stats' ? 'active' : ''}`}
            onClick={() => setActiveTab('stats')}
          >
            統計資訊
          </button>
        </div>

        {/* Logs Tab */}
        {activeTab === 'logs' && (
          <div>
            {/* Controls */}
            <div className="card">
              <div className="card-title">日誌控制</div>
              
              {/* Log file selection */}
              <div className="form-grid">
                <div className="form-group">
                  <label className="form-label">日誌檔案</label>
                  <select 
                    className="form-select"
                    value={selectedLogType} 
                    onChange={(e) => setSelectedLogType(e.target.value)}
                  >
                    {Object.entries(logFiles).map(([key, file]) => (
                      <option key={key} value={key}>
                        {key} ({logService.formatFileSize(file.size)})
                      </option>
                    ))}
                  </select>
                </div>
                
                <div className="form-group">
                  <button
                    className="btn"
                    onClick={() => downloadLog(selectedLogType)}
                    disabled={!selectedLogType || loading}
                    style={{ marginTop: '1.5rem' }}
                  >
                    下載
                  </button>
                </div>
              </div>

              {/* Filters */}
              <div className="form-grid">
                <div className="form-group">
                  <label className="form-label">日誌級別</label>
                  <select 
                    className="form-select"
                    value={filters.level || ''} 
                    onChange={(e) => setFilters(prev => ({ ...prev, level: e.target.value || undefined }))}
                  >
                    <option value="">全部級別</option>
                    <option value="DEBUG">DEBUG</option>
                    <option value="INFO">INFO</option>
                    <option value="WARNING">WARNING</option>
                    <option value="ERROR">ERROR</option>
                    <option value="CRITICAL">CRITICAL</option>
                  </select>
                </div>
                
                <div className="form-group">
                  <label className="form-label">時間範圍</label>
                  <select 
                    className="form-select"
                    value={filters.hours?.toString() || ''} 
                    onChange={(e) => setFilters(prev => ({ ...prev, hours: e.target.value ? parseInt(e.target.value) : undefined }))}
                  >
                    <option value="1">最近 1 小時</option>
                    <option value="6">最近 6 小時</option>
                    <option value="24">最近 24 小時</option>
                    <option value="168">最近 1 週</option>
                    <option value="">全部時間</option>
                  </select>
                </div>
                
                <div className="form-group">
                  <label className="form-label">顯示數量</label>
                  <select 
                    className="form-select"
                    value={filters.limit?.toString() || '100'} 
                    onChange={(e) => setFilters(prev => ({ ...prev, limit: parseInt(e.target.value) }))}
                  >
                    <option value="50">50 條</option>
                    <option value="100">100 條</option>
                    <option value="200">200 條</option>
                    <option value="500">500 條</option>
                  </select>
                </div>
              </div>

              {/* Search */}
              <div className="search-group">
                <input
                  className="form-input"
                  placeholder="搜尋日誌內容..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  onKeyPress={(e) => e.key === 'Enter' && searchLogs()}
                />
                <button className="btn btn-primary" onClick={searchLogs} disabled={loading}>
                   搜尋
                </button>
                {isSearchMode && (
                  <button 
                    className="btn"
                    onClick={() => {
                      setIsSearchMode(false);
                      setSearchQuery('');
                      loadLogs();
                    }}
                  >
                     清除
                  </button>
                )}
              </div>

              {/* Status Info */}
              <div className="status-info">
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
            </div>

            {/* Logs Display */}
            <div className="card">
              <div className="card-title">
                 日誌內容
                {isSearchMode && <span style={{ marginLeft: '0.5rem', fontSize: '0.875rem', color: '#6b7280' }}>搜尋模式</span>}
              </div>
              
              {loading && logs.length === 0 ? (
                <div className="loading-spinner">
                  <div className="spinner" />
                  <p>載入中...</p>
                </div>
              ) : (
                <div className="logs-container">
                  {(isSearchMode ? searchResults : logs).map((entry, index) => 
                    renderLogEntry(entry, index)
                  )}
                  
                  {!isSearchMode && pagination.hasMore && (
                    <div style={{ textAlign: 'center', padding: '1rem' }}>
                      <button 
                        className="btn"
                        onClick={loadMoreLogs}
                        disabled={loading}
                      >
                        {loading ? <div className="spinner" /> : '載入更多'}
                      </button>
                    </div>
                  )}
                  
                  {(isSearchMode ? searchResults : logs).length === 0 && !loading && (
                    <div className="empty-state">
                      <p>{isSearchMode ? '沒有找到匹配的日誌' : '沒有日誌資料'}</p>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        )}

        {/* Stats Tab */}
        {activeTab === 'stats' && stats && (
          <div className="stats-grid">
            {/* File Stats */}
            <div className="card">
              <div className="card-title"> 檔案資訊</div>
              <p style={{ color: '#6b7280', marginBottom: '1rem' }}>
                總大小: {logService.formatFileSize(stats.total_size)}
              </p>
              <div>
                {Object.entries(stats.files).map(([name, file]) => (
                  <div key={name} className="stat-item">
                    <span style={{ fontWeight: '500' }}>{name}</span>
                    <span style={{ color: '#6b7280' }}>
                      {logService.formatFileSize(file.size)}
                    </span>
                  </div>
                ))}
              </div>
            </div>

            {/* Level Distribution */}
            <div className="card">
              <div className="card-title"> 日誌級別分佈</div>
              <div>
                {Object.entries(stats.level_distribution).map(([level, count]) => {
                  const levelColor = logService.getLogLevelColor(level);
                  const icon = logService.getLogLevelIcon(level);
                  return (
                    <div key={level} className="stat-item">
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                        <span className={`log-level-badge ${levelColor}`}>
                          {icon} {level}
                        </span>
                      </div>
                      <span style={{ fontWeight: '500' }}>{count.toLocaleString()}</span>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* API Usage */}
            <div className="card">
              <div className="card-title"> API 使用統計</div>
              <div>
                {Object.entries(stats.api_usage).map(([api, count]) => (
                  <div key={api} className="stat-item">
                    <span style={{ textTransform: 'capitalize' }}>{api}</span>
                    <span style={{ fontWeight: '500' }}>{count.toLocaleString()}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Recent Activity */}
            <div className="card">
              <div className="card-title"> 最近活動</div>
              <p style={{ color: '#6b7280', marginBottom: '1rem' }}>最新的系統活動記錄</p>
              <div>
                {stats.recent_activity.slice(0, 10).map((activity, index) => {
                  const levelColor = logService.getLogLevelColor(activity.level);
                  const icon = logService.getLogLevelIcon(activity.level);
                  return (
                    <div key={index} className="stat-item" style={{ flexDirection: 'column', alignItems: 'flex-start' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', width: '100%' }}>
                        <span className={`log-level-badge ${levelColor}`}>
                          {icon}
                        </span>
                        <span style={{ fontSize: '0.875rem', color: '#1f2937', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          {activity.message}
                        </span>
                      </div>
                      <span style={{ fontSize: '0.75rem', color: '#6b7280', marginTop: '0.25rem' }}>
                        {logService.formatTimestamp(activity.timestamp)}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default LogViewer;