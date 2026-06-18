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

  const toggleMultiValue = (
    value: string,
    setter: React.Dispatch<React.SetStateAction<string[]>>
  ) => {
    setter((prev) => {
      if (prev.includes(value)) {
        return prev.filter((v) => v !== value);
      }
      return [...prev, value];
    });
  };

  // 組合起始日期（月/日未填時補最小值 01）
  const buildDateFrom = (year: string, month: string, day: string): string | undefined => {
    if (!year) return undefined;
    const m = month ? month.padStart(2, '0') : '01';
    const d = day ? day.padStart(2, '0') : '01';
    return `${year}-${m}-${d}`;
  };

  // 組合結束日期（月未填時補 12，日未填時補 31）
  // 31 作為月末上限對字串比較永遠安全：不存在的日期（如 02-31）在資料中不會出現，
  // 且 between 只要求 <= 上限，實際最後一筆記錄日期必然 <= 當月真正最後一天 <= "31"
  const buildDateTo = (year: string, month: string, day: string): string | undefined => {
    if (!year) return undefined;
    const m = month ? month.padStart(2, '0') : '12';
    const d = day ? day.padStart(2, '0') : '31';
    return `${year}-${m}-${d}`;
  };

  // 處理搜尋
  const handleSearch = () => {
    if (!validateSearchParams()) {
      showToast('error', t('query.advanced.validationAtLeastOne'));
      return;
    }

    // 年份必填驗證：有月或日但沒有年時報錯
    if (!dateFromYear && (dateFromMonth || dateFromDay)) {
      showToast('error', t('query.advanced.dateYearRequired', '日期篩選：請輸入起始年份'));
      return;
    }
    if (!dateToYear && (dateToMonth || dateToDay)) {
      showToast('error', t('query.advanced.dateYearRequired', '日期篩選：請輸入結束年份'));
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

    const dateFrom = buildDateFrom(dateFromYear, dateFromMonth, dateFromDay);
    // 結束側用上限預設（無月→12，無日→31），確保「只填年份」時涵蓋整年
    const dateTo = buildDateTo(dateToYear, dateToMonth, dateToDay);

    // 起始日期不可大於結束日期（比較的是 from 的最小值 vs to 的最大值）
    if (dateFrom && dateTo && dateFrom > dateTo) {
      showToast('error', t('query.advanced.dateRangeInvalid', '起始日期不可大於結束日期'));
      return;
    }

    if (dateFrom && !dateTo) {
      // 只填起始日期：to 取同一個週期的上限
      params.production_date_from = dateFrom;
      params.production_date_to = buildDateTo(dateFromYear, dateFromMonth, dateFromDay)!;
    } else if (!dateFrom && dateTo) {
      // 只填結束日期：from 取同一個週期的下限
      params.production_date_from = buildDateFrom(dateToYear, dateToMonth, dateToDay)!;
      params.production_date_to = dateTo;
    } else if (dateFrom && dateTo) {
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
              <label>{t('query.advanced.machineNo')}</label>
              <div className="multi-checkbox-list" role="group" aria-label={t('query.advanced.machineNo')}>
                {machineOptions.map((opt) => (
                  <label key={opt} className="multi-checkbox-item">
                    <input
                      type="checkbox"
                      checked={machineNos.includes(opt)}
                      onChange={() => toggleMultiValue(opt, setMachineNos)}
                    />
                    <span>{opt}</span>
                  </label>
                ))}
              </div>
            </div>

            {/* 下膠編號 (Bottom Tape) */}
            <div className="search-field">
              <label>{t('query.advanced.moldNo')}</label>
              <div className="multi-checkbox-list" role="group" aria-label={t('query.advanced.moldNo')}>
                {moldOptions.map((opt) => (
                  <label key={opt} className="multi-checkbox-item">
                    <input
                      type="checkbox"
                      checked={moldNos.includes(opt)}
                      onChange={() => toggleMultiValue(opt, setMoldNos)}
                    />
                    <span>{opt}</span>
                  </label>
                ))}
              </div>
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
              <label>{t('query.advanced.specification')}</label>
              <div className="multi-checkbox-list" role="group" aria-label={t('query.advanced.specification')}>
                {specOptions.map((opt) => (
                  <label key={opt} className="multi-checkbox-item">
                    <input
                      type="checkbox"
                      checked={specifications.includes(opt)}
                      onChange={() => toggleMultiValue(opt, setSpecifications)}
                    />
                    <span>{opt}</span>
                  </label>
                ))}
              </div>
            </div>

            {/* 材料代號 (P1/P2) */}
            <div className="search-field">
              <label>{t('query.advanced.material')}</label>
              <div className="multi-checkbox-list" role="group" aria-label={t('query.advanced.material')}>
                {materialOptions.map((opt) => (
                  <label key={opt} className="multi-checkbox-item">
                    <input
                      type="checkbox"
                      checked={materials.includes(opt)}
                      onChange={() => toggleMultiValue(opt, setMaterials)}
                    />
                    <span>{opt}</span>
                  </label>
                ))}
              </div>
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
