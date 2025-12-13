// src/pages/QueryPage.tsx
import { useState, useRef } from "react";
import { Modal } from "../components/common/Modal";
import "../styles/query-page.css";

// 數據類型枚舉
type DataType = 'P1' | 'P2' | 'P3';

interface QueryRecord {
  id: string;
  lot_no: string;
  data_type: DataType;
  production_date?: string;
  created_at: string;
  display_name: string;
  
  // P1專用欄位
  product_name?: string;
  quantity?: number;
  notes?: string;
  
  // P2專用欄位
  sheet_width?: number;
  thickness1?: number;
  thickness2?: number;
  thickness3?: number;
  thickness4?: number;
  thickness5?: number;
  thickness6?: number;
  thickness7?: number;
  appearance?: number;
  rough_edge?: number;
  slitting_result?: number;
  
  // P3專用欄位
  p3_no?: string;
  
  // 額外資料欄位 (來自CSV的其他欄位，包含溫度數據等)
  additional_data?: { [key: string]: any };
}

interface QueryResponse {
  total_count: number;
  page: number;
  page_size: number;
  records: QueryRecord[];
}

export function QueryPage() {
  // 搜尋相關狀態
  const [searchKeyword, setSearchKeyword] = useState("");
  const [searchPerformed, setSearchPerformed] = useState(false);
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [suggestionLoading, setSuggestionLoading] = useState(false);
  
  // 記錄列表相關狀態
  const [records, setRecords] = useState<QueryRecord[]>([]);
  const [expandedRecordId, setExpandedRecordId] = useState<string | null>(null);
  const [collapsedSections, setCollapsedSections] = useState<{ [key: string]: boolean }>({});
  const [detailRecord, setDetailRecord] = useState<QueryRecord | null>(null);
  const [loading, setLoading] = useState(false);
  const [totalCount, setTotalCount] = useState(0);
  const [currentPage, setCurrentPage] = useState(1);
  
  const inputRef = useRef<HTMLInputElement>(null);
  const suggestionsRef = useRef<HTMLDivElement>(null);
  const pageSize = 50;

  // 搜尋記錄
  const searchRecords = async (search: string, page: number = 1) => {
    setLoading(true);
    try {
      const params = new URLSearchParams({
        page: page.toString(),
        page_size: pageSize.toString()
      });
      
      if (search) {
        params.append('lot_no', search);
      }
      
      const response = await fetch(`/api/query/records?${params}`);
      if (response.ok) {
        const data: QueryResponse = await response.json();
        setRecords(data.records);
        setTotalCount(data.total_count);
        setCurrentPage(data.page);
        setSearchPerformed(true);
      } else {
        console.error("搜尋記錄時出錯:", response.status);
      }
    } catch (error) {
      console.error("搜尋記錄時出錯:", error);
    } finally {
      setLoading(false);
    }
  };

  // 獲取搜尋建議
  const fetchSuggestions = async (query: string) => {
    if (!query.trim() || query.trim().length < 1) {
      setSuggestions([]);
      setShowSuggestions(false);
      return;
    }

    setSuggestionLoading(true);
    try {
      const params = new URLSearchParams({
        query: query.trim(),
        limit: '10'
      });
      
      const response = await fetch(`/api/query/lots/suggestions?${params}`);
      if (response.ok) {
        const data: string[] = await response.json();
        setSuggestions(data);
        setShowSuggestions(data.length > 0);
      } else {
        console.error("獲取建議時出錯:", response.status);
        setSuggestions([]);
        setShowSuggestions(false);
      }
    } catch (error) {
      console.error("獲取建議時出錯:", error);
      setSuggestions([]);
      setShowSuggestions(false);
    } finally {
      setSuggestionLoading(false);
    }
  };

  // 處理搜尋
  const handleSearch = async () => {
    if (searchKeyword.trim()) {
      await searchRecords(searchKeyword.trim());
      setShowSuggestions(false);
    }
  };

  // 處理輸入變化
  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    setSearchKeyword(value);
    fetchSuggestions(value);
  };

  // 處理建議點擊
  const handleSuggestionClick = (suggestion: string) => {
    setSearchKeyword(suggestion);
    setShowSuggestions(false);
    searchRecords(suggestion);
  };

  // 處理輸入焦點
  const handleInputFocus = () => {
    if (searchKeyword.trim().length >= 1) {
      fetchSuggestions(searchKeyword);
    }
  };

  // 處理輸入失焦
  const handleInputBlur = () => {
    setTimeout(() => setShowSuggestions(false), 200);
  };

  // 切換展開狀態
  const toggleExpand = (recordId: string) => {
    setExpandedRecordId(prev => prev === recordId ? null : recordId);
    // 重置收起狀態
    if (expandedRecordId !== recordId) {
      setCollapsedSections({});
    }
  };

  // 切換區塊收起狀態
  const toggleSection = (recordId: string, sectionKey: string) => {
    const key = `${recordId}-${sectionKey}`;
    setCollapsedSections(prev => ({
      ...prev,
      [key]: !prev[key]
    }));
  };

  // 判斷區塊是否收起
  const isSectionCollapsed = (recordId: string, sectionKey: string): boolean => {
    const key = `${recordId}-${sectionKey}`;
    return collapsedSections[key] || false;
  };

  // 分組資料的輔助函數
  const groupDataByPrefix = (data: { [key: string]: any }) => {
    const groups: { [key: string]: { [key: string]: any } } = {
      actual_temp: {},
      set_temp: {},
      other: {}
    };

    Object.entries(data).forEach(([key, value]) => {
      if (key.startsWith('actual_temp_') || key.startsWith('Actual_Temp_')) {
        groups.actual_temp[key] = value;
      } else if (key.startsWith('set_temp_') || key.startsWith('Set_Temp_')) {
        groups.set_temp[key] = value;
      } else {
        groups.other[key] = value;
      }
    });

    return groups;
  };

  // 渲染分組區塊
  const renderGroupedSection = (
    recordId: string,
    title: string,
    sectionKey: string,
    data: { [key: string]: any },
    icon: string = "ℹ",
    vertical: boolean = false
  ) => {
    const isCollapsed = isSectionCollapsed(recordId, sectionKey);
    const fieldCount = Object.keys(data).length;

    return (
      <div className="data-section" key={sectionKey}>
        <div className="section-header">
          <div className="section-title-wrapper">
            <span className="section-icon">{icon}</span>
            <h5>{title}</h5>
            <span className="field-count-badge">{fieldCount}</span>
          </div>
          <button
            className="btn-collapse"
            onClick={() => toggleSection(recordId, sectionKey)}
          >
            {isCollapsed ? '展開' : '收起'}
          </button>
        </div>
        {!isCollapsed && (
          <div className="section-content">
            {vertical ? (
              <table className="data-table data-table-vertical">
                <tbody>
                  {Object.entries(data).map(([key, value]) => (
                    <tr key={key}>
                      <th>{key}</th>
                      <td>{typeof value === 'number' ? value.toLocaleString() : String(value)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <table className="data-table">
                <thead>
                  <tr>
                    {Object.keys(data).map(key => (
                      <th key={key}>{key}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    {Object.values(data).map((value, idx) => (
                      <td key={idx}>
                        {typeof value === 'number' ? value.toLocaleString() : String(value)}
                      </td>
                    ))}
                  </tr>
                </tbody>
              </table>
            )}
          </div>
        )}
      </div>
    );
  };

  // 渲染P1展開內容
  const renderP1ExpandedContent = (record: QueryRecord) => {
    if (!record.additional_data) {
      return <p className="no-data">此記錄沒有額外的CSV資料</p>;
    }

    // 分組其他資料
    const grouped = groupDataByPrefix(record.additional_data);
    
    // 基本資料
    const basicData = {
      lot_no: record.lot_no,
      updated_at: new Date(record.created_at).toLocaleString('zh-TW'),
      created_at: new Date(record.created_at).toLocaleString('zh-TW')
    };

    // 合併 actual_temp 和 set_temp 作為押出機生產條件
    const extrusionConditions = {
      ...grouped.actual_temp,
      ...grouped.set_temp
    };

    return (
      <div className="grouped-data-container">
        {renderGroupedSection(record.id, '基本資料', 'basic', basicData, '')}
        
        {Object.keys(extrusionConditions).length > 0 && 
          renderGroupedSection(record.id, '押出機生產條件', 'extrusion', extrusionConditions, '', true)}
        
        {Object.keys(grouped.other).length > 0 && 
          renderGroupedSection(record.id, '其他參數', 'other', grouped.other, '')}
      </div>
    );
  };

  // 渲染P2展開內容
  const renderP2ExpandedContent = (record: QueryRecord) => {
    if (!record.additional_data) {
      return <p className="no-data">此記錄沒有額外的CSV資料</p>;
    }

    // 基本資料
    const basicData = {
      lot_no: record.lot_no,
      updated_at: new Date(record.created_at).toLocaleString('zh-TW'),
      created_at: new Date(record.created_at).toLocaleString('zh-TW')
    };

    // 檢查是否為 rows 陣列結構
    const rows = record.additional_data.rows || [];
    const hasRows = Array.isArray(rows) && rows.length > 0;

    return (
      <div className="grouped-data-container">
        {renderGroupedSection(record.id, '基本資料', 'basic', basicData, 'ℹ️')}
        
        {hasRows && (
          <div className="data-section">
            <div className="section-header">
              <div className="section-title-wrapper">
                <span className="section-icon">📊</span>
                <h5>檢測數據</h5>
                <span className="field-count-badge">{rows.length} 筆</span>
              </div>
              <button
                className="btn-collapse"
                onClick={() => toggleSection(record.id, 'rows_data')}
              >
                {isSectionCollapsed(record.id, 'rows_data') ? '展開' : '收起'}
              </button>
            </div>
            {!isSectionCollapsed(record.id, 'rows_data') && (
              <div className="section-content">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>#</th>
                      {Object.keys(rows[0]).map(key => (
                        <th key={key}>{key}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((row: any, idx: number) => (
                      <tr key={idx}>
                        <td>{idx + 1}</td>
                        {Object.values(row).map((value: any, vidx: number) => (
                          <td key={vidx}>
                            {typeof value === 'number' ? value.toLocaleString() : String(value)}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}
      </div>
    );
  };

  // 渲染P3展開內容
  const renderP3ExpandedContent = (record: QueryRecord) => {
    if (!record.additional_data) {
      return <p className="no-data">此記錄沒有額外的CSV資料</p>;
    }

    // 基本資料
    const basicData = {
      lot_no: record.lot_no,
      p3_no: record.p3_no || '-',
      updated_at: new Date(record.created_at).toLocaleString('zh-TW'),
      created_at: new Date(record.created_at).toLocaleString('zh-TW')
    };

    // 檢查是否有 rows 陣列
    const rows = record.additional_data.rows || [];
    const rowCount = Array.isArray(rows) ? rows.length : 0;

    return (
      <div className="grouped-data-container">
        <div className="p3-header">
          <div className="p3-badges">
            <span className="badge badge-primary">批號: {record.lot_no}</span>
            <span className="badge badge-success">檢查筆數: {rowCount}筆</span>
          </div>
          <div className="p3-stats">
            <div className="stat-item">
              <span className="stat-label">原始筆數:</span>
              <span className="stat-value">{rowCount}</span>
            </div>
            <div className="stat-item">
              <span className="stat-label">有效筆數:</span>
              <span className="stat-value">{rowCount}</span>
            </div>
          </div>
        </div>

        {renderGroupedSection(record.id, '基本資料', 'basic', basicData, 'ℹ️')}
        
        {/* 渲染檢查項目表格 */}
        {Array.isArray(rows) && rows.length > 0 && (
          <div className="data-section" key="check_items">
            <div className="section-header">
              <div className="section-title-wrapper">
                <span className="section-icon">✅</span>
                <h5>檢查項目明細</h5>
                <span className="field-count-badge">{rows.length} 筆</span>
              </div>
              <button
                className="btn-collapse"
                onClick={() => toggleSection(record.id, 'check_items')}
              >
                {collapsedSections[`${record.id}-check_items`] ? '▼' : '▲'}
              </button>
            </div>
            {!collapsedSections[`${record.id}-check_items`] && (
              <div className="section-content">
                <div className="table-container">
                  <table className="data-table">
                    <thead>
                      <tr>
                        {Object.keys(rows[0]).map(header => (
                          <th key={header}>{header}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {rows.map((row: any, idx: number) => (
                        <tr key={idx}>
                          {Object.keys(rows[0]).map(header => (
                            <td key={header}>
                              {typeof row[header] === 'number' 
                                ? row[header].toLocaleString() 
                                : row[header] || '-'}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    );
  };

  // 根據資料類型渲染展開內容
  const renderExpandedContent = (record: QueryRecord) => {
    switch (record.data_type) {
      case 'P1':
        return renderP1ExpandedContent(record);
      case 'P2':
        return renderP2ExpandedContent(record);
      case 'P3':
        return renderP3ExpandedContent(record);
      default:
        return <p className="no-data">未知的資料類型</p>;
    }
  };

  // 清除搜尋
  const handleClear = () => {
    setSearchKeyword('');
    setSearchPerformed(false);
    setRecords([]);
    setTotalCount(0);
    setCurrentPage(1);
    setExpandedRecordId(null);
    setCollapsedSections({});
    setShowSuggestions(false);
    setSuggestions([]);
  };

  // 渲染額外資料欄位
  const renderAdditionalData = (additionalData: { [key: string]: any } | undefined) => {
    if (!additionalData || Object.keys(additionalData).length === 0) {
      return null;
    }

    // 檢查是否有 rows 陣列 (P3 資料格式)
    if (additionalData.rows && Array.isArray(additionalData.rows) && additionalData.rows.length > 0) {
      const rows = additionalData.rows;
      const headers = Object.keys(rows[0]);

      return (
        <div className="additional-data-section">
          <div className="section-title">檢查項目明細</div>
          <div className="table-container">
            <table className="data-table">
              <thead>
                <tr>
                  {headers.map(header => (
                    <th key={header}>{header}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((row: any, idx: number) => (
                  <tr key={idx}>
                    {headers.map(header => (
                      <td key={header}>
                        {typeof row[header] === 'number' 
                          ? row[header].toLocaleString() 
                          : row[header] || '-'}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      );
    }

    // 一般鍵值對資料顯示
    return (
      <div className="additional-data-section">
        <div className="section-title">CSV 表格完整資料</div>
        <div className="additional-data-grid">
          {Object.entries(additionalData).map(([key, value]) => (
            <div key={key} className="detail-row">
              <strong>{key}：</strong>
              <span>{typeof value === 'number' ? value.toLocaleString() : String(value)}</span>
            </div>
          ))}
        </div>
      </div>
    );
  };

  // 渲染P1詳細資料
  const renderP1Details = (record: QueryRecord) => (
    <div className="detail-grid">
      <div className="detail-row">
        <strong>批號：</strong>
        <span>{record.lot_no}</span>
      </div>
      {record.notes && (
        <div className="detail-row">
          <strong>備註：</strong>
          <span>{record.notes}</span>
        </div>
      )}
      <div className="detail-row">
        <strong>建立時間：</strong>
        <span>{new Date(record.created_at).toLocaleString()}</span>
      </div>
      {renderAdditionalData(record.additional_data)}
    </div>
  );

  // 渲染P2詳細資料
  const renderP2Details = (record: QueryRecord) => (
    <div className="detail-grid">
      <div className="detail-row">
        <strong>批號：</strong>
        <span>{record.lot_no}</span>
      </div>
      <div className="detail-row">
        <strong>片材寬度(mm)：</strong>
        <span>{record.sheet_width}</span>
      </div>
      <div className="thickness-section">
        <strong>厚度測量(μm)：</strong>
        <div className="thickness-grid">
          <span>厚度1: {record.thickness1}</span>
          <span>厚度2: {record.thickness2}</span>
          <span>厚度3: {record.thickness3}</span>
          <span>厚度4: {record.thickness4}</span>
          <span>厚度5: {record.thickness5}</span>
          <span>厚度6: {record.thickness6}</span>
          <span>厚度7: {record.thickness7}</span>
        </div>
      </div>
      <div className="detail-row">
        <strong>外觀：</strong>
        <span>{record.appearance === 1 ? '通過' : '不通過'}</span>
      </div>
      <div className="detail-row">
        <strong>粗糙邊緣：</strong>
        <span>{record.rough_edge === 1 ? '通過' : '不通過'}</span>
      </div>
      <div className="detail-row">
        <strong>切割結果：</strong>
        <span>{record.slitting_result === 1 ? '通過' : '不通過'}</span>
      </div>
      <div className="detail-row">
        <strong>建立時間：</strong>
        <span>{new Date(record.created_at).toLocaleString()}</span>
      </div>
      {renderAdditionalData(record.additional_data)}
    </div>
  );

  // 渲染P3詳細資料
  const renderP3Details = (record: QueryRecord) => (
    <div className="detail-grid">
      <div className="detail-row">
        <strong>批號：</strong>
        <span>{record.lot_no}</span>
      </div>
      <div className="detail-row">
        <strong>P3編號：</strong>
        <span>{record.p3_no}</span>
      </div>
      {record.notes && (
        <div className="detail-row">
          <strong>備註：</strong>
          <span>{record.notes}</span>
        </div>
      )}
      <div className="detail-row">
        <strong>建立時間：</strong>
        <span>{new Date(record.created_at).toLocaleString()}</span>
      </div>
      {renderAdditionalData(record.additional_data)}
    </div>
  );

  return (
    <div className="query-page">
      {/* 搜尋區域 */}
      <section className="query-search-section">
        <label className="query-search-label">
          資料查詢
          
          <div className="query-description">
            <p> <strong>批號查詢：</strong>輸入批號進行模糊搜尋，查詢後可查看 P1/P2/P3 分類資料</p>
          </div>

          <div className="query-search-input-wrapper autocomplete-wrapper">
            <input
              ref={inputRef}
              type="text"
              className="query-search-input"
              placeholder="輸入 Lot No 查詢 (例: 2503033)"
              value={searchKeyword}
              onChange={handleInputChange}
              onFocus={handleInputFocus}
              onBlur={handleInputBlur}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  handleSearch();
                } else if (e.key === "Escape") {
                  setShowSuggestions(false);
                }
              }}
            />
            
            {/* 自動完成建議 */}
            {showSuggestions && (
              <div ref={suggestionsRef} className="autocomplete-suggestions">
                {suggestionLoading ? (
                  <div className="suggestion-item loading">載入建議中...</div>
                ) : suggestions.length > 0 ? (
                  suggestions.map((suggestion, index) => (
                    <div
                      key={index}
                      className="suggestion-item"
                      onMouseDown={() => handleSuggestionClick(suggestion)}
                    >
                      {suggestion}
                    </div>
                  ))
                ) : (
                  <div className="suggestion-item no-results">沒有找到相符的建議</div>
                )}
              </div>
            )}
            
            <button 
              className="btn-primary" 
              onClick={handleSearch}
              disabled={loading}
            >
              {loading ? "查詢中..." : "查詢"}
            </button>
            
            {/* 清除按鈕 */}
            {searchKeyword && (
              <button 
                className="btn-secondary" 
                onClick={handleClear}
              >
                清除
              </button>
            )}
          </div>
        </label>
      </section>

      {/* 結果區域 */}
      {searchPerformed && (
        <section className="query-result-section">
          {loading ? (
            <p className="section-empty">載入中...</p>
          ) : records.length === 0 ? (
            <p className="section-empty">沒有找到符合條件的資料</p>
          ) : (
            <div className="records-container">
              <div className="records-header">
                <h3>{searchKeyword ? `${searchKeyword} - ` : ''}共找到 {totalCount} 筆資料</h3>
              </div>
              
              <table className="records-table">
                <thead>
                  <tr>
                    <th>Lot No</th>
                    <th>資料類型</th>
                    <th>生產日期</th>
                    <th>建立時間</th>
                    <th>操作</th>
                  </tr>
                </thead>
                <tbody>
                  {records.map((record) => (
                    <>
                      <tr key={record.id}>
                        <td>{record.lot_no}</td>
                        <td>
                          <span className={`data-type-label ${record.data_type.toLowerCase()}`}>
                            {record.data_type}
                          </span>
                        </td>
                        <td>{record.production_date || '未設定'}</td>
                        <td>{new Date(record.created_at).toLocaleString('zh-TW', {
                          year: 'numeric',
                          month: '2-digit',
                          day: '2-digit',
                          hour: '2-digit',
                          minute: '2-digit',
                          hour12: false
                        })}</td>
                        <td>
                          <button
                            className="btn-expand"
                            title="展開查看CSV資料"
                            onClick={() => toggleExpand(record.id)}
                          >
                            {expandedRecordId === record.id ? '收起' : '展開'}
                          </button>
                        </td>
                      </tr>
                      
                      {/* 展開行 - 顯示分組資料 */}
                      {expandedRecordId === record.id && (
                        <tr className="expanded-row">
                          <td colSpan={5}>
                            <div className="expanded-data-container">
                              {renderExpandedContent(record)}
                            </div>
                          </td>
                        </tr>
                      )}
                    </>
                  ))}
                </tbody>
              </table>
              
              {/* 分頁控制 */}
              {totalCount > pageSize && (
                <div className="pagination">
                  <button
                    onClick={() => searchRecords(searchKeyword, currentPage - 1)}
                    disabled={currentPage <= 1}
                  >
                    上一頁
                  </button>
                  <span>第 {currentPage} 頁</span>
                  <button
                    onClick={() => searchRecords(searchKeyword, currentPage + 1)}
                    disabled={currentPage * pageSize >= totalCount}
                  >
                    下一頁
                  </button>
                </div>
              )}
            </div>
          )}
        </section>
      )}

      {/* 詳細資料模態框 */}
      <Modal
        open={detailRecord !== null}
        title={`${detailRecord?.data_type} 資料詳情`}
        onClose={() => setDetailRecord(null)}
      >
        {detailRecord && (
          <div className="record-detail">
            {detailRecord.data_type === 'P1' && renderP1Details(detailRecord)}
            {detailRecord.data_type === 'P2' && renderP2Details(detailRecord)}
            {detailRecord.data_type === 'P3' && renderP3Details(detailRecord)}
          </div>
        )}
      </Modal>
    </div>
  );
}
