// src/pages/QueryPage.tsx
import React, { useState, useRef } from "react";
import { useTranslation } from "react-i18next";
import { useToast } from "../components/common/ToastContext";
import { Modal } from "../components/common/Modal";
import { AdvancedSearch, AdvancedSearchParams } from "../components/AdvancedSearch";
import { EditRecordModal } from "../components/EditRecordModal";
import "../styles/query-page.css";
import type { DataType } from "../types/common";
import { TENANT_STORAGE_KEY, type QueryRecord, type QueryResponse } from "./query/types";
import {
  mergeP2RecordsForLotNo,
  isLikelyProductId,
  normalizeTraceRecord,
  formatFieldValue,
  getP2SlittingTimeForSummary,
} from "./query/utils";
import { RecordExpandedContent } from "./query/RecordExpandedContent";
import { RecordDetailContent } from "./query/RecordDetailContent";

export function QueryPage() {
  const { t } = useTranslation();
  const { showToast } = useToast();
  // 搜尋相關狀態
  const [searchKeyword, setSearchKeyword] = useState("");
  const [searchPerformed, setSearchPerformed] = useState(false);
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [suggestionLoading, setSuggestionLoading] = useState(false);

  // 進階搜尋相關狀態
  const [advancedSearchExpanded, setAdvancedSearchExpanded] = useState(false);
  const [advancedSearchParams, setAdvancedSearchParams] = useState<AdvancedSearchParams | null>(null);

  // 記錄列表相關狀態
  const [records, setRecords] = useState<QueryRecord[]>([]);
  const [expandedRecordId, setExpandedRecordId] = useState<string | null>(null);
  const [collapsedSections, setCollapsedSections] = useState<{ [key: string]: boolean }>({});
  const [detailRecord, setDetailRecord] = useState<QueryRecord | null>(null);
  const [editRecord, setEditRecord] = useState<QueryRecord | null>(null);
  const [tenantId, setTenantId] = useState<string>("");

  const effectiveTenantId = tenantId || window.localStorage.getItem(TENANT_STORAGE_KEY) || ''

  // 表格排序狀態
  const [tableSortState, setTableSortState] = useState<{ [key: string]: { column: string; direction: 'asc' | 'desc' } }>({});

  React.useEffect(() => {
    const storedTenantId = window.localStorage.getItem(TENANT_STORAGE_KEY);
    if (storedTenantId) {
      setTenantId(storedTenantId);
    }
  }, []);

  const mergeTenantHeaders = (headers?: HeadersInit): HeadersInit => {
    const tenantHeaders: Record<string, string> = effectiveTenantId ? { 'X-Tenant-Id': effectiveTenantId } : {};

    if (!headers) return tenantHeaders;
    if (headers instanceof Headers) {
      const merged = new Headers(headers);
      for (const [k, v] of Object.entries(tenantHeaders)) merged.set(k, v);
      return merged;
    }
    if (Array.isArray(headers)) {
      const mergedObj: Record<string, string> = { ...tenantHeaders };
      for (const [k, v] of headers) mergedObj[String(k)] = String(v);
      return mergedObj;
    }
    return { ...tenantHeaders, ...(headers as Record<string, string>) };
  };

  const fetchWithTenant = (input: RequestInfo | URL, init?: RequestInit) => {
    return fetch(input, {
      ...init,
      headers: mergeTenantHeaders(init?.headers),
    });
  };
  const [loading, setLoading] = useState(false);
  const [totalCount, setTotalCount] = useState(0);
  const [currentPage, setCurrentPage] = useState(1);
  const [traceabilityData, setTraceabilityData] = useState<any>(null);
  const [traceActiveTab, setTraceActiveTab] = useState<DataType>('P3');

  const inputRef = useRef<HTMLInputElement>(null);
  const suggestionsRef = useRef<HTMLDivElement>(null);
  const traceSectionRef = useRef<HTMLDivElement>(null);
  const pageSize = 50;

  const scrollToTrace = () => {
    setTimeout(() => {
      traceSectionRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, 50);
  };

  // 搜尋記錄 (支援基本搜尋和進階搜尋)
  const searchRecords = async (search: string, page: number = 1, advancedParams?: AdvancedSearchParams) => {
    setLoading(true);
    setExpandedRecordId(null);
    setCollapsedSections({});
    try {
      let apiUrl = '/api/v2/query/records';

      const isLikelyExactLotNo = (value: string): boolean => {
        return /^\d{6,8}_\d{2}$/.test(value.trim());
      };

      const lotNoForMerge = (advancedParams?.lot_no || search || '').trim();
      const canMergeP2LotNo =
        isLikelyExactLotNo(lotNoForMerge) &&
        (!advancedParams || !advancedParams.winder_number) &&
        (!advancedParams?.data_type || advancedParams.data_type === 'P2');

      const effectivePage = canMergeP2LotNo ? 1 : page;
      const effectivePageSize = canMergeP2LotNo ? (advancedParams ? 200 : 100) : pageSize;

      const params = new URLSearchParams({
        page: effectivePage.toString(),
        page_size: effectivePageSize.toString()
      });

      if (advancedParams) {
        apiUrl = '/api/v2/query/records/dynamic';

        type DynamicFilter = { field: string; op: string; value: any };

        const filters: DynamicFilter[] = [];
        if (advancedParams.lot_no) {
          filters.push({ field: 'lot_no', op: 'contains', value: advancedParams.lot_no });
        }

        const dateFrom = (advancedParams.production_date_from || '').trim();
        const dateTo = (advancedParams.production_date_to || '').trim();
        if (dateFrom && dateTo) {
          if (dateFrom === dateTo) {
            filters.push({ field: 'production_date', op: 'eq', value: dateFrom });
          } else {
            filters.push({ field: 'production_date', op: 'between', value: [dateFrom, dateTo] });
          }
        }

        if (advancedParams.machine_no && advancedParams.machine_no.length) {
          filters.push({ field: 'machine_no', op: 'all_of', value: advancedParams.machine_no });
        }
        if (advancedParams.mold_no && advancedParams.mold_no.length) {
          filters.push({ field: 'mold_no', op: 'all_of', value: advancedParams.mold_no });
        }
        if (advancedParams.product_id) {
          filters.push({ field: 'product_id', op: 'contains', value: advancedParams.product_id });
        }
        if (advancedParams.specification && advancedParams.specification.length) {
          filters.push({ field: 'specification', op: 'all_of', value: advancedParams.specification });
        }
        if (advancedParams.material && advancedParams.material.length) {
          filters.push({ field: 'material', op: 'all_of', value: advancedParams.material });
        }
        if (advancedParams.winder_number) {
          filters.push({ field: 'winder_number', op: 'eq', value: advancedParams.winder_number });
        }
        if (advancedParams.thickness_min || advancedParams.thickness_max) {
          const a = advancedParams.thickness_min ? Number(advancedParams.thickness_min) : null;
          const b = advancedParams.thickness_max ? Number(advancedParams.thickness_max) : null;
          if (Number.isFinite(a) && Number.isFinite(b)) {
            filters.push({ field: 'thickness', op: 'between', value: [a, b] });
          } else if (Number.isFinite(a)) {
            filters.push({ field: 'thickness', op: 'between', value: [a, a] });
          } else if (Number.isFinite(b)) {
            filters.push({ field: 'thickness', op: 'between', value: [b, b] });
          }
        }

        const dataTypeRaw = (advancedParams.data_type || '').trim().toUpperCase();
        const dataType = (dataTypeRaw === 'P1' || dataTypeRaw === 'P2' || dataTypeRaw === 'P3') ? dataTypeRaw : undefined;

        const response = await fetchWithTenant(apiUrl, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            data_type: dataType,
            filters,
            page: effectivePage,
            page_size: effectivePageSize,
          }),
        });

        if (response.ok) {
          const data: QueryResponse = await response.json();

          if (canMergeP2LotNo) {
            const merged = mergeP2RecordsForLotNo(data.records, lotNoForMerge);
            setRecords(merged);
            setTotalCount(merged.length);
            setCurrentPage(1);
          } else {
            setRecords(data.records);
            setTotalCount(data.total_count);
            setCurrentPage(data.page);
          }
          setSearchPerformed(true);
        } else {
          console.error('Error searching records:', response.status);
        }

        return;
      } else if (search) {
        params.append('lot_no', search);
      }

      const response = await fetchWithTenant(`${apiUrl}?${params}`);
      if (response.ok) {
        const data: QueryResponse = await response.json();

        if (canMergeP2LotNo) {
          const merged = mergeP2RecordsForLotNo(data.records, lotNoForMerge);
          setRecords(merged);
          setTotalCount(merged.length);
          setCurrentPage(1);
        } else {
          setRecords(data.records);
          setTotalCount(data.total_count);
          setCurrentPage(data.page);
        }
        setSearchPerformed(true);
      } else {
        console.error('Error searching records:', response.status);
      }
    } catch (error) {
      console.error('Error searching records:', error);
    } finally {
      setLoading(false);
    }
  };

  // 處理 P3 關聯查詢
  const handleP3LinkSearch = async (record: QueryRecord, row: any, rowProductId?: string) => {
    try {
      let baseLotNo = '';
      let sourceWinder: number | null = null;

      const p3No = row['P3_No.'] || row['P3 No.'] || row['p3_no'] || row['P3NO'];

      if (p3No) {
        const parts = p3No.toString().trim().split('_');
        if (parts.length >= 3) {
          const winderPart = parts[parts.length - 2];
          if (/^\d+$/.test(winderPart)) {
            sourceWinder = parseInt(winderPart, 10);
            baseLotNo = parts.slice(0, parts.length - 2).join('_');
            console.log('Parsed from P3_No:', { p3No, baseLotNo, sourceWinder });
          }
        }
      }

      if (!sourceWinder) {
        const lotNoVal = row['lot no'] || row['lot_no'] || row['Lot No'] || row['Lot No.'];
        if (lotNoVal) {
          const parts = lotNoVal.toString().trim().split('_');
          if (parts.length >= 3) {
            const lastPart = parts[parts.length - 1];
            if (/^\d+$/.test(lastPart)) {
              sourceWinder = parseInt(lastPart, 10);
              if (!baseLotNo) {
                baseLotNo = parts.slice(0, parts.length - 1).join('_');
              }
              console.log('Parsed from lot no field:', { lotNoVal, baseLotNo, sourceWinder });
            }
          }
        }
      }

      if (!baseLotNo || !sourceWinder) {
        baseLotNo = record.lot_no;

        const winderVal = row['Winder'] || row['winder'] || row['Winder No'] || row['source_winder'];
        if (winderVal && /^\d+$/.test(winderVal.toString())) {
          sourceWinder = parseInt(winderVal.toString(), 10);
        }
      }

      if (!baseLotNo) {
        showToast('error', t('query.errors.lotInfoMissing'));
        return;
      }

      if (!sourceWinder) {
        showToast('error', t('query.errors.winderMissing'));
        return;
      }

      console.log('P3 link search executing:', { baseLotNo, sourceWinder });

      setLoading(true);

      const traceResponse = await fetchWithTenant(
        `/api/traceability/winder/${encodeURIComponent(baseLotNo)}/${sourceWinder}`
      );

      if (!traceResponse.ok) {
        if (traceResponse.status === 404) {
          showToast('error', t('query.errors.p2NotFound', { lotNo: baseLotNo, winder: sourceWinder }));
          setLoading(false);
          return;
        }
        showToast(
          'error',
          t('query.errors.traceFailedWithStatus', {
            status: traceResponse.status,
            statusText: traceResponse.statusText || String(traceResponse.status)
          })
        );
        setLoading(false);
        return;
      }

      const traceData = await traceResponse.json();

      console.log('[Traceability Debug] Backend response traceData:', traceData);

      const p3Record = { ...record };

      if (rowProductId) {
        p3Record.product_id = rowProductId;
      }

      const lotVal = row['lot'] || row['Lot'] || row['production_lot'] || row['Production Lot'] || row['lot_no'] || row['Lot No'];
      if (lotVal) {
        p3Record.production_lot = lotVal;
      }

      const flowData = {
        product_id: rowProductId || record.product_id || `${baseLotNo}_${sourceWinder}`,
        p3: p3Record,
        p2: traceData.p2,
        p1: traceData.p1,
        trace_complete: !!(record && traceData.p2 && traceData.p1),
        missing_links: [] as string[]
      };

      if (!traceData.p2) flowData.missing_links.push('P2');
      if (!traceData.p1) flowData.missing_links.push('P1');

      setTraceabilityData(flowData);
      setTraceActiveTab('P3');
      scrollToTrace();

      setLoading(false);

      setTimeout(() => {
        const searchResultsElement = document.querySelector('.data-container');
        if (searchResultsElement) {
          searchResultsElement.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
      }, 500);

    } catch (error: any) {
      console.error('P3 link search failed:', error);
      showToast('error', t('query.errors.searchFailedWithDetail', { detail: String(error?.message || '') || t('query.errors.unknownError') }));
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
        term: query.trim(),
        limit: '10'
      });

      const response = await fetchWithTenant(`/api/v2/query/lots/suggestions?${params}`);
      if (response.ok) {
        const data: string[] = await response.json();
        setSuggestions(data);
        setShowSuggestions(data.length > 0);
      } else {
        console.error('Error fetching suggestions:', response.status);
        setSuggestions([]);
        setShowSuggestions(false);
      }
    } catch (error) {
      console.error('Error fetching suggestions:', error);
      setSuggestions([]);
      setShowSuggestions(false);
    } finally {
      setSuggestionLoading(false);
    }
  };

  // 處理基本搜尋
  const handleSearch = async () => {
    if (!effectiveTenantId) {
      showToast('error', t('query.noTenantWarning'));
      return;
    }

    const keyword = searchKeyword.trim();
    if (!keyword) return;

    setShowSuggestions(false);

    if (isLikelyProductId(keyword)) {
      try {
        setLoading(true);
        setAdvancedSearchParams(null);
        setRecords([]);
        setTotalCount(0);
        setSearchPerformed(false);

        const res = await fetchWithTenant(`/api/traceability/product/${encodeURIComponent(keyword)}`);
        if (!res.ok) {
          if (res.status === 404) {
            showToast('error', t('query.errors.productNotFound'));
            return;
          }
          const text = await res.text().catch(() => '');
          throw new Error(text || res.statusText);
        }
        const data = await res.json();
        setTraceabilityData(data);
        setTraceActiveTab('P3');
        scrollToTrace();
      } catch (e: any) {
        console.error('Product ID traceability failed:', e);
        showToast('error', t('query.errors.searchFailedWithDetail', { detail: String(e?.message || '') || t('query.errors.unknownError') }));
      } finally {
        setLoading(false);
      }
      return;
    }

    setTraceabilityData(null);
    setTraceActiveTab('P3');
    setAdvancedSearchParams(null);
    await searchRecords(keyword);
  };

  // 處理進階搜尋
  const handleAdvancedSearch = async (params: AdvancedSearchParams) => {
    if (!effectiveTenantId) {
      showToast('error', t('query.noTenantWarning'));
      return;
    }

    setAdvancedSearchParams(params);
    setSearchKeyword('');
    await searchRecords('', 1, params);
  };

  // 重置進階搜尋
  const handleAdvancedReset = () => {
    setAdvancedSearchParams(null);
    setRecords([]);
    setSearchPerformed(false);
    setTotalCount(0);
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    setSearchKeyword(value);
    if (tenantId) fetchSuggestions(value);
  };

  const handleSuggestionClick = (suggestion: string) => {
    setSearchKeyword(suggestion);
    setShowSuggestions(false);
    if (!effectiveTenantId) {
      showToast('error', t('query.noTenantWarning'));
      return;
    }
    searchRecords(suggestion);
  };

  const handleInputFocus = () => {
    if (searchKeyword.trim().length >= 1) {
      if (tenantId) fetchSuggestions(searchKeyword);
    }
  };

  const handleInputBlur = () => {
    setTimeout(() => setShowSuggestions(false), 200);
  };

  const toggleExpand = (recordId: string) => {
    setExpandedRecordId(prev => prev === recordId ? null : recordId);
    if (expandedRecordId !== recordId) {
      setCollapsedSections({});
    }
  };

  const toggleSection = (recordId: string, sectionKey: string) => {
    const key = `${recordId}-${sectionKey}`;
    setCollapsedSections(prev => ({
      ...prev,
      [key]: !prev[key]
    }));
  };

  const handleTableSort = (recordId: string, tableType: 'p2' | 'p3', column: string) => {
    const key = `${recordId}-${tableType}`;
    const currentSort = tableSortState[key];

    let newDirection: 'asc' | 'desc' = 'asc';
    if (currentSort && currentSort.column === column) {
      newDirection = currentSort.direction === 'asc' ? 'desc' : 'asc';
    }

    setTableSortState({
      ...tableSortState,
      [key]: { column, direction: newDirection }
    });
  };

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
    setTraceabilityData(null);
    setTraceActiveTab('P3');
  };

  return (
    <div className="query-page">
      {/* 搜尋區域 */}
      <section className="query-search-section">
        <label className="query-search-label">
          {t('query.title')}

          <div className="query-description">
            <p><strong>{t('query.descLotTitle')}</strong>{t('query.descLot')}</p>
            <p><strong>{t('query.descProductTitle')}</strong>{t('query.descProduct')}</p>
            <p><strong>{t('query.descAdvancedTitle')}</strong>{t('query.descAdvanced')}</p>
          </div>

          <div className="query-search-input-wrapper autocomplete-wrapper">
            {!effectiveTenantId && (
              <div
                style={{
                  marginBottom: '10px',
                  padding: '10px 12px',
                  borderRadius: '8px',
                  background: '#fff3cd',
                  border: '1px solid #ffeeba',
                  color: '#856404',
                  fontSize: '14px',
                }}
              >
                {t('query.noTenantWarning')}
              </div>
            )}
            <input
              ref={inputRef}
              type="text"
              className="query-search-input"
              placeholder={t('query.searchPlaceholder')}
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
                  <div className="suggestion-item loading">{t('query.suggestionLoading')}</div>
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
                  <div className="suggestion-item no-results">{t('query.suggestionNoResults')}</div>
                )}
              </div>
            )}

            <button
              className="btn-primary"
              onClick={handleSearch}
              disabled={loading || !tenantId}
            >
              {loading ? t('query.searching') : t('query.search')}
            </button>

            {searchKeyword && (
              <button
                className="btn-secondary"
                onClick={handleClear}
              >
                {t('common.clear')}
              </button>
            )}

            <button
              className={`btn-secondary advanced-search-toggle ${advancedSearchExpanded ? 'expanded' : ''}`}
              onClick={() => setAdvancedSearchExpanded(!advancedSearchExpanded)}
              type="button"
              title={t('query.advancedSearch')}
              aria-expanded={advancedSearchExpanded}
              aria-controls="advanced-search-panel"
            >
              <span className={`toggle-icon ${advancedSearchExpanded ? 'expanded' : ''}`}>▶</span>
              {t('query.advancedSearch')}
            </button>
          </div>

          <AdvancedSearch
            onSearch={handleAdvancedSearch}
            onReset={handleAdvancedReset}
            isExpanded={advancedSearchExpanded}
            tenantId={tenantId}
          />
        </label>
      </section>

      {/* 追溯結果（同頁三站 Tabs，預設站3） */}
      {traceabilityData && (
        <section className="query-result-section" ref={traceSectionRef}>
          <div className="records-container">
            <div className="records-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <h3>{traceabilityData.product_id ? `${t('query.traceResult')} - ${traceabilityData.product_id}` : t('query.traceResult')}</h3>
              <button className="btn-secondary" onClick={() => setTraceabilityData(null)}>
                {t('query.clearTraceResult')}
              </button>
            </div>

            <div style={{ display: 'flex', gap: '8px', marginBottom: '12px' }}>
              <button
                className={traceActiveTab === 'P3' ? 'btn-primary' : 'btn-secondary'}
                onClick={() => setTraceActiveTab('P3')}
              >
                P3
              </button>
              <button
                className={traceActiveTab === 'P2' ? 'btn-primary' : 'btn-secondary'}
                onClick={() => setTraceActiveTab('P2')}
              >
                P2
              </button>
              <button
                className={traceActiveTab === 'P1' ? 'btn-primary' : 'btn-secondary'}
                onClick={() => setTraceActiveTab('P1')}
              >
                P1
              </button>
            </div>

            <div className="record-detail">
              {traceActiveTab === 'P3' && (
                (() => {
                  const rec = normalizeTraceRecord('P3', traceabilityData.p3);
                  return rec ? <RecordDetailContent record={rec} collapsedSections={collapsedSections} onToggleSection={toggleSection} /> : <p className="section-empty">{t('common.noData')}</p>;
                })()
              )}
              {traceActiveTab === 'P2' && (
                (() => {
                  const rec = normalizeTraceRecord('P2', traceabilityData.p2);
                  return rec ? <RecordDetailContent record={rec} collapsedSections={collapsedSections} onToggleSection={toggleSection} /> : <p className="section-empty">{t('common.noData')}</p>;
                })()
              )}
              {traceActiveTab === 'P1' && (
                (() => {
                  const rec = normalizeTraceRecord('P1', traceabilityData.p1);
                  return rec ? <RecordDetailContent record={rec} collapsedSections={collapsedSections} onToggleSection={toggleSection} /> : <p className="section-empty">{t('common.noData')}</p>;
                })()
              )}
            </div>
          </div>
        </section>
      )}

      {/* 結果區域 */}
      {searchPerformed && (
        <section className="query-result-section">
          {loading ? (
            <p className="section-empty">{t('common.loading')}</p>
          ) : records.length === 0 ? (
            <p className="section-empty">{t('query.results.noResults')}</p>
          ) : (
            <div className="records-container">
              <div className="records-header">
                <h3>
                  {searchKeyword
                    ? t('query.results.foundCountWithKeyword', { keyword: searchKeyword, count: totalCount })
                    : t('query.results.foundCount', { count: totalCount })}
                </h3>
              </div>

              {(() => {
                const lotNoForDisplay = (advancedSearchParams?.lot_no || searchKeyword || '').trim();
                const isSingleP2LotCard =
                  !!lotNoForDisplay &&
                  !advancedSearchParams?.winder_number &&
                  records.length === 1 &&
                  records[0]?.data_type === 'P2';

                if (isSingleP2LotCard) {
                  const record = records[0];
                  return (
                    <div className="single-record-card">
                      <div className="single-record-card-header">
                        <div className="single-record-card-title">
                          <span className="single-record-lot">{record.lot_no}</span>
                          <span className={`data-type-label ${record.data_type.toLowerCase()}`}>{record.data_type}</span>
                        </div>
                        <div className="single-record-card-meta">
                          <div>{t('query.fields.slittingTime')}: {getP2SlittingTimeForSummary(record) ?? '-'}</div>
                          <div>{t('query.fields.createdAt')}: {new Date(record.created_at).toLocaleString('zh-TW', {
                            year: 'numeric',
                            month: '2-digit',
                            day: '2-digit',
                            hour: '2-digit',
                            minute: '2-digit',
                            hour12: false
                          })}</div>
                        </div>
                        <div className="single-record-card-actions">
                          <button
                            className="btn-expand"
                            title={t('query.actions.expandDetails')}
                            onClick={() => toggleExpand(record.id)}
                          >
                            {expandedRecordId === record.id ? t('common.collapse') : t('common.expand')}
                          </button>
                        </div>
                      </div>

                      {expandedRecordId === record.id && (
                        <div className="single-record-card-body">
                          <RecordDetailContent record={record} collapsedSections={collapsedSections} onToggleSection={toggleSection} />
                        </div>
                      )}
                    </div>
                  );
                }

                return (
                  <table className="records-table">
                    <thead>
                      <tr>
                        <th>{t('query.tableHeaders.lotNo')}</th>
                        <th>{t('query.tableHeaders.dataType')}</th>
                        <th>{t('query.tableHeaders.productionDate')}</th>
                        <th>{t('query.tableHeaders.createdAt')}</th>
                        <th>{t('query.tableHeaders.actions')}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {records.map((record) => (
                        <React.Fragment key={record.id}>
                          <tr>
                            <td>{record.lot_no}</td>
                            <td>
                              <span className={`data-type-label ${record.data_type.toLowerCase()}`}>
                                {record.data_type}
                              </span>
                            </td>
                            <td>
                              {record.data_type === 'P2'
                                ? (getP2SlittingTimeForSummary(record) ?? '-')
                                : formatFieldValue('production_date', record.production_date)}
                            </td>
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
                                title={t('query.actions.expandCsvData')}
                                onClick={() => toggleExpand(record.id)}
                              >
                                {expandedRecordId === record.id ? t('common.collapse') : t('common.expand')}
                              </button>
                            </td>
                          </tr>

                          {/* 展開行 - 顯示分組資料 */}
                          {expandedRecordId === record.id && (
                            <tr className="expanded-row">
                              <td colSpan={5}>
                                <div className="expanded-data-container">
                                  <RecordExpandedContent
                                    record={record}
                                    collapsedSections={collapsedSections}
                                    tableSortState={tableSortState}
                                    onToggleSection={toggleSection}
                                    onTableSort={handleTableSort}
                                    onP3LinkSearch={handleP3LinkSearch}
                                  />
                                </div>
                              </td>
                            </tr>
                          )}
                        </React.Fragment>
                      ))}
                    </tbody>
                  </table>
                );
              })()}

              {/* 分頁控制 */}
              {totalCount > pageSize && (
                <div className="pagination">
                  <button
                    onClick={() => searchRecords(searchKeyword, currentPage - 1, advancedSearchParams || undefined)}
                    disabled={currentPage <= 1}
                  >
                    {t('query.pagination.previous')}
                  </button>
                  <span>{t('query.pagination.page', { page: currentPage })}</span>
                  <button
                    onClick={() => searchRecords(searchKeyword, currentPage + 1, advancedSearchParams || undefined)}
                    disabled={currentPage * pageSize >= totalCount}
                  >
                    {t('query.pagination.next')}
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
        title={t('query.detailModalTitle', { type: String(detailRecord?.data_type || '') })}
        onClose={() => setDetailRecord(null)}
      >
        {detailRecord && (
          <div className="record-detail">
            <RecordDetailContent record={detailRecord} collapsedSections={collapsedSections} onToggleSection={toggleSection} />
          </div>
        )}
      </Modal>

      <EditRecordModal
        open={editRecord !== null}
        record={editRecord}
        type={editRecord?.data_type as any}
        tenantId={tenantId}
        onClose={() => setEditRecord(null)}
        onSave={(updated) => {
          console.log("Record updated:", updated);
        }}
      />
    </div>
  );
}
