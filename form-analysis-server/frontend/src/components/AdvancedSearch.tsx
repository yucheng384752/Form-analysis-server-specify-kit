import React, { useState, useEffect } from 'react';
import './advanced-search.css';

export interface AdvancedSearchParams {
  lot_no?: string;
  production_date_from?: string;
  production_date_to?: string;
  machine_no?: string;
  mold_no?: string;
  product_id?: string;
  p3_specification?: string;
  data_type?: string;
}

interface AdvancedSearchProps {
  onSearch: (params: AdvancedSearchParams) => void;
  onReset: () => void;
  isExpanded: boolean;
  onToggle: () => void;
}

export const AdvancedSearch: React.FC<AdvancedSearchProps> = ({
  onSearch,
  onReset,
  isExpanded,
  onToggle,
}) => {
  // 批號
  const [lotNo, setLotNo] = useState('');
  
  // 日期範圍 - 年月日分開
  const [dateFromYear, setDateFromYear] = useState('');
  const [dateFromMonth, setDateFromMonth] = useState('');
  const [dateFromDay, setDateFromDay] = useState('');
  const [dateToYear, setDateToYear] = useState('');
  const [dateToMonth, setDateToMonth] = useState('');
  const [dateToDay, setDateToDay] = useState('');
  
  // 其他搜尋條件
  const [machineNo, setMachineNo] = useState('');
  const [moldNo, setMoldNo] = useState('');
  const [productId, setProductId] = useState('');
  const [p3Specification, setP3Specification] = useState('');
  const [dataType, setDataType] = useState('');

  // 選項狀態
  const [machineOptions, setMachineOptions] = useState<string[]>([]);
  const [moldOptions, setMoldOptions] = useState<string[]>([]);
  const [specOptions, setSpecOptions] = useState<string[]>([]);

  // 載入選項
  useEffect(() => {
    if (isExpanded) {
      const fetchOptions = async () => {
        try {
          // 平行請求所有選項
          const [machineRes, moldRes, specRes] = await Promise.all([
            fetch('/api/v2/query/options/machine_no'),
            fetch('/api/v2/query/options/mold_no'),
            fetch('/api/v2/query/options/p3_specification')
          ]);

          if (machineRes.ok) setMachineOptions(await machineRes.json());
          if (moldRes.ok) setMoldOptions(await moldRes.json());
          if (specRes.ok) setSpecOptions(await specRes.json());
        } catch (error) {
          console.error('Failed to fetch search options:', error);
        }
      };

      fetchOptions();
    }
  }, [isExpanded]);

  // 驗證至少填寫一個條件
  const validateSearchParams = (): boolean => {
    return !!(
      lotNo.trim() ||
      dateFromYear || dateFromMonth || dateFromDay ||
      dateToYear || dateToMonth || dateToDay ||
      machineNo.trim() ||
      moldNo.trim() ||
      productId.trim() ||
      p3Specification.trim() ||
      dataType
    );
  };

  // 組合日期字串
  const buildDateString = (year: string, month: string, day: string): string | undefined => {
    if (!year && !month && !day) return undefined;
    
    const y = year || '0000';
    const m = month ? month.padStart(2, '0') : '01';
    const d = day ? day.padStart(2, '0') : '01';
    
    return `${y}-${m}-${d}`;
  };

  // 處理搜尋
  const handleSearch = () => {
    if (!validateSearchParams()) {
      alert('請至少填寫一個搜尋條件');
      return;
    }

    const params: AdvancedSearchParams = {};
    
    // Lot No 正規化：去除前後空白，並將中間的空白轉換為底線
    // 例如: "2507313 02" -> "2507313_02"
    if (lotNo.trim()) {
      let normalizedLot = lotNo.trim();
      // 將連續的空白替換為單一底線
      normalizedLot = normalizedLot.replace(/\s+/g, '_');
      params.lot_no = normalizedLot;
    }
    
    const dateFrom = buildDateString(dateFromYear, dateFromMonth, dateFromDay);
    if (dateFrom) params.production_date_from = dateFrom;
    
    const dateTo = buildDateString(dateToYear, dateToMonth, dateToDay);
    if (dateTo) params.production_date_to = dateTo;
    
    // 其他欄位僅去除前後空白，後端已支援不分大小寫搜尋 (ilike)
    if (machineNo.trim()) params.machine_no = machineNo.trim();
    if (moldNo.trim()) params.mold_no = moldNo.trim();
    if (productId.trim()) params.product_id = productId.trim();
    if (p3Specification.trim()) params.p3_specification = p3Specification.trim();
    if (dataType) params.data_type = dataType;

    onSearch(params);
  };

  // 重置所有欄位
  const handleReset = () => {
    setLotNo('');
    setDateFromYear('');
    setDateFromMonth('');
    setDateFromDay('');
    setDateToYear('');
    setDateToMonth('');
    setDateToDay('');
    setMachineNo('');
    setMoldNo('');
    setProductId('');
    setP3Specification('');
    setDataType('');
    onReset();
  };

  return (
    <div className="advanced-search">
      <button 
        className="advanced-search-toggle"
        onClick={onToggle}
        type="button"
      >
        <span className={`toggle-icon ${isExpanded ? 'expanded' : ''}`}>▶</span>
        進階搜尋
      </button>

      {isExpanded && (
        <div className="advanced-search-panel">
          <div className="search-grid">
            {/* 批號 */}
            <div className="search-field">
              <label htmlFor="adv-lot-no">批號</label>
              <input
                id="adv-lot-no"
                type="text"
                value={lotNo}
                onChange={(e) => setLotNo(e.target.value)}
                placeholder="輸入批號 (模糊搜尋)"
              />
            </div>

            {/* 生產日期起始 */}
            <div className="search-field date-field">
              <label>生產日期 (起始)</label>
              <div className="date-inputs">
                <input
                  type="number"
                  value={dateFromYear}
                  onChange={(e) => setDateFromYear(e.target.value)}
                  placeholder="年"
                  min="1900"
                  max="2100"
                  className="date-year"
                />
                <span className="date-separator">/</span>
                <input
                  type="number"
                  value={dateFromMonth}
                  onChange={(e) => setDateFromMonth(e.target.value)}
                  placeholder="月"
                  min="1"
                  max="12"
                  className="date-month"
                />
                <span className="date-separator">/</span>
                <input
                  type="number"
                  value={dateFromDay}
                  onChange={(e) => setDateFromDay(e.target.value)}
                  placeholder="日"
                  min="1"
                  max="31"
                  className="date-day"
                />
              </div>
            </div>

            {/* 生產日期結束 */}
            <div className="search-field date-field">
              <label>生產日期 (結束)</label>
              <div className="date-inputs">
                <input
                  type="number"
                  value={dateToYear}
                  onChange={(e) => setDateToYear(e.target.value)}
                  placeholder="年"
                  min="1900"
                  max="2100"
                  className="date-year"
                />
                <span className="date-separator">/</span>
                <input
                  type="number"
                  value={dateToMonth}
                  onChange={(e) => setDateToMonth(e.target.value)}
                  placeholder="月"
                  min="1"
                  max="12"
                  className="date-month"
                />
                <span className="date-separator">/</span>
                <input
                  type="number"
                  value={dateToDay}
                  onChange={(e) => setDateToDay(e.target.value)}
                  placeholder="日"
                  min="1"
                  max="31"
                  className="date-day"
                />
              </div>
            </div>

            {/* 機台號碼 */}
            <div className="search-field">
              <label htmlFor="adv-machine-no">機台號碼</label>
              <input
                id="adv-machine-no"
                type="text"
                value={machineNo}
                onChange={(e) => setMachineNo(e.target.value)}
                placeholder="輸入機台號碼 (模糊搜尋)"
                list="machine-options"
              />
              <datalist id="machine-options">
                {machineOptions.map((opt, idx) => (
                  <option key={idx} value={opt} />
                ))}
              </datalist>
            </div>

            {/* 下膠編號 (Bottom Tape) */}
            <div className="search-field">
              <label htmlFor="adv-mold-no">下膠編號</label>
              <input
                id="adv-mold-no"
                type="text"
                value={moldNo}
                onChange={(e) => setMoldNo(e.target.value)}
                placeholder="輸入下膠編號 (模糊搜尋)"
                list="mold-options"
              />
              <datalist id="mold-options">
                {moldOptions.map((opt, idx) => (
                  <option key={idx} value={opt} />
                ))}
              </datalist>
            </div>

            {/* 產品編號 */}
            <div className="search-field">
              <label htmlFor="adv-product-id">產品編號</label>
              <input
                id="adv-product-id"
                type="text"
                value={productId}
                onChange={(e) => setProductId(e.target.value)}
                placeholder="輸入產品編號 (模糊搜尋)"
              />
            </div>

            {/* P3 規格 */}
            <div className="search-field">
              <label htmlFor="adv-p3-specification">P3 規格</label>
              <input
                id="adv-p3-specification"
                type="text"
                value={p3Specification}
                onChange={(e) => setP3Specification(e.target.value)}
                placeholder="輸入 P3 規格 (模糊搜尋)"
                list="spec-options"
              />
              <datalist id="spec-options">
                {specOptions.map((opt, idx) => (
                  <option key={idx} value={opt} />
                ))}
              </datalist>
            </div>

            {/* 資料類型 */}
            <div className="search-field">
              <label htmlFor="adv-data-type">資料類型</label>
              <select
                id="adv-data-type"
                value={dataType}
                onChange={(e) => setDataType(e.target.value)}
              >
                <option value="">全部</option>
                <option value="P1">P1</option>
                <option value="P2">P2</option>
                <option value="P3">P3</option>
              </select>
            </div>
          </div>

          {/* 操作按鈕 */}
          <div className="search-actions">
            <button 
              className="btn-reset"
              onClick={handleReset}
              type="button"
            >
              重置
            </button>
            <button 
              className="btn-search"
              onClick={handleSearch}
              type="button"
            >
              搜尋
            </button>
          </div>
        </div>
      )}
    </div>
  );
};
