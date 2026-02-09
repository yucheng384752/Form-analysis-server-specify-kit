import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  fetchArtifactDetailView,
  fetchArtifactList,
  fetchArtifactListView,
  type ArtifactKey,
  type ArtifactListItem,
} from '../../services/analyticsArtifacts'

type ViewKey = 'events' | 'aggregated' | 'rag' | 'llm' | 'weighted'

const VIEW_TO_ARTIFACT: Record<ViewKey, ArtifactKey> = {
  events: 'serialized_events',
  aggregated: 'aggregated_diagnostics',
  rag: 'rag_results',
  llm: 'llm_reports',
  weighted: 'weighted_contributions',
}

function isPlainObject(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value)
}

function toStr(value: unknown): string {
  if (value === null || value === undefined) return ''
  return String(value)
}

function safeNumber(value: unknown): number {
  const n = typeof value === 'number' ? value : Number(value)
  return Number.isFinite(n) ? n : 0
}

function tryParseIsoDate(value: unknown): Date | null {
  const s = String(value ?? '').trim()
  if (!s) return null
  const d = new Date(s)
  return Number.isFinite(d.getTime()) ? d : null
}

function formatIsoPreview(value: unknown): string {
  const d = tryParseIsoDate(value)
  if (!d) return ''
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  const hh = String(d.getHours()).padStart(2, '0')
  const mm = String(d.getMinutes()).padStart(2, '0')
  return `${y}-${m}-${day} ${hh}:${mm}`
}

function pickId(item: unknown): string {
  if (!isPlainObject(item)) return ''
  const candidates = ['event_id', 'summary_id', 'id', 'eventId', 'summaryId']
  for (const k of candidates) {
    const v = item[k]
    if (typeof v === 'string' && v.trim()) return v.trim()
  }
  return ''
}

export function ArtifactsView(props: { view: ViewKey; tenantHeaders?: Record<string, string>; productIds?: string[] }) {
  const artifactKey = VIEW_TO_ARTIFACT[props.view]

  const productIdFilters = useMemo(() => {
    const ids = (props.productIds ?? []).map((s) => s.trim()).filter(Boolean)
    const uniq: string[] = []
    const seen = new Set<string>()
    for (const x of ids) {
      const k = x.toLowerCase()
      if (seen.has(k)) continue
      seen.add(k)
      uniq.push(x)
      if (uniq.length >= 50) break
    }
    return uniq
  }, [props.productIds])

  const productIdNeedle = useMemo(() => productIdFilters.map((x) => x.toLowerCase()), [productIdFilters])

  const matchAnyProductId = useCallback(
    (...haystacks: Array<string | undefined | null>) => {
      if (productIdNeedle.length === 0) return true
      const combined = haystacks.filter(Boolean).join(' ').toLowerCase()
      return productIdNeedle.some((pid) => combined.includes(pid))
    },
    [productIdNeedle],
  )

  const requestOpts = useMemo(() => {
    return props.tenantHeaders ? { headers: props.tenantHeaders } : undefined
  }, [props.tenantHeaders])

  const [list, setList] = useState<ArtifactListItem[]>([])
  const [listError, setListError] = useState('')
  const [loadingList, setLoadingList] = useState(false)

  const [listData, setListData] = useState<unknown>(null)
  const [listDataError, setListDataError] = useState('')
  const [loadingListData, setLoadingListData] = useState(false)

  const [detailData, setDetailData] = useState<unknown>(null)
  const [detailError, setDetailError] = useState('')
  const [loadingDetail, setLoadingDetail] = useState(false)

  const [query, setQuery] = useState('')
  const [selectedId, setSelectedId] = useState<string>('')

  const [sortMode, setSortMode] = useState<'dateDesc' | 'anomaliesDesc' | 'sampleDesc' | 'alphaAsc'>('dateDesc')

  const selectedInfo = useMemo(() => list.find((x) => String(x.key) === artifactKey) ?? null, [artifactKey, list])

  const refreshList = useCallback(() => {
    void (async () => {
      try {
        setLoadingList(true)
        setListError('')
        const items = await fetchArtifactList(requestOpts)
        setList(items)
      } catch (e: any) {
        setList([])
        setListError(String(e?.message || e))
      } finally {
        setLoadingList(false)
      }
    })()
  }, [requestOpts])

  const refreshListData = useCallback(() => {
    void (async () => {
      try {
        setLoadingListData(true)
        setListDataError('')
        const json = await fetchArtifactListView(artifactKey, requestOpts, { productIds: productIdFilters })
        setListData(json)
      } catch (e: any) {
        setListData(null)
        setListDataError(String(e?.message || e))
      } finally {
        setLoadingListData(false)
      }
    })()
  }, [artifactKey, productIdFilters, requestOpts])

  const refreshDetailData = useCallback(
    (itemId: string) => {
      const id = String(itemId || '').trim()
      if (!id) {
        setDetailData(null)
        setDetailError('')
        setLoadingDetail(false)
        return
      }
      void (async () => {
        try {
          setLoadingDetail(true)
          setDetailError('')
          const json = await fetchArtifactDetailView(artifactKey, id, requestOpts)
          setDetailData(json)
        } catch (e: any) {
          setDetailData(null)
          setDetailError(String(e?.message || e))
        } finally {
          setLoadingDetail(false)
        }
      })()
    },
    [artifactKey, requestOpts],
  )

  useEffect(() => {
    refreshList()
  }, [refreshList])

  useEffect(() => {
    setSelectedId('')
    setQuery('')
    setDetailData(null)
    setDetailError('')
    refreshListData()
  }, [artifactKey, refreshListData])

  useEffect(() => {
    if (!selectedId) {
      setDetailData(null)
      setDetailError('')
      return
    }
    refreshDetailData(selectedId)
  }, [refreshDetailData, selectedId])

  // ===== Events (serialized_results) =====
  type EventRow = {
    event_id: string
    event_date_raw: unknown
    event_date: Date | null
    produce_no: string
    winder: string
    slitting: string
    iqr_count: number
    t2_count: number
    spe_count: number
  }

  const eventRows = useMemo(() => {
    if (props.view !== 'events') return [] as EventRow[]
    if (!Array.isArray(listData)) return [] as EventRow[]
    return listData
      .map((item) => {
        const obj = isPlainObject(item) ? item : {}
        const eventId = toStr(obj['event_id']).trim()
        const eventDateRaw = obj['event_date']
        const eventDate = tryParseIsoDate(eventDateRaw)

        const produceNo = toStr(obj['produce_no'] ?? '').trim()
        const winder = toStr(obj['winder'] ?? '').trim()
        const slitting = toStr(obj['slitting'] ?? '').trim()
        const iqrCount = safeNumber(obj['iqr_count'])
        const t2Count = safeNumber(obj['t2_count'])
        const speCount = safeNumber(obj['spe_count'])
        return {
          event_id: eventId || pickId(item) || '(no id)',
          event_date_raw: eventDateRaw,
          event_date: eventDate,
          produce_no: produceNo,
          winder,
          slitting,
          iqr_count: iqrCount,
          t2_count: t2Count,
          spe_count: speCount,
        }
      })
      .filter((x) => x.event_id)
  }, [listData, props.view])

  const eventSummary = useMemo(() => {
    if (props.view !== 'events') return null
    const total = eventRows.length
    const withIqr = eventRows.filter((x) => x.iqr_count > 0).length
    const uniqueProduce = new Set(eventRows.map((x) => x.produce_no).filter(Boolean)).size
    return {
      total,
      withIqr,
      uniqueProduce,
    }
  }, [eventRows, props.view])

  const filteredEventRows = useMemo(() => {
    if (props.view !== 'events') return [] as EventRow[]
    const byPid = productIdNeedle.length > 0 ? eventRows.filter((r) => matchAnyProductId(r.produce_no, r.event_id)) : eventRows
    const q = query.trim().toLowerCase()
    const base = q
      ? byPid.filter((r) =>
          [r.event_id, r.produce_no, r.winder, r.slitting]
            .filter(Boolean)
            .some((v) => v.toLowerCase().includes(q)),
        )
      : byPid

    const sorted = [...base]
    switch (sortMode) {
      case 'anomaliesDesc':
        sorted.sort((a, b) => b.iqr_count - a.iqr_count || (b.event_date?.getTime() ?? 0) - (a.event_date?.getTime() ?? 0))
        break
      case 'alphaAsc':
        sorted.sort((a, b) => a.event_id.localeCompare(b.event_id))
        break
      case 'dateDesc':
      default:
        sorted.sort((a, b) => (b.event_date?.getTime() ?? 0) - (a.event_date?.getTime() ?? 0))
        break
    }
    return sorted
  }, [eventRows, matchAnyProductId, productIdNeedle.length, props.view, query, sortMode])

  const selectedEvent = useMemo(() => {
    if (props.view !== 'events') return null
    if (!selectedId) return null
    return filteredEventRows.find((x) => x.event_id === selectedId) ?? null
  }, [filteredEventRows, props.view, selectedId])

  // ===== Aggregated (ut_aggregated_diagnostics) =====
  type AggRow = {
    summary_id: string
    analysis_dimension: string
    sample_count: number
    context_preview: string
    core_feature_count: number
    event_count: number
  }

  const aggRows = useMemo(() => {
    if (props.view !== 'aggregated') return [] as AggRow[]
    if (!Array.isArray(listData)) return [] as AggRow[]

    return listData
      .map((item) => {
        const obj = isPlainObject(item) ? item : {}

        const summaryId = toStr(obj['summary_id']).trim() || pickId(item) || '(no id)'
        const dim = toStr(obj['analysis_dimension']).trim()
        const sample = safeNumber(obj['sample_count'])
        const ctxPreview = toStr(obj['context_preview']).trim()
        const coreCount = safeNumber(obj['core_feature_count'])
        const eventCount = safeNumber(obj['event_count'])
        return {
          summary_id: summaryId,
          analysis_dimension: dim,
          sample_count: sample,
          context_preview: ctxPreview,
          core_feature_count: coreCount,
          event_count: eventCount,
        }
      })
      .filter((x) => x.summary_id)
  }, [listData, props.view])

  const aggSummary = useMemo(() => {
    if (props.view !== 'aggregated') return null
    const total = aggRows.length
    const samples = aggRows.reduce((acc, r) => acc + (r.sample_count || 0), 0)
    const topDim = (() => {
      const map = new Map<string, number>()
      for (const r of aggRows) {
        const k = r.analysis_dimension || '(unknown)'
        map.set(k, (map.get(k) ?? 0) + 1)
      }
      return [...map.entries()].sort((a, b) => b[1] - a[1]).slice(0, 3)
    })()
    return { total, samples, topDim }
  }, [aggRows, props.view])

  const filteredAggRows = useMemo(() => {
    if (props.view !== 'aggregated') return [] as AggRow[]
    const byPid = productIdNeedle.length > 0 ? aggRows.filter((r) => matchAnyProductId(r.summary_id, r.analysis_dimension, r.context_preview)) : aggRows
    const q = query.trim().toLowerCase()
    const base = q
      ? byPid.filter((r) =>
          [r.summary_id, r.analysis_dimension, r.context_preview]
            .filter(Boolean)
            .some((v) => v.toLowerCase().includes(q)),
        )
      : byPid

    const sorted = [...base]
    if (sortMode === 'alphaAsc') {
      sorted.sort((a, b) => a.summary_id.localeCompare(b.summary_id))
    } else {
      sorted.sort((a, b) => b.sample_count - a.sample_count)
    }
    return sorted
  }, [aggRows, matchAnyProductId, productIdNeedle.length, props.view, query, sortMode])

  const selectedAgg = useMemo(() => {
    if (props.view !== 'aggregated') return null
    if (!selectedId) return null
    return filteredAggRows.find((x) => x.summary_id === selectedId) ?? null
  }, [filteredAggRows, props.view, selectedId])

  type CoreFeatureSummary = {
    feature: string
    iqr_freq: number
    t2_freq: number
    spe_freq: number
    total: number
  }

  const selectedAggDetail = useMemo(() => (props.view === 'aggregated' && isPlainObject(detailData) ? (detailData as any) : null), [detailData, props.view])

  const selectedAggCoreFeatures = useMemo(() => {
    if (props.view !== 'aggregated') return [] as CoreFeatureSummary[]
    if (!selectedAggDetail) return [] as CoreFeatureSummary[]
    const core = Array.isArray(selectedAggDetail['core_features']) ? (selectedAggDetail['core_features'] as unknown[]) : []
    const rows: CoreFeatureSummary[] = core
      .filter(isPlainObject)
      .map((x) => x as Record<string, unknown>)
      .map((x) => {
        const feature = toStr(x['feature']).trim()
        const iqr = safeNumber(x['iqr_freq'])
        const t2 = safeNumber(x['t2_freq'])
        const spe = safeNumber(x['spe_freq'])
        const total = safeNumber(x['total']) || iqr + t2 + spe
        return { feature, iqr_freq: iqr, t2_freq: t2, spe_freq: spe, total }
      })
      .filter((r) => Boolean(r.feature))
    rows.sort((a, b) => b.total - a.total || b.iqr_freq - a.iqr_freq || a.feature.localeCompare(b.feature))
    return rows
  }, [props.view, selectedAggDetail])

  // ===== Weighted contributions =====
  type WeightedItem = {
    id: string
    x_T2: number
    x_SPE: number
    t2_top: string
    spe_top: string
  }

  const weightedItems = useMemo(() => {
    if (props.view !== 'weighted') return [] as WeightedItem[]
    if (!Array.isArray(listData)) return [] as WeightedItem[]
    return listData
      .filter(isPlainObject)
      .map((x) => x as Record<string, unknown>)
      .map((row) => {
        const id = toStr(row['id']).trim()
        return {
          id,
          x_T2: safeNumber(row['x_T2']),
          x_SPE: safeNumber(row['x_SPE']),
          t2_top: toStr(row['t2_top']).trim(),
          spe_top: toStr(row['spe_top']).trim(),
        }
      })
      .filter((x) => x.id)
  }, [listData, props.view])

  const filteredWeightedItems = useMemo(() => {
    if (props.view !== 'weighted') return [] as WeightedItem[]
    const byPid = productIdNeedle.length > 0 ? weightedItems.filter((r) => matchAnyProductId(r.id)) : weightedItems
    const q = query.trim().toLowerCase()
    const base = q
      ? byPid.filter((r) => [r.id, r.t2_top, r.spe_top].filter(Boolean).some((v) => v.toLowerCase().includes(q)))
      : byPid
    const sorted = [...base]
    sorted.sort((a, b) => Math.max(b.x_T2, b.x_SPE) - Math.max(a.x_T2, a.x_SPE) || a.id.localeCompare(b.id))
    return sorted
  }, [matchAnyProductId, productIdNeedle.length, props.view, query, weightedItems])

  const selectedWeighted = useMemo(() => {
    if (props.view !== 'weighted') return null
    if (!selectedId) return null
    return filteredWeightedItems.find((x) => x.id === selectedId) ?? null
  }, [filteredWeightedItems, props.view, selectedId])

  // ===== RAG =====
  type RagEvent = {
    event_id: string
    feature_count: number
    sop_count: number
  }

  const ragEvents = useMemo(() => {
    if (props.view !== 'rag') return [] as RagEvent[]
    if (!Array.isArray(listData)) return [] as RagEvent[]
    return listData
      .filter(isPlainObject)
      .map((x) => x as Record<string, unknown>)
      .map((row) => {
        return {
          event_id: toStr(row['event_id']).trim(),
          feature_count: safeNumber(row['feature_count']),
          sop_count: safeNumber(row['sop_count']),
        }
      })
      .filter((x) => x.event_id)
  }, [listData, props.view])

  const filteredRagEvents = useMemo(() => {
    if (props.view !== 'rag') return [] as RagEvent[]
    const q = query.trim().toLowerCase()
    const byPid = productIdNeedle.length > 0 ? ragEvents.filter((r) => matchAnyProductId(r.event_id)) : ragEvents
    return q ? byPid.filter((r) => r.event_id.toLowerCase().includes(q)) : byPid
  }, [matchAnyProductId, productIdNeedle.length, props.view, query, ragEvents])

  const selectedRag = useMemo(() => {
    if (props.view !== 'rag') return null
    if (!selectedId) return null
    return filteredRagEvents.find((x) => x.event_id === selectedId) ?? null
  }, [filteredRagEvents, props.view, selectedId])

  // ===== LLM =====
  type LlmListItem = {
    event_id: string
    event_time_raw: unknown
    event_time: Date | null
    total_anomalies: number
  }

  const llmItems = useMemo(() => {
    if (props.view !== 'llm') return [] as LlmListItem[]
    if (!Array.isArray(listData)) return [] as LlmListItem[]
    return listData
      .filter(isPlainObject)
      .map((x) => x as Record<string, unknown>)
      .map((row) => {
        const eventId = toStr(row['event_id']).trim()
        const rawTime = row['event_time']
        const d = tryParseIsoDate(rawTime)
        return {
          event_id: eventId,
          event_time_raw: rawTime,
          event_time: d,
          total_anomalies: safeNumber(row['total_anomalies']),
        }
      })
      .filter((x) => x.event_id)
  }, [listData, props.view])

  const filteredLlmItems = useMemo(() => {
    if (props.view !== 'llm') return [] as LlmListItem[]
    const byPid = productIdNeedle.length > 0 ? llmItems.filter((r) => matchAnyProductId(r.event_id)) : llmItems
    const q = query.trim().toLowerCase()
    const base = q ? byPid.filter((r) => r.event_id.toLowerCase().includes(q)) : byPid
    const sorted = [...base]
    sorted.sort((a, b) => b.total_anomalies - a.total_anomalies)
    return sorted
  }, [llmItems, matchAnyProductId, productIdNeedle.length, props.view, query])

  const selectedLlmDetail = useMemo(() => (props.view === 'llm' && isPlainObject(detailData) ? (detailData as any) : null), [detailData, props.view])

  return (
    <div className="analytics-artifacts-root" style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div className="register-block" style={{ width: '100%' }}>
        <div className="register-title" style={{ marginBottom: 8 }}>改善報告</div>
        <div className="analytics-artifacts-hint" style={{ marginBottom: 10 }}>
          這些內容來自 Analytical-Four pipeline 產出的 JSON 檔案；若顯示 404，請先在外部產生檔案並放在 `september_v2`（或設定 `ANALYTICS_ARTIFACTS_DIR`）。
        </div>

        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
          <button type="button" className="btn-secondary" disabled={loadingList} onClick={refreshList}>
            {loadingList ? '更新中…' : '刷新清單'}
          </button>
          <button
            type="button"
            className="btn-primary"
            disabled={loadingListData || loadingDetail}
            onClick={() => {
              refreshListData()
              if (selectedId) refreshDetailData(selectedId)
            }}
          >
            {loadingListData || loadingDetail ? '載入中…' : '重新載入（清單/明細）'}
          </button>
          <div className="analytics-artifacts-hint">目前：<code>{artifactKey}</code></div>
          {selectedInfo ? (
            <div className="analytics-artifacts-hint">
              檔名：<code>{selectedInfo.filename}</code> / {selectedInfo.exists ? '存在' : '不存在'}
            </div>
          ) : null}
        </div>

        {productIdFilters.length > 0 ? (
          <div style={{ marginTop: 10 }}>
            <div className="analytics-artifacts-hint" style={{ marginBottom: 6 }}>產品編號（{productIdFilters.length}）：</div>
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
              {productIdFilters.slice(0, 12).map((pid) => (
                <span key={pid} className="analytics-pill">{pid}</span>
              ))}
              {productIdFilters.length > 12 ? <span className="analytics-artifacts-hint">…</span> : null}
            </div>
          </div>
        ) : null}

        <div style={{ marginTop: 10, display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
          <input
            className="register-input"
            placeholder={props.view === 'events' ? '搜尋 event_id / Produce_No. / Winder…' : '搜尋 id / 維度 / key…'}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            style={{ maxWidth: 420 }}
          />
          <select className="register-input" value={sortMode} onChange={(e) => setSortMode(e.target.value as any)} style={{ maxWidth: 220 }}>
            <option value="dateDesc">排序：日期（新→舊）</option>
            <option value="anomaliesDesc">排序：異常數（多→少）</option>
            <option value="sampleDesc">排序：樣本數（多→少）</option>
            <option value="alphaAsc">排序：ID（A→Z）</option>
          </select>
          <div>
            {props.view === 'events' && eventSummary ? (
              <>
                <span className="analytics-pill">Events: {eventSummary.total}</span>
                <span className="analytics-pill">有 IQR: {eventSummary.withIqr}</span>
                <span className="analytics-pill">Produce_No.: {eventSummary.uniqueProduce}</span>
              </>
            ) : null}
            {props.view === 'aggregated' && aggSummary ? (
              <>
                <span className="analytics-pill">Summaries: {aggSummary.total}</span>
                <span className="analytics-pill">樣本總和: {aggSummary.samples}</span>
                {aggSummary.topDim.map(([k, v]) => (
                  <span key={k} className="analytics-pill">{k}: {v}</span>
                ))}
              </>
            ) : null}
            {props.view === 'rag' ? (
              <>
                <span className="analytics-pill">Events: {ragEvents.length}</span>
              </>
            ) : null}
            {props.view === 'weighted' ? (
              <>
                <span className="analytics-pill">Items: {weightedItems.length}</span>
              </>
            ) : null}
          </div>
        </div>

        {listError ? <div className="error" style={{ marginTop: 10 }}>{listError}</div> : null}
        {listDataError ? <div className="error" style={{ marginTop: 10 }}>{listDataError}</div> : null}
        {detailError ? <div className="error" style={{ marginTop: 10 }}>{detailError}</div> : null}
      </div>

      {props.view === 'events' && eventRows.length > 0 ? (
        <div className="analytics-report-grid">
          <div className="register-block">
            <div className="register-title" style={{ marginBottom: 8 }}>事件清單（{filteredEventRows.length}）</div>
            <div className="analytics-report-list">
              {filteredEventRows.slice(0, 500).map((r) => {
                const active = r.event_id === selectedId
                return (
                  <button
                    key={r.event_id}
                    type="button"
                    className={active ? 'btn-primary' : 'btn-secondary'}
                    style={{ textAlign: 'left' }}
                    onClick={() => setSelectedId(r.event_id)}
                    title={r.event_id}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', gap: 10 }}>
                      <div style={{ fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis' }}>{r.produce_no || r.event_id}</div>
                      <div className="muted" style={{ whiteSpace: 'nowrap' }}>{formatIsoPreview(r.event_date_raw) || '-'}</div>
                    </div>
                    <div className="muted" style={{ marginTop: 4, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                      <span className="analytics-pill">IQR: {r.iqr_count}</span>
                      <span className="analytics-pill">T2: {r.t2_count}</span>
                      <span className="analytics-pill">SPE: {r.spe_count}</span>
                      {r.slitting ? <span className="analytics-pill">Slit: {r.slitting}</span> : null}
                      {r.winder ? <span className="analytics-pill">Winder: {r.winder}</span> : null}
                    </div>
                  </button>
                )
              })}
              {filteredEventRows.length > 500 ? <div className="muted">僅顯示前 500 筆（避免卡頓）</div> : null}
            </div>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            {selectedEvent ? (
              <>
                <div className="register-block">
                  <div className="register-title" style={{ marginBottom: 8 }}>事件摘要</div>
                  <div className="muted" style={{ marginBottom: 10 }}><code>{selectedEvent.event_id}</code></div>
                  <div className="analytics-report-kv">
                    <div><span className="analytics-report-k">時間</span><span className="analytics-report-v">{formatIsoPreview(selectedEvent.event_date_raw) || '-'}</span></div>
                    <div><span className="analytics-report-k">Produce_No.</span><span className="analytics-report-v">{selectedEvent.produce_no || '-'}</span></div>
                    <div><span className="analytics-report-k">Slitting</span><span className="analytics-report-v">{selectedEvent.slitting || '-'}</span></div>
                    <div><span className="analytics-report-k">Winder</span><span className="analytics-report-v">{selectedEvent.winder || '-'}</span></div>
                    <div><span className="analytics-report-k">IQR anomalies</span><span className="analytics-report-v">{selectedEvent.iqr_count}</span></div>
                  </div>
                </div>

                {props.view === 'events' && selectedId && isPlainObject(detailData) ? (
                  <>
                    {Array.isArray((detailData as any)?.iqr_features) ? (
                      <div className="register-block">
                        <div className="register-title" style={{ marginBottom: 8 }}>IQR 異常特徵</div>
                        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                          {((detailData as any).iqr_features as unknown[]).slice(0, 80).map((x, idx) => (
                            <span key={idx} className="analytics-pill">{toStr(x) || '-'}</span>
                          ))}
                        </div>
                      </div>
                    ) : null}

                    {Array.isArray((detailData as any)?.t2_features) ? (
                      <div className="register-block">
                        <div className="register-title" style={{ marginBottom: 8 }}>T2 Top Features</div>
                        <div className="analytics-report-table">
                          <div className="analytics-report-row analytics-report-head">
                            <div>feature</div>
                            <div>final_score</div>
                            <div>final_rank</div>
                          </div>
                          {((detailData as any).t2_features as unknown[]).slice(0, 20).filter(isPlainObject).map((x: any, idx: number) => (
                            <div key={idx} className="analytics-report-row">
                              <div>{toStr(x.feature) || '-'}</div>
                              <div>{safeNumber(x.final_score).toFixed(6)}</div>
                              <div>{safeNumber(x.final_rank)}</div>
                            </div>
                          ))}
                        </div>
                      </div>
                    ) : null}

                    {Array.isArray((detailData as any)?.spe_features) ? (
                      <div className="register-block">
                        <div className="register-title" style={{ marginBottom: 8 }}>SPE Top Features</div>
                        <div className="analytics-report-table">
                          <div className="analytics-report-row analytics-report-head">
                            <div>feature</div>
                            <div>final_score</div>
                            <div>final_rank</div>
                          </div>
                          {((detailData as any).spe_features as unknown[]).slice(0, 20).filter(isPlainObject).map((x: any, idx: number) => (
                            <div key={idx} className="analytics-report-row">
                              <div>{toStr(x.feature) || '-'}</div>
                              <div>{safeNumber(x.final_score).toFixed(6)}</div>
                              <div>{safeNumber(x.final_rank)}</div>
                            </div>
                          ))}
                        </div>
                      </div>
                    ) : null}
                  </>
                ) : null}
              </>
            ) : (
              <>
                <div className="register-block">
                  <div className="register-title" style={{ marginBottom: 8 }}>事件摘要</div>
                  <div className="muted">請從左側選擇一筆事件</div>
                </div>
              </>
            )}
          </div>
        </div>
      ) : props.view === 'aggregated' && aggRows.length > 0 ? (
        <div className="analytics-report-grid">
          <div className="register-block">
            <div className="register-title" style={{ marginBottom: 8 }}>彙總清單（{filteredAggRows.length}）</div>
            <div className="analytics-report-list">
              {filteredAggRows.slice(0, 500).map((r) => {
                const active = r.summary_id === selectedId
                return (
                  <button
                    key={r.summary_id}
                    type="button"
                    className={active ? 'btn-primary' : 'btn-secondary'}
                    style={{ textAlign: 'left' }}
                    onClick={() => setSelectedId(r.summary_id)}
                    title={r.summary_id}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', gap: 10 }}>
                      <div style={{ fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis' }}>{r.analysis_dimension || '(dimension)'}</div>
                      <div className="muted" style={{ whiteSpace: 'nowrap' }}>樣本 {r.sample_count}</div>
                    </div>
                    <div className="muted" style={{ marginTop: 4, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                      <span className="analytics-pill">core: {r.core_feature_count}</span>
                      <span className="analytics-pill">events: {r.event_count}</span>
                      {r.context_preview ? <span className="analytics-pill">{r.context_preview}</span> : null}
                    </div>
                  </button>
                )
              })}
              {filteredAggRows.length > 500 ? <div className="muted">僅顯示前 500 筆（避免卡頓）</div> : null}
            </div>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            {selectedAgg ? (
              <>
                <div className="register-block">
                  <div className="register-title" style={{ marginBottom: 8 }}>彙總摘要</div>
                  <div className="muted" style={{ marginBottom: 10 }}><code>{selectedAgg.summary_id}</code></div>
                  <div className="analytics-report-kv">
                    <div><span className="analytics-report-k">維度</span><span className="analytics-report-v">{selectedAgg.analysis_dimension || '-'}</span></div>
                    <div><span className="analytics-report-k">樣本數</span><span className="analytics-report-v">{selectedAgg.sample_count}</span></div>
                    <div><span className="analytics-report-k">events</span><span className="analytics-report-v">{selectedAgg.event_count}</span></div>
                    <div><span className="analytics-report-k">core features</span><span className="analytics-report-v">{selectedAgg.core_feature_count}</span></div>
                  </div>
                </div>

                <div className="register-block">
                  <div className="register-title" style={{ marginBottom: 8 }}>Core Features 重點摘要</div>
                  {selectedAggCoreFeatures.length === 0 ? (
                    <div className="muted">找不到 core_features 或 evidence 結構不符合預期</div>
                  ) : (
                    <>
                      <div className="muted" style={{ marginBottom: 10 }}>
                        依 evidence 頻率（IQR + T2 + SPE）排序，僅顯示前 12 個。
                      </div>
                      <div className="analytics-report-card-grid">
                        {selectedAggCoreFeatures.slice(0, 12).map((r) => (
                          <div key={r.feature} className="analytics-report-card">
                            <div style={{ display: 'flex', justifyContent: 'space-between', gap: 10, alignItems: 'baseline' }}>
                              <div style={{ fontWeight: 800, overflow: 'hidden', textOverflow: 'ellipsis' }}>{r.feature}</div>
                              <div className="muted" style={{ whiteSpace: 'nowrap' }}>Total {r.total}</div>
                            </div>
                            <div className="muted" style={{ marginTop: 8, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                              <span className="analytics-pill">IQR: {r.iqr_freq}</span>
                              <span className="analytics-pill">T2: {r.t2_freq}</span>
                              <span className="analytics-pill">SPE: {r.spe_freq}</span>
                            </div>
                          </div>
                        ))}
                      </div>
                    </>
                  )}
                </div>
              </>
            ) : (
              <>
                <div className="register-block"><div className="register-title" style={{ marginBottom: 8 }}>彙總摘要</div><div className="muted">請從左側選擇一筆彙總</div></div>
              </>
            )}
          </div>
        </div>
      ) : props.view === 'weighted' && weightedItems.length > 0 ? (
        <div className="analytics-report-grid">
          <div className="register-block">
            <div className="register-title" style={{ marginBottom: 8 }}>案件清單（{filteredWeightedItems.length}）</div>
            <div className="analytics-report-list">
              {filteredWeightedItems.slice(0, 500).map((r) => {
                const active = r.id === selectedId
                return (
                  <button
                    key={r.id}
                    type="button"
                    className={active ? 'btn-primary' : 'btn-secondary'}
                    style={{ textAlign: 'left' }}
                    onClick={() => setSelectedId(r.id)}
                    title={r.id}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', gap: 10 }}>
                      <div style={{ fontWeight: 600 }}>{r.id}</div>
                      <div className="muted" style={{ whiteSpace: 'nowrap' }}>x_T2 {r.x_T2.toFixed(3)} / x_SPE {r.x_SPE.toFixed(3)}</div>
                    </div>
                    <div className="muted" style={{ marginTop: 4, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                      {r.t2_top ? <span className="analytics-pill">T2 top: {r.t2_top}</span> : null}
                      {r.spe_top ? <span className="analytics-pill">SPE top: {r.spe_top}</span> : null}
                    </div>
                  </button>
                )
              })}
              {filteredWeightedItems.length > 500 ? <div className="muted">僅顯示前 500 筆（避免卡頓）</div> : null}
            </div>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            {selectedWeighted && isPlainObject(detailData) ? (
              <>
                <div className="register-block">
                  <div className="register-title" style={{ marginBottom: 8 }}>加權貢獻摘要</div>
                  <div className="muted" style={{ marginBottom: 10 }}><code>{selectedWeighted.id}</code></div>
                  <div className="analytics-report-kv">
                    <div><span className="analytics-report-k">x_T2</span><span className="analytics-report-v">{selectedWeighted.x_T2.toFixed(3)}</span></div>
                    <div><span className="analytics-report-k">x_SPE</span><span className="analytics-report-v">{selectedWeighted.x_SPE.toFixed(3)}</span></div>
                  </div>
                </div>

                {(() => {
                  const t2 = Array.isArray((detailData as any)?.t2_features) ? ((detailData as any).t2_features as unknown[]) : []
                  const spe = Array.isArray((detailData as any)?.spe_features) ? ((detailData as any).spe_features as unknown[]) : []
                  const top10 = (items: unknown[]) => items.filter(isPlainObject).map((x) => x as Record<string, unknown>).slice(0, 10)
                  return (
                    <>
                      <div className="register-block">
                        <div className="register-title" style={{ marginBottom: 8 }}>T2 Top Features</div>
                        <div className="analytics-report-table">
                          <div className="analytics-report-row analytics-report-head">
                            <div>feature</div>
                            <div>final_score</div>
                            <div>final_rank</div>
                          </div>
                          {top10(t2).map((x, idx) => (
                            <div key={idx} className="analytics-report-row">
                              <div>{toStr(x['feature'])}</div>
                              <div>{safeNumber(x['final_score']).toFixed(6)}</div>
                              <div>{safeNumber(x['final_rank'])}</div>
                            </div>
                          ))}
                        </div>
                      </div>

                      <div className="register-block">
                        <div className="register-title" style={{ marginBottom: 8 }}>SPE Top Features</div>
                        <div className="analytics-report-table">
                          <div className="analytics-report-row analytics-report-head">
                            <div>feature</div>
                            <div>final_score</div>
                            <div>final_rank</div>
                          </div>
                          {top10(spe).map((x, idx) => (
                            <div key={idx} className="analytics-report-row">
                              <div>{toStr(x['feature'])}</div>
                              <div>{safeNumber(x['final_score']).toFixed(6)}</div>
                              <div>{safeNumber(x['final_rank'])}</div>
                            </div>
                          ))}
                        </div>
                      </div>
                    </>
                  )
                })()}
              </>
            ) : (
              <>
                <div className="register-block"><div className="register-title" style={{ marginBottom: 8 }}>加權貢獻摘要</div><div className="muted">請從左側選擇一筆案件</div></div>
              </>
            )}
          </div>
        </div>
      ) : props.view === 'rag' && ragEvents.length > 0 ? (
        <div className="analytics-report-grid">
          <div className="register-block">
            <div className="register-title" style={{ marginBottom: 8 }}>事件清單（{filteredRagEvents.length}）</div>
            <div className="analytics-report-list">
              {filteredRagEvents.slice(0, 500).map((r) => {
                const active = r.event_id === selectedId
                return (
                  <button
                    key={r.event_id}
                    type="button"
                    className={active ? 'btn-primary' : 'btn-secondary'}
                    style={{ textAlign: 'left' }}
                    onClick={() => setSelectedId(r.event_id)}
                    title={r.event_id}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', gap: 10 }}>
                      <div style={{ fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis' }}>{r.event_id}</div>
                      <div className="muted" style={{ whiteSpace: 'nowrap' }}>SOP {r.sop_count}</div>
                    </div>
                    <div className="muted" style={{ marginTop: 4, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                      <span className="analytics-pill">features: {r.feature_count}</span>
                    </div>
                  </button>
                )
              })}
              {filteredRagEvents.length > 500 ? <div className="muted">僅顯示前 500 筆（避免卡頓）</div> : null}
            </div>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            {selectedRag && isPlainObject(detailData) ? (
              <>
                <div className="register-block">
                  <div className="register-title" style={{ marginBottom: 8 }}>SOP 建議（RAG）</div>
                  <div className="analytics-artifacts-hint" style={{ marginBottom: 10 }}><code>{selectedRag.event_id}</code></div>
                  {Object.entries(((detailData as any)?.features ?? {}) as Record<string, unknown>).map(([feature, rows]) => {
                    const arr = Array.isArray(rows) ? (rows as unknown[]) : []
                    if (arr.length === 0) return null
                    return (
                      <div key={feature} style={{ marginBottom: 12 }}>
                        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'baseline' }}>
                          <div style={{ fontWeight: 700 }}>{feature}</div>
                          <span className="analytics-pill">{arr.length} 條</span>
                        </div>
                        <div className="analytics-report-table" style={{ marginTop: 6 }}>
                          <div
                            className="analytics-report-row analytics-report-head"
                            style={{ gridTemplateColumns: '90px 130px 120px 1.2fr 1.2fr 120px' }}
                          >
                            <div>code</div>
                            <div>station</div>
                            <div>kind</div>
                            <div>problem</div>
                            <div>action</div>
                            <div>section</div>
                          </div>
                          {arr.slice(0, 20).filter(isPlainObject).map((row: any, idx) => {
                            const code = toStr(row.code)
                            const station = toStr(row.station)
                            const kind = toStr(row.kind)
                            const problem = toStr(row.problem)
                            const action = toStr(row.action)
                            const section = toStr(row.section)
                            return (
                              <div
                                key={idx}
                                className="analytics-report-row"
                                style={{ gridTemplateColumns: '90px 130px 120px 1.2fr 1.2fr 120px' }}
                                title={[code, station, kind, problem, action, section].filter(Boolean).join(' / ')}
                              >
                                <div>{code || '-'}</div>
                                <div>{station || '-'}</div>
                                <div>{kind || '-'}</div>
                                <div style={{ whiteSpace: 'normal' }}>{problem || '-'}</div>
                                <div style={{ whiteSpace: 'normal' }}>{action || '-'}</div>
                                <div>{section || '-'}</div>
                              </div>
                            )
                          })}
                          {arr.length > 20 ? (
                            <div className="analytics-artifacts-hint" style={{ padding: '8px 10px' }}>
                              僅顯示前 20 條（避免卡頓）
                            </div>
                          ) : null}
                        </div>
                      </div>
                    )
                  })}
                </div>
              </>
            ) : (
              <>
                <div className="register-block"><div className="register-title" style={{ marginBottom: 8 }}>SOP 建議（RAG）</div><div className="analytics-artifacts-hint">請從左側選擇一筆事件</div></div>
              </>
            )}
          </div>
        </div>
      ) : props.view === 'llm' && llmItems.length > 0 ? (
        <div className="analytics-report-grid">
          <div className="register-block">
            <div className="register-title" style={{ marginBottom: 8 }}>事件清單（{filteredLlmItems.length}）</div>
            <div className="analytics-report-list">
              {filteredLlmItems.slice(0, 500).map((r) => {
                const active = r.event_id === selectedId
                return (
                  <button
                    key={r.event_id}
                    type="button"
                    className={active ? 'btn-primary' : 'btn-secondary'}
                    style={{ textAlign: 'left' }}
                    onClick={() => setSelectedId(r.event_id)}
                    title={r.event_id}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', gap: 10 }}>
                      <div style={{ fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis' }}>{r.event_id}</div>
                      <div className="muted" style={{ whiteSpace: 'nowrap' }}>異常 {r.total_anomalies}</div>
                    </div>
                    <div className="muted" style={{ marginTop: 4 }}>{formatIsoPreview(r.event_time_raw) || '-'}</div>
                  </button>
                )
              })}
              {filteredLlmItems.length > 500 ? <div className="muted">僅顯示前 500 筆（避免卡頓）</div> : null}
            </div>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            {selectedLlmDetail ? (
              <>
                <div className="register-block">
                  <div className="register-title" style={{ marginBottom: 8 }}>LLM 主異常清單（表格）</div>
                  <div className="analytics-report-kv">
                    <div><span className="analytics-report-k">event_id</span><span className="analytics-report-v"><code>{toStr(selectedLlmDetail.event_id) || '-'}</code></span></div>
                    <div><span className="analytics-report-k">event_time</span><span className="analytics-report-v">{formatIsoPreview(selectedLlmDetail.event_time) || '-'}</span></div>
                    <div><span className="analytics-report-k">total_anomalies</span><span className="analytics-report-v">{safeNumber(selectedLlmDetail.total_anomalies)}</span></div>
                  </div>
                </div>

                {Array.isArray(selectedLlmDetail.by_station) ? (
                  <div className="register-block">
                    <div className="register-title" style={{ marginBottom: 8 }}>按站點</div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                      {(selectedLlmDetail.by_station as unknown[]).filter(isPlainObject).map((stationRow: any) => {
                        const station = toStr(stationRow.station)
                        const anomalies = Array.isArray(stationRow.anomalies) ? (stationRow.anomalies as unknown[]) : []
                        if (anomalies.length === 0) return null
                        return (
                          <div key={station} className="analytics-report-subcard">
                            <div style={{ display: 'flex', gap: 8, alignItems: 'baseline', flexWrap: 'wrap' }}>
                              <div style={{ fontWeight: 800 }}>{station || '(station)'}</div>
                              <span className="analytics-pill">{anomalies.length} 條</span>
                            </div>
                            <div className="analytics-report-table" style={{ marginTop: 8 }}>
                              <div className="analytics-report-row analytics-report-head" style={{ gridTemplateColumns: '220px 150px 1.5fr' }}>
                                <div>feature</div>
                                <div>method</div>
                                <div>description</div>
                              </div>
                              {anomalies.slice(0, 50).filter(isPlainObject).map((it: any, idx: number) => (
                                <div key={idx} className="analytics-report-row" style={{ gridTemplateColumns: '220px 150px 1.5fr' }}>
                                  <div>{toStr(it.feature_name) || '-'}</div>
                                  <div>{toStr(it.detection_method) || '-'}</div>
                                  <div style={{ whiteSpace: 'normal' }}>{toStr(it.problem_description) || '-'}</div>
                                </div>
                              ))}
                            </div>
                          </div>
                        )
                      })}
                    </div>
                  </div>
                ) : null}
              </>
            ) : (
              <div className="register-block"><div className="register-title" style={{ marginBottom: 8 }}>LLM 主異常清單（表格）</div><div className="muted">請從左側選擇一筆事件</div></div>
            )}
          </div>
        </div>
      ) : (
        <div className="register-block">
          <div className="register-title" style={{ marginBottom: 8 }}>改善報告</div>
          <div className="muted">目前沒有可顯示的表格資料（或檔案不存在）。</div>
        </div>
      )}
    </div>
  )
}

export type { ViewKey }
