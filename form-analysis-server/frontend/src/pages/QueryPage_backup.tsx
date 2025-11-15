// src/pages/QueryPage.tsx
import { useState, useEffect, useRef } from "react";
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
}

interface QueryResponse {
  total_count: number;
  page: number;
  page_size: number;
  records: QueryRecord[];
}

interface LotGroupResponse {
  lot_no: string;
  p1_count: number;
  p2_count: number;
  p3_count: number;
  total_count: number;
  latest_production_date?: string;
  created_at: string;
}

interface LotGroupListResponse {
  total_count: number;
  page: number;
  page_size: number;
  groups: LotGroupResponse[];
}

export function QueryPage() {
  // 搜尋相關狀態
  const [searchKeyword, setSearchKeyword] = useState("");
  const [searchPerformed, setSearchPerformed] = useState(false);
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [suggestionLoading, setSuggestionLoading] = useState(false);
  
  // 批號分組相關狀態
  const [lotGroups, setLotGroups] = useState<LotGroupResponse[]>([]);
  const [selectedLotNo, setSelectedLotNo] = useState<string>("");
  const [activeDataType, setActiveDataType] = useState<DataType | null>(null);
  
  // 記錄列表相關狀態
  const [records, setRecords] = useState<QueryRecord[]>([]);
  const [detailRecord, setDetailRecord] = useState<QueryRecord | null>(null);
  const [loading, setLoading] = useState(false);
  const [totalCount, setTotalCount] = useState(0);
  const [currentPage, setCurrentPage] = useState(1);
  
  const inputRef = useRef<HTMLInputElement>(null);
  const suggestionsRef = useRef<HTMLDivElement>(null);
  const pageSize = 10;

  const fetchRecords = async (page: number = 1, search: string = "") => {
    setLoading(true);
    try {
      const params = new URLSearchParams({
        page: page.toString(),
        page_size: pageSize.toString(),
        ...(search && { search })
      });
      
      const response = await fetch(`/api/records?${params}`);
      if (response.ok) {
        const data: QueryResponse = await response.json();
        setRecords(data.records);
        setTotalCount(data.total_count);
        setCurrentPage(data.page);
      } else {
        console.error("獲取記錄時出錯:", response.status);
      }
    } catch (error) {
      console.error("獲取記錄時出錯:", error);
    } finally {
      setLoading(false);
    }
  };

  const handleSearch = async () => {
    await fetchRecords(1, keyword.trim());
    setShowSuggestions(false);
  };

  const fetchSuggestions = async (query: string) => {
    // 只有在 lot_no 查詢模式下才顯示自動完成建議
    if (queryType !== 'lot_no' || !query.trim() || query.trim().length < 1) {
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
      
      const response = await fetch(`/api/records/suggestions?${params}`);
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

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    setKeyword(value);
    fetchSuggestions(value);
  };

  const handleSuggestionClick = (suggestion: string) => {
    setKeyword(suggestion);
    setShowSuggestions(false);
    fetchRecords(1, suggestion);
  };

  const handleInputFocus = () => {
    if (queryType === 'lot_no' && keyword.trim().length >= 1) {
      fetchSuggestions(keyword);
    }
  };

  const handleInputBlur = () => {
    // 延遲關閉建議，讓用戶有時間點擊建議
    setTimeout(() => setShowSuggestions(false), 200);
  };

  const handleViewDetail = async (record: QueryRecord) => {
    try {
      const response = await fetch(`/api/records/${record.id}`);
      if (response.ok) {
        const detailData = await response.json();
        setDetailRecord(detailData);
      } else {
        console.error("獲取記錄詳細資料時出錯:", response.status);
      }
    } catch (error) {
      console.error("獲取記錄詳細資料時出錯:", error);
    }
  };

  // 初始載入
  useEffect(() => {
    fetchRecords();
  }, []);

  return (
    <div className="query-page">
      <section className="query-search-section">
        <label className="query-search-label">
          資料查詢
          
          {/* 查詢類型選擇 */}
          <div className="query-type-selector">
            <label className="query-type-option">
              <input
                type="radio"
                name="queryType"
                value="lot_no"
                checked={queryType === 'lot_no'}
                onChange={(e) => {
                  setQueryType(e.target.value as QueryType);
                  setKeyword('');
                  setShowSuggestions(false);
                  setSuggestions([]);
                }}
              />
              依批號查詢 (Lot No)
            </label>
            <label className="query-type-option">
              <input
                type="radio"
                name="queryType"
                value="product_name"
                checked={queryType === 'product_name'}
                onChange={(e) => {
                  setQueryType(e.target.value as QueryType);
                  setKeyword('');
                  setShowSuggestions(false);
                  setSuggestions([]);
                }}
              />
              依產品名稱查詢
            </label>
            <label className="query-type-option">
              <input
                type="radio"
                name="queryType"
                value="all"
                checked={queryType === 'all'}
                onChange={(e) => {
                  setQueryType(e.target.value as QueryType);
                  setKeyword('');
                  setShowSuggestions(false);
                  setSuggestions([]);
                }}
              />
              全域查詢
            </label>
          </div>

          {/* 查詢說明 */}
          <div className="query-description">
            {queryType === 'lot_no' && (
              <p>🔍 <strong>批號查詢：</strong>支援精確或模糊搜尋，例如: 2503033_01 或 2503033</p>
            )}
            {queryType === 'product_name' && (
              <p>🔍 <strong>產品名稱查詢：</strong>支援產品名稱的模糊搜尋</p>
            )}
            {queryType === 'all' && (
              <p>🔍 <strong>全域查詢：</strong>同時搜尋批號和產品名稱</p>
            )}
          </div>

          <div className="query-search-input-wrapper autocomplete-wrapper">
            <input
              ref={inputRef}
              type="text"
              className="query-search-input"
              placeholder={
                queryType === 'lot_no' ? "輸入 Lot No 查詢 (例: 2503033_01)" :
                queryType === 'product_name' ? "輸入產品名稱查詢" :
                "輸入 Lot No 或產品名稱查詢"
              }
              value={keyword}
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
            {showSuggestions && queryType === 'lot_no' && (
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
            {keyword && (
              <button 
                className="btn-secondary" 
                onClick={() => {
                  setKeyword('');
                  setRecords([]);
                  setTotalCount(0);
                  setShowSuggestions(false);
                  setSuggestions([]);
                  fetchRecords(); // 重新載入所有記錄
                }}
              >
                清除
              </button>
            )}
          </div>
        </label>
      </section>

      <section className="query-result-section">
        <div className="query-table-wrapper">
          {loading ? (
            <p className="section-empty">載入中...</p>
          ) : records.length === 0 ? (
            <p className="section-empty">沒有找到符合條件的資料</p>
          ) : (
            <>
              <div className="query-result-header">
                <p>共找到 {totalCount} 筆記錄</p>
              </div>
              <table className="query-table">
                <thead>
                  <tr>
                    <th>Lot No</th>
                    {/* <th>Product Name</th>
                    <th>Quantity</th> */}
                    <th>Production Date</th>
                    <th>Created At</th>
                    <th>操作</th>
                  </tr>
                </thead>
                <tbody>
                  {records.map((record) => (
                    <tr key={record.id}>
                      <td>{record.lot_no}</td>
                      <td>{record.product_name}</td>
                      <td>{record.quantity}</td>
                      <td>{record.production_date}</td>
                      <td>{new Date(record.created_at).toLocaleString()}</td>
                      <td>
                        <button
                          className="icon-button"
                          title="檢視詳細"
                          onClick={() => handleViewDetail(record)}
                        >
                          🔍
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              
              {totalCount > pageSize && (
                <div className="pagination">
                  <button
                    onClick={() => fetchRecords(currentPage - 1, keyword)}
                    disabled={currentPage <= 1}
                  >
                    上一頁
                  </button>
                  <span>第 {currentPage} 頁</span>
                  <button
                    onClick={() => fetchRecords(currentPage + 1, keyword)}
                    disabled={currentPage * pageSize >= totalCount}
                  >
                    下一頁
                  </button>
                </div>
              )}
            </>
          )}
        </div>
      </section>

      <Modal
        open={detailRecord !== null}
        title="資料細項"
        onClose={() => setDetailRecord(null)}
      >
        {detailRecord && (
          <div className="query-detail">
            <p>
              <strong>Lot No：</strong>
              {detailRecord.lot_no}
            </p>
            <p>
              <strong>Product Name：</strong>
              {detailRecord.product_name}
            </p>
            <p>
              <strong>Quantity：</strong>
              {detailRecord.quantity}
            </p>
            <p>
              <strong>Production Date：</strong>
              {detailRecord.production_date}
            </p>
            <p>
              <strong>Created At：</strong>
              {new Date(detailRecord.created_at).toLocaleString()}
            </p>
          </div>
        )}
      </Modal>
    </div>
  );
}
