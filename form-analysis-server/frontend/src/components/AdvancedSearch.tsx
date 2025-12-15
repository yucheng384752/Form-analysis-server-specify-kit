import React, { useState } from 'react';
import './advanced-search.css';

export interface AdvancedSearchParams {
  lot_no?: string;
  production_date_from?: string;
  production_date_to?: string;
  machine_no?: string;
  mold_no?: string;
  product_name?: string;
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
  const [productName, setProductName] = useState('');
  const [dataType, setDataType] = useState('');

  // 驗證至少填寫一個條件
  const validateSearchParams = (): boolean => {
    return !!(
      lotNo.trim() ||
      dateFromYear || dateFromMonth || dateFromDay ||
      dateToYear || dateToMonth || dateToDay ||
      machineNo.trim() ||
      moldNo.trim() ||
      productName.trim() ||
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
    
    if (lotNo.trim()) params.lot_no = lotNo.trim();
    
    const dateFrom = buildDateString(dateFromYear, dateFromMonth, dateFromDay);
    if (dateFrom) params.production_date_from = dateFrom;
    
    const dateTo = buildDateString(dateToYear, dateToMonth, dateToDay);
    if (dateTo) params.production_date_to = dateTo;
    
    if (machineNo.trim()) params.machine_no = machineNo.trim();
    if (moldNo.trim()) params.mold_no = moldNo.trim();
    if (productName.trim()) params.product_name = productName.trim();
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
    setProductName('');
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
        高級搜尋
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
              />
            </div>

            {/* 模具編號 */}
            <div className="search-field">
              <label htmlFor="adv-mold-no">模具編號</label>
              <input
                id="adv-mold-no"
                type="text"
                value={moldNo}
                onChange={(e) => setMoldNo(e.target.value)}
                placeholder="輸入模具編號 (模糊搜尋)"
              />
            </div>

            {/* 產品名稱 */}
            <div className="search-field">
              <label htmlFor="adv-product-name">產品名稱</label>
              <input
                id="adv-product-name"
                type="text"
                value={productName}
                onChange={(e) => setProductName(e.target.value)}
                placeholder="輸入產品名稱 (模糊搜尋)"
              />
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
