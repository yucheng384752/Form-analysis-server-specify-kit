import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { useToast } from './common/ToastContext';
import './advanced-search.css';

export interface AdvancedSearchParams {
  lot_no?: string;
  production_date_from?: string;
  production_date_to?: string;
  machine_no?: string[];
  mold_no?: string[];
  product_id?: string;
  specification?: string[];  // 統一規格搜尋 (P1/P2/P3)
  material?: string[];       // 材料代號 (P1/P2)
  // 厚度篩選（整數輸入，單位 0.01mm；例如 30 表示 0.30mm）
  thickness_min?: string;
  thickness_max?: string;
  winder_number?: string;  // Winder Number
  data_type?: string;
}

interface AdvancedSearchProps {
  onSearch: (params: AdvancedSearchParams) => void;
  onReset: () => void;
  isExpanded: boolean;
  tenantId?: string;
}

export const AdvancedSearch: React.FC<AdvancedSearchProps> = ({
  onSearch,
  onReset,
  isExpanded,
  tenantId,
}) => {
  const { t } = useTranslation();
  const { showToast } = useToast();
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
  const [machineNos, setMachineNos] = useState<string[]>([]);
  const [moldNos, setMoldNos] = useState<string[]>([]);
  const [productId, setProductId] = useState('');
  const [specifications, setSpecifications] = useState<string[]>([]);  // 統一規格
  const [materials, setMaterials] = useState<string[]>([]);            // 材料代號
  const [thicknessMin, setThicknessMin] = useState('');
  const [thicknessMax, setThicknessMax] = useState('');
  const [winderNumber, setWinderNumber] = useState('');   // Winder Number
  const [dataType, setDataType] = useState('');

  // 選項狀態
  const [machineOptions, setMachineOptions] = useState<string[]>([]);
  const [moldOptions, setMoldOptions] = useState<string[]>([]);
  const [specOptions, setSpecOptions] = useState<string[]>([]);
  const [materialOptions, setMaterialOptions] = useState<string[]>([]);

  // 載入選項
  useEffect(() => {
    if (isExpanded) {
      const fetchOptions = async () => {
        try {
          const headers: HeadersInit = tenantId ? { 'X-Tenant-Id': tenantId } : {};
          // 平行請求所有選項
          const [machineRes, moldRes, specRes, materialRes] = await Promise.all([
            fetch('/api/v2/query/options/machine_no', { headers }),
            fetch('/api/v2/query/options/mold_no', { headers }),
            fetch('/api/v2/query/options/specification', { headers }),
            fetch('/api/v2/query/options/material', { headers })
          ]);

          if (machineRes.ok) setMachineOptions(await machineRes.json());
          if (moldRes.ok) setMoldOptions(await moldRes.json());
          if (specRes.ok) setSpecOptions(await specRes.json());
          if (materialRes.ok) setMaterialOptions(await materialRes.json());
        } catch (error) {
          console.error('Failed to fetch search options:', error);
        }
      };

      fetchOptions();
    }
  }, [isExpanded, tenantId]);

  // 驗證至少填寫一個條件
  const validateSearchParams = (): boolean => {
    return !!(
      lotNo.trim() ||
      dateFromYear || dateFromMonth || dateFromDay ||
      dateToYear || dateToMonth || dateToDay ||
      machineNos.length > 0 ||
      moldNos.length > 0 ||
      productId.trim() ||
      specifications.length > 0 ||
      materials.length > 0 ||
      thicknessMin.trim() ||
      thicknessMax.trim() ||
      winderNumber.trim() ||
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
      showToast('error', t('query.advanced.validationAtLeastOne'));
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
    
    // 日期邏輯優化：若只填寫一個日期，另一個自動使用同一天
    const dateFrom = buildDateString(dateFromYear, dateFromMonth, dateFromDay);
    const dateTo = buildDateString(dateToYear, dateToMonth, dateToDay);
    
    if (dateFrom && !dateTo) {
      // 只填寫起始日期，結束日期使用同一天
      params.production_date_from = dateFrom;
      params.production_date_to = dateFrom;
    } else if (!dateFrom && dateTo) {
      // 只填寫結束日期，起始日期使用同一天
      params.production_date_from = dateTo;
      params.production_date_to = dateTo;
    } else if (dateFrom && dateTo) {
      // 兩個都填寫
      params.production_date_from = dateFrom;
      params.production_date_to = dateTo;
    }
    
    // 其他欄位僅去除前後空白，後端已支援不分大小寫搜尋 (ilike)
    if (machineNos.length) params.machine_no = machineNos;
    if (moldNos.length) params.mold_no = moldNos;
    if (productId.trim()) params.product_id = productId.trim();
    if (specifications.length) params.specification = specifications;
    if (materials.length) params.material = materials;
    if (thicknessMin.trim()) params.thickness_min = thicknessMin.trim();
    if (thicknessMax.trim()) params.thickness_max = thicknessMax.trim();
    if (winderNumber.trim()) params.winder_number = winderNumber.trim();
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
    setMachineNos([]);
    setMoldNos([]);
    setProductId('');
    setSpecifications([]);
    setMaterials([]);
    setThicknessMin('');
    setThicknessMax('');
    setWinderNumber('');
    setDataType('');
    onReset();
  };

  return (
    <div className="advanced-search">
      <div
        id="advanced-search-panel"
        className="advanced-search-panel"
        data-expanded={isExpanded ? 'true' : 'false'}
        aria-hidden={!isExpanded}
      >
        <div className="advanced-search-panel-inner">
          <fieldset className="advanced-search-fieldset" disabled={!isExpanded}>
            <div className="search-grid">
            {/* 批號 */}
            <div className="search-field">
              <label htmlFor="adv-lot-no">{t('query.advanced.lotNo')}</label>
              <input
                id="adv-lot-no"
                type="text"
                value={lotNo}
                onChange={(e) => setLotNo(e.target.value)}
                placeholder={t('query.advanced.lotNoPlaceholder')}
              />
            </div>

            {/* 生產日期起始 */}
            <div className="search-field date-field">
              <label>{t('query.advanced.productionDateFrom')}</label>
              <div className="date-inputs">
                <input
                  type="number"
                  value={dateFromYear}
                  onChange={(e) => setDateFromYear(e.target.value)}
                  placeholder={t('query.advanced.year')}
                  min="1900"
                  max="2100"
                  className="date-year"
                />
                <span className="date-separator">/</span>
                <input
                  type="number"
                  value={dateFromMonth}
                  onChange={(e) => setDateFromMonth(e.target.value)}
                  placeholder={t('query.advanced.month')}
                  min="1"
                  max="12"
                  className="date-month"
                />
                <span className="date-separator">/</span>
                <input
                  type="number"
                  value={dateFromDay}
                  onChange={(e) => setDateFromDay(e.target.value)}
                  placeholder={t('query.advanced.day')}
                  min="1"
                  max="31"
                  className="date-day"
                />
              </div>
            </div>

            {/* 生產日期結束 */}
            <div className="search-field date-field">
              <label>{t('query.advanced.productionDateTo')}</label>
              <div className="date-inputs">
                <input
                  type="number"
                  value={dateToYear}
                  onChange={(e) => setDateToYear(e.target.value)}
                  placeholder={t('query.advanced.year')}
                  min="1900"
                  max="2100"
                  className="date-year"
                />
                <span className="date-separator">/</span>
                <input
                  type="number"
                  value={dateToMonth}
                  onChange={(e) => setDateToMonth(e.target.value)}
                  placeholder={t('query.advanced.month')}
                  min="1"
                  max="12"
                  className="date-month"
                />
                <span className="date-separator">/</span>
                <input
                  type="number"
                  value={dateToDay}
                  onChange={(e) => setDateToDay(e.target.value)}
                  placeholder={t('query.advanced.day')}
                  min="1"
                  max="31"
                  className="date-day"
                />
              </div>
            </div>

            {/* 機台號碼 */}
            <div className="search-field">
              <label htmlFor="adv-machine-no">{t('query.advanced.machineNo')}</label>
              <select
                id="adv-machine-no"
                multiple
                value={machineNos}
                onChange={(e) => setMachineNos(Array.from(e.target.selectedOptions, (o) => o.value))}
              >
                {machineOptions.map((opt, idx) => (
                  <option key={idx} value={opt}>{opt}</option>
                ))}
              </select>
            </div>

            {/* 下膠編號 (Bottom Tape) */}
            <div className="search-field">
              <label htmlFor="adv-mold-no">{t('query.advanced.moldNo')}</label>
              <select
                id="adv-mold-no"
                multiple
                value={moldNos}
                onChange={(e) => setMoldNos(Array.from(e.target.selectedOptions, (o) => o.value))}
              >
                {moldOptions.map((opt, idx) => (
                  <option key={idx} value={opt}>{opt}</option>
                ))}
              </select>
            </div>

            {/* 產品編號 */}
            <div className="search-field">
              <label htmlFor="adv-product-id">{t('query.advanced.productId')}</label>
              <input
                id="adv-product-id"
                type="text"
                value={productId}
                onChange={(e) => setProductId(e.target.value)}
                placeholder={t('query.advanced.productIdPlaceholder')}
              />
            </div>

            {/* 統一規格 (P1/P2/P3) */}
            <div className="search-field">
              <label htmlFor="adv-specification">{t('query.advanced.specification')}</label>
              <select
                id="adv-specification"
                multiple
                value={specifications}
                onChange={(e) => setSpecifications(Array.from(e.target.selectedOptions, (o) => o.value))}
              >
                {specOptions.map((opt, idx) => (
                  <option key={idx} value={opt}>{opt}</option>
                ))}
              </select>
            </div>

            {/* 材料代號 (P1/P2) */}
            <div className="search-field">
              <label htmlFor="adv-material">{t('query.advanced.material')}</label>
              <select
                id="adv-material"
                multiple
                value={materials}
                onChange={(e) => setMaterials(Array.from(e.target.selectedOptions, (o) => o.value))}
              >
                {materialOptions.map((opt, idx) => (
                  <option key={idx} value={opt}>{opt}</option>
                ))}
              </select>
            </div>

            {/* 厚度篩選（整數輸入，單位 0.01mm） */}
            <div className="search-field">
              <label htmlFor="adv-thickness-min">{t('query.advanced.thicknessMin')}</label>
              <input
                id="adv-thickness-min"
                type="number"
                value={thicknessMin}
                onChange={(e) => setThicknessMin(e.target.value)}
                placeholder={t('query.advanced.thicknessMinPlaceholder')}
                min="0"
              />
            </div>

            <div className="search-field">
              <label htmlFor="adv-thickness-max">{t('query.advanced.thicknessMax')}</label>
              <input
                id="adv-thickness-max"
                type="number"
                value={thicknessMax}
                onChange={(e) => setThicknessMax(e.target.value)}
                placeholder={t('query.advanced.thicknessMaxPlaceholder')}
                min="0"
              />
            </div>

            {/* Winder Number（下拉 1~20） */}
            <div className="search-field">
              <label htmlFor="adv-winder-number">{t('query.advanced.winderNumber')}</label>
              <select
                id="adv-winder-number"
                value={winderNumber}
                onChange={(e) => setWinderNumber(e.target.value)}
              >
                <option value="">{t('query.advanced.winderAll')}</option>
                {Array.from({ length: 20 }, (_, i) => String(i + 1)).map((opt) => (
                  <option key={opt} value={opt}>{opt}</option>
                ))}
              </select>
            </div>

            {/* 資料類型 */}
            <div className="search-field">
              <label htmlFor="adv-data-type">{t('query.advanced.dataType')}</label>
              <select
                id="adv-data-type"
                value={dataType}
                onChange={(e) => setDataType(e.target.value)}
              >
                <option value="">{t('query.advanced.dataTypeAll')}</option>
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
                {t('query.advanced.reset')}
              </button>
              <button
                className="btn-search"
                onClick={handleSearch}
                type="button"
              >
                {t('query.advanced.search')}
              </button>
            </div>
          </fieldset>
        </div>
      </div>
    </div>
  );
};
