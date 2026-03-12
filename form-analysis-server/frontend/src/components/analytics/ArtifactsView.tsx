import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  fetchComplaintAnalysis,
  fetchArtifactDetailView,
  fetchArtifactList,
  fetchArtifactListView,
  fetchArtifactSnapshotView,
  type ArtifactKey,
  type ArtifactInputResolveResult,
  type ComplaintAnalysisResult,
  type ArtifactUnifiedSnapshot,
  type ArtifactListItem,
} from '../../services/analyticsArtifacts'
import { useToast } from '../common/ToastContext'
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ScatterChart,
  Scatter,
  ZAxis,
} from 'recharts'

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
  const { showToast } = useToast()

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
  const [resolveMeta, setResolveMeta] = useState<ArtifactInputResolveResult | null>(null)
  const [snapshotData, setSnapshotData] = useState<ArtifactUnifiedSnapshot | null>(null)
  const [complaintAnalysis, setComplaintAnalysis] = useState<ComplaintAnalysisResult | null>(null)

  const [detailData, setDetailData] = useState<unknown>(null)
  const [detailError, setDetailError] = useState('')
  const [loadingDetail, setLoadingDetail] = useState(false)

  const [query, setQuery] = useState('')
  const [selectedId, setSelectedId] = useState<string>('')
  const [mappingNotice, setMappingNotice] = useState('')

  const [sortMode, setSortMode] = useState<'dateDesc' | 'anomaliesDesc' | 'sampleDesc' | 'alphaAsc'>('dateDesc')
  const [showDiagnosticsPanel, setShowDiagnosticsPanel] = useState(false)
  const [complaintRunPending, setComplaintRunPending] = useState(false)
  const listDataReqSeqRef = useRef(0)
  const unmatchedToastSigRef = useRef('')

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
    const reqSeq = ++listDataReqSeqRef.current
    void (async () => {
      try {
        setLoadingListData(true)
        setListDataError('')
        setResolveMeta(null)
        setSnapshotData(null)
        setComplaintAnalysis(null)
        let effectiveProductIds = productIdFilters
        if (productIdFilters.length > 0) {
          const complaint = await fetchComplaintAnalysis(requestOpts, {
            productIds: productIdFilters,
            snapshotArtifactKey: artifactKey,
            includeReportViews: ['llm_reports', 'rag_results'],
          })
          const resolved = complaint.input_summary
          if (reqSeq !== listDataReqSeqRef.current) return
          setResolveMeta(resolved)
          setComplaintAnalysis(complaint)
          if (resolved.resolved.length > 0) {
            effectiveProductIds = resolved.resolved
          } else {
            if (reqSeq !== listDataReqSeqRef.current) return
            setListData([])
            return
          }
          setSnapshotData(complaint.snapshot)
        } else {
          const snapshot = await fetchArtifactSnapshotView(artifactKey, requestOpts, { productIds: productIdFilters })
          if (reqSeq !== listDataReqSeqRef.current) return
          setSnapshotData(snapshot)
        }
        if (reqSeq !== listDataReqSeqRef.current) return
        const json = await fetchArtifactListView(artifactKey, requestOpts, { productIds: effectiveProductIds })
        if (reqSeq !== listDataReqSeqRef.current) return
        setListData(json)
      } catch (e: any) {
        if (reqSeq !== listDataReqSeqRef.current) return
        setListData(null)
        setListDataError(String(e?.message || e))
        setResolveMeta(null)
        setSnapshotData(null)
        setComplaintAnalysis(null)
      } finally {
        if (reqSeq !== listDataReqSeqRef.current) return
        setLoadingListData(false)
      }
    })()
  }, [artifactKey, productIdFilters, requestOpts])

  const unmatchedDiagnostics = useMemo(() => {
    if (!resolveMeta || !Array.isArray(resolveMeta.unmatched)) return [] as Array<{
      productId: string
      reasonCode: string
      reasonMessage: string
      normalized: string[]
      traceTokens: string[]
    }>
    return resolveMeta.unmatched.map((pid) => {
      const diag = resolveMeta.match_diagnostics?.[pid]
      return {
        productId: pid,
        reasonCode: diag?.reason_code || '',
        reasonMessage: diag?.reason_message || '',
        normalized: Array.isArray(resolveMeta.normalized_inputs?.[pid]) ? resolveMeta.normalized_inputs[pid] : [],
        traceTokens: Array.isArray(resolveMeta.trace_tokens?.[pid]) ? resolveMeta.trace_tokens[pid] : [],
      }
    })
  }, [resolveMeta])

  const inputMatchSummary = useMemo(() => {
    if (!resolveMeta) return [] as Array<{
      productId: string
      matched: boolean
      hitCount: number
      matchedStage: string
      reasonCode: string
      reasonMessage: string
      matchedTokens: string[]
      matchedBy: string[]
    }>
    const requested = Array.isArray(resolveMeta.requested) ? resolveMeta.requested : []
    const mapping = complaintAnalysis?.mapping && typeof complaintAnalysis.mapping === 'object' ? complaintAnalysis.mapping : {}
    return requested.map((pid) => {
      const hits = Array.isArray(resolveMeta.matches?.[pid]) ? resolveMeta.matches[pid] : []
      const diag = resolveMeta.match_diagnostics?.[pid]
      const mapRow = mapping?.[pid]
      const mapTokens =
        mapRow && Array.isArray((mapRow as any).matched_tokens)
          ? ((mapRow as any).matched_tokens as string[]).map((x) => String(x).trim()).filter(Boolean)
          : []
      const stage =
        mapRow && typeof (mapRow as any).matched_stage === 'string'
          ? String((mapRow as any).matched_stage)
          : hits.length > 0
            ? 'matched_direct'
            : 'unmatched'
      return {
        productId: pid,
        matched: hits.length > 0,
        hitCount: hits.length,
        matchedStage: stage,
        reasonCode: diag?.reason_code || '',
        reasonMessage: diag?.reason_message || '',
        matchedTokens: mapTokens.length > 0 ? mapTokens : hits,
        matchedBy: Array.isArray(diag?.matched_by) ? diag.matched_by : [],
      }
    })
  }, [complaintAnalysis?.mapping, resolveMeta])

  useEffect(() => {
    if (!resolveMeta) return
    const unmatchedCount = Number(resolveMeta.unmatched_count ?? 0)
    if (unmatchedCount <= 0) return
    const reasonPairs = Object.entries(resolveMeta.unmatched_reason_counts || {})
      .filter(([, v]) => Number(v) > 0)
      .map(([k, v]) => `${k}:${Number(v)}`)
      .join(', ')
    const sig = `${unmatchedCount}|${reasonPairs}`
    if (unmatchedToastSigRef.current === sig) return
    unmatchedToastSigRef.current = sig
    showToast(
      'info',
      reasonPairs
        ? `未命中 ${unmatchedCount} 筆（${reasonPairs}）`
        : `未命中 ${unmatchedCount} 筆`,
      { key: 'complaint-unmatched-summary', durationMs: 3000 },
    )
  }, [resolveMeta, showToast])

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
    if (productIdFilters.length > 0) {
      setComplaintRunPending(true)
    } else {
      setComplaintRunPending(false)
    }
  }, [productIdFilters])

  useEffect(() => {
    setSelectedId('')
    setQuery('')
    setDetailData(null)
    setDetailError('')
    if (productIdFilters.length > 0 && complaintRunPending) {
      return
    }
    const timer = window.setTimeout(() => {
      refreshListData()
    }, 350)
    return () => {
      window.clearTimeout(timer)
    }
  }, [artifactKey, complaintRunPending, productIdFilters.length, refreshListData])

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

  const eventTrendData = useMemo(() => {
    if (props.view !== 'events') return [] as Array<{ day: string; events: number; iqr: number }>
    const m = new Map<string, { events: number; iqr: number }>()
    for (const row of filteredEventRows) {
      const day = formatIsoPreview(row.event_date_raw).slice(0, 10) || 'Unknown'
      const prev = m.get(day) ?? { events: 0, iqr: 0 }
      prev.events += 1
      if (row.iqr_count > 0) prev.iqr += 1
      m.set(day, prev)
    }
    return [...m.entries()]
      .map(([day, v]) => ({ day, events: v.events, iqr: v.iqr }))
      .sort((a, b) => a.day.localeCompare(b.day))
      .slice(-30)
  }, [filteredEventRows, props.view])

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

  const aggCoreChartData = useMemo(() => {
    return selectedAggCoreFeatures.slice(0, 12).map((r) => ({
      feature: r.feature,
      IQR: r.iqr_freq,
      T2: r.t2_freq,
      SPE: r.spe_freq,
      total: r.total,
    }))
  }, [selectedAggCoreFeatures])

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

  const weightedScatterData = useMemo(() => {
    if (props.view !== 'weighted') return [] as Array<{ id: string; x: number; y: number; z: number }>
    return filteredWeightedItems.slice(0, 400).map((r) => ({
      id: r.id,
      x: Number(r.x_T2) || 0,
      y: Number(r.x_SPE) || 0,
      z: Math.max(1, Math.round((Math.max(Number(r.x_T2) || 0, Number(r.x_SPE) || 0) + 0.01) * 24)),
    }))
  }, [filteredWeightedItems, props.view])

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

  const currentFilteredCount = useMemo(() => {
    if (props.view === 'events') return filteredEventRows.length
    if (props.view === 'aggregated') return filteredAggRows.length
    if (props.view === 'weighted') return filteredWeightedItems.length
    if (props.view === 'rag') return filteredRagEvents.length
    if (props.view === 'llm') return filteredLlmItems.length
    return 0
  }, [
    filteredAggRows.length,
    filteredEventRows.length,
    filteredLlmItems.length,
    filteredRagEvents.length,
    filteredWeightedItems.length,
    props.view,
  ])

  const resolveDetailIdFromToken = useCallback(
    (token: string): string => {
      const t = String(token || '').trim()
      if (!t) return ''
      const low = t.toLowerCase()

      if (props.view === 'events') {
        for (const row of filteredEventRows) {
          if (row.event_id.toLowerCase() === low) return row.event_id
          if (row.produce_no && row.produce_no.toLowerCase() === low) return row.event_id
        }
        return ''
      }
      if (props.view === 'aggregated') {
        for (const row of filteredAggRows) {
          if (row.summary_id.toLowerCase() === low) return row.summary_id
          if (row.analysis_dimension && row.analysis_dimension.toLowerCase() === low) return row.summary_id
        }
        return ''
      }
      if (props.view === 'weighted') {
        for (const row of filteredWeightedItems) {
          if (row.id.toLowerCase() === low) return row.id
        }
        return ''
      }
      if (props.view === 'rag') {
        for (const row of filteredRagEvents) {
          if (row.event_id.toLowerCase() === low) return row.event_id
        }
        return ''
      }
      if (props.view === 'llm') {
        for (const row of filteredLlmItems) {
          if (row.event_id.toLowerCase() === low) return row.event_id
        }
        return ''
      }
      return ''
    },
    [
      filteredAggRows,
      filteredEventRows,
      filteredLlmItems,
      filteredRagEvents,
      filteredWeightedItems,
      props.view,
    ],
  )

  const jumpToMappedDetail = useCallback(
    (tokens: string[]) => {
      setMappingNotice('')
      for (const token of tokens) {
        const id = resolveDetailIdFromToken(token)
        if (!id) continue
        setSelectedId(id)
        setMappingNotice(`已定位到 ${id}`)
        return
      }
      const preview = tokens.slice(0, 3).join(', ')
      setMappingNotice(
        preview
          ? `目前視圖無法定位這些 token：${preview}。可切換 artifacts 視圖再試。`
          : '目前視圖找不到可關聯 token。',
      )
    },
    [resolveDetailIdFromToken],
  )

  const emptyHint = useMemo(() => {
    const hasFilters = productIdFilters.length > 0
    const allUnmatched =
      hasFilters &&
      !!resolveMeta &&
      Number(resolveMeta.requested_count ?? 0) > 0 &&
      Number(resolveMeta.resolved_count ?? 0) === 0
    if (allUnmatched) {
      return '此批輸入皆未命中。系統已切換為 diagnostics-only 模式，僅顯示未命中診斷。'
    }
    if (productIdFilters.length === 0) {
      return '目前沒有可顯示的表格資料（或檔案不存在）。'
    }
    if (props.view === 'events') {
      return '目前 product_id 過濾後為 0 筆。此視圖主要索引 event_id 或 Produce_No.（例如 2507173_02_19）。'
    }
    if (props.view === 'weighted' || props.view === 'rag' || props.view === 'llm') {
      return '目前 product_id 過濾後為 0 筆。此視圖主要索引 event_id（多為 UUID）。'
    }
    if (props.view === 'aggregated') {
      return '目前 product_id 過濾後為 0 筆。此視圖主要索引 summary_id/analysis_dimension。'
    }
    return '目前沒有可顯示的表格資料（或檔案不存在）。'
  }, [productIdFilters.length, props.view, resolveMeta])

  const localCrossComplaintSnapshot = useMemo(() => {
    const stationMap = new Map<string, number>()
    const machineMap = new Map<string, number>()
    const featureMap = new Map<string, number>()
    let sampleCount = 0

    if (props.view === 'events') {
      for (const row of filteredEventRows) {
        sampleCount += 1
        const station = (row.slitting || '').trim() || 'Unknown'
        const machine = (row.winder || '').trim() || 'Unknown'
        stationMap.set(station, (stationMap.get(station) ?? 0) + 1)
        machineMap.set(machine, (machineMap.get(machine) ?? 0) + 1)
        featureMap.set('IQR', (featureMap.get('IQR') ?? 0) + Number(row.iqr_count || 0))
        featureMap.set('T2', (featureMap.get('T2') ?? 0) + Number(row.t2_count || 0))
        featureMap.set('SPE', (featureMap.get('SPE') ?? 0) + Number(row.spe_count || 0))
      }
    } else if (props.view === 'weighted') {
      for (const row of filteredWeightedItems) {
        sampleCount += 1
        const t2 = (row.t2_top || '').trim()
        const spe = (row.spe_top || '').trim()
        if (t2) featureMap.set(`T2:${t2}`, (featureMap.get(`T2:${t2}`) ?? 0) + 1)
        if (spe) featureMap.set(`SPE:${spe}`, (featureMap.get(`SPE:${spe}`) ?? 0) + 1)
      }
    } else if (props.view === 'llm') {
      for (const row of filteredLlmItems) {
        sampleCount += 1
        featureMap.set('LLM:anomalies', (featureMap.get('LLM:anomalies') ?? 0) + Number(row.total_anomalies || 0))
      }
    }

    const stationRows = [...stationMap.entries()].map(([name, count]) => ({ name, count })).sort((a, b) => b.count - a.count)
    const machineRows = [...machineMap.entries()].map(([name, count]) => ({ name, count })).sort((a, b) => b.count - a.count)
    const featureRows = [...featureMap.entries()].map(([name, count]) => ({ name, count })).sort((a, b) => b.count - a.count)

    return {
      sampleCount,
      stationRows,
      machineRows,
      featureRows,
      metrics: {} as Record<string, number>,
    }
  }, [filteredEventRows, filteredLlmItems, filteredWeightedItems, props.view])

  const crossComplaintSnapshot = useMemo(() => {
    if (!snapshotData) return localCrossComplaintSnapshot
    return {
      sampleCount: Number(snapshotData.sample_count || 0),
      stationRows: snapshotData.station_distribution.map((x) => ({ name: x.name, count: Number(x.count || 0) })),
      machineRows: snapshotData.machine_distribution.map((x) => ({ name: x.name, count: Number(x.count || 0) })),
      featureRows: snapshotData.top_features.map((x) => ({ name: x.name, count: Number(x.count || 0) })),
      metrics: snapshotData.metrics || {},
    }
  }, [localCrossComplaintSnapshot, snapshotData])

  const complaintReportSnapshot = useMemo(() => {
    const payload = complaintAnalysis?.report_payload
    if (!payload || typeof payload !== 'object') {
      return { llm: null as ArtifactUnifiedSnapshot | null, rag: null as ArtifactUnifiedSnapshot | null }
    }
    const llm = payload['llm_reports'] ?? null
    const rag = payload['rag_results'] ?? null
    return { llm, rag }
  }, [complaintAnalysis])

  const complaintReportComposition = useMemo(() => {
    const c = complaintAnalysis?.report_composition
    if (!c || typeof c !== 'object') {
      return { summary: [] as string[], suggestions: [] as string[], evidence_refs: [] as Array<{ requested_id: string; token: string; source: string }> }
    }
    return {
      summary: Array.isArray(c.summary) ? c.summary.map((x) => String(x).trim()).filter(Boolean) : [],
      suggestions: Array.isArray(c.suggestions) ? c.suggestions.map((x) => String(x).trim()).filter(Boolean) : [],
      evidence_refs: Array.isArray(c.evidence_refs)
        ? c.evidence_refs
            .filter((x) => x && typeof x === 'object')
            .map((x: any) => ({
              requested_id: String(x.requested_id ?? '').trim(),
              token: String(x.token ?? '').trim(),
              source: String(x.source ?? '').trim(),
            }))
            .filter((x) => x.token)
        : [],
    }
  }, [complaintAnalysis?.report_composition])

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
          {productIdFilters.length > 0 ? (
            <button
              type="button"
              className="btn-primary"
              disabled={loadingListData || loadingDetail}
              onClick={() => {
                setComplaintRunPending(false)
                refreshListData()
              }}
            >
              {loadingListData || loadingDetail ? '分析中…' : '開始客訴分析'}
            </button>
          ) : null}
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
            {complaintRunPending ? (
              <div className="analytics-artifacts-hint" style={{ marginTop: 6 }}>
                已更新客訴輸入，請按「開始客訴分析」執行。
              </div>
            ) : null}
          </div>
        ) : null}

        {resolveMeta ? (
          <div style={{ marginTop: 10, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <span className="analytics-pill">requested: {Number(resolveMeta.requested_count ?? 0)}</span>
            <span className="analytics-pill">resolved: {Number(resolveMeta.resolved_count ?? 0)}</span>
            <span className="analytics-pill">unmatched: {Number(resolveMeta.unmatched_count ?? 0)}</span>
            <span className="analytics-pill">trace_attempted: {Number(resolveMeta.trace_attempted_count ?? 0)}</span>
            <span className="analytics-pill">trace_resolved: {Number(resolveMeta.trace_resolved_count ?? 0)}</span>
            {Object.entries(resolveMeta.unmatched_reason_counts || {}).map(([k, v]) => (
              <span key={k} className="analytics-pill">{k}: {Number(v || 0)}</span>
            ))}
          </div>
        ) : null}

        {resolveMeta && Number(resolveMeta.requested_count ?? 0) > 0 && Number(resolveMeta.resolved_count ?? 0) === 0 ? (
          <div style={{ marginTop: 10, border: '1px solid #fecaca', background: '#fff1f2', borderRadius: 8, padding: 10 }}>
            <div style={{ fontWeight: 700, marginBottom: 4 }}>Diagnostics-only 模式</div>
            <div className="analytics-artifacts-hint">
              本次客訴 product_id 全部未命中，已停用圖表/報告資料計算，僅保留未命中原因與 trace 診斷資訊。
            </div>
          </div>
        ) : null}

        {productIdFilters.length > 0 ? (
          <div style={{ marginTop: 10, border: '1px solid #d1fae5', background: '#ecfdf5', borderRadius: 8, padding: 10 }}>
            <div style={{ fontWeight: 700, marginBottom: 6 }}>跨客訴彙總快照</div>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 8 }}>
              <span className="analytics-pill">samples: {crossComplaintSnapshot.sampleCount}</span>
              <span className="analytics-pill">stations: {crossComplaintSnapshot.stationRows.length}</span>
              <span className="analytics-pill">machines: {crossComplaintSnapshot.machineRows.length}</span>
              <span className="analytics-pill">features: {crossComplaintSnapshot.featureRows.length}</span>
              {Object.entries(crossComplaintSnapshot.metrics || {}).slice(0, 4).map(([k, v]) => (
                <span key={k} className="analytics-pill">{k}: {Number(v || 0)}</span>
              ))}
            </div>
            {(crossComplaintSnapshot.stationRows.length > 0 || crossComplaintSnapshot.machineRows.length > 0) ? (
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 10 }}>
                {crossComplaintSnapshot.stationRows.length > 0 ? (
                  <div>
                    <div className="analytics-artifacts-hint" style={{ marginBottom: 6 }}>站點分布 Top</div>
                    <div className="analytics-chart-wrap" style={{ height: 220, marginTop: 0 }}>
                      <ResponsiveContainer>
                        <BarChart data={crossComplaintSnapshot.stationRows.slice(0, 8)}>
                          <CartesianGrid strokeDasharray="3 3" />
                          <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                          <YAxis allowDecimals={false} />
                          <Tooltip />
                          <Bar dataKey="count" fill="#10b981" />
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                  </div>
                ) : null}
                {crossComplaintSnapshot.machineRows.length > 0 ? (
                  <div>
                    <div className="analytics-artifacts-hint" style={{ marginBottom: 6 }}>機台分布 Top</div>
                    <div className="analytics-chart-wrap" style={{ height: 220, marginTop: 0 }}>
                      <ResponsiveContainer>
                        <BarChart data={crossComplaintSnapshot.machineRows.slice(0, 8)}>
                          <CartesianGrid strokeDasharray="3 3" />
                          <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                          <YAxis allowDecimals={false} />
                          <Tooltip />
                          <Bar dataKey="count" fill="#2563eb" />
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                  </div>
                ) : null}
              </div>
            ) : (
              <div className="analytics-artifacts-hint" style={{ marginBottom: 8 }}>
                目前 view 沒有可聚合的站點/機台欄位（可切換至 Events 視圖）。
              </div>
            )}
            {crossComplaintSnapshot.featureRows.length > 0 ? (
              <div style={{ marginTop: 8 }}>
                <div className="analytics-artifacts-hint" style={{ marginBottom: 6 }}>Top Features</div>
                <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                  {crossComplaintSnapshot.featureRows.slice(0, 12).map((x) => (
                    <span key={x.name} className="analytics-pill">{x.name}: {x.count}</span>
                  ))}
                </div>
              </div>
            ) : null}
            {(complaintReportSnapshot.llm || complaintReportSnapshot.rag) ? (
              <div style={{ marginTop: 10 }}>
                <div className="analytics-artifacts-hint" style={{ marginBottom: 6 }}>改善報告摘要（complaint-analysis.report_payload）</div>
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                  {complaintReportSnapshot.llm ? (
                    <>
                      <span className="analytics-pill">llm.samples: {Number(complaintReportSnapshot.llm.sample_count || 0)}</span>
                      {Object.entries(complaintReportSnapshot.llm.metrics || {}).slice(0, 4).map(([k, v]) => (
                        <span key={`llm-${k}`} className="analytics-pill">llm.{k}: {Number(v || 0)}</span>
                      ))}
                    </>
                  ) : null}
                  {complaintReportSnapshot.rag ? (
                    <>
                      <span className="analytics-pill">rag.samples: {Number(complaintReportSnapshot.rag.sample_count || 0)}</span>
                      {Object.entries(complaintReportSnapshot.rag.metrics || {}).slice(0, 4).map(([k, v]) => (
                        <span key={`rag-${k}`} className="analytics-pill">rag.{k}: {Number(v || 0)}</span>
                      ))}
                    </>
                  ) : null}
                </div>
              </div>
            ) : null}
            {(complaintReportComposition.summary.length > 0 ||
              complaintReportComposition.suggestions.length > 0 ||
              complaintReportComposition.evidence_refs.length > 0) ? (
              <div style={{ marginTop: 10, border: '1px solid #dbeafe', background: '#eff6ff', borderRadius: 8, padding: 10 }}>
                <div style={{ fontWeight: 700, marginBottom: 6 }}>改善報告（標準化）</div>
                {complaintReportComposition.summary.length > 0 ? (
                  <div style={{ marginBottom: 6 }}>
                    <div className="analytics-artifacts-hint" style={{ marginBottom: 4 }}>Summary</div>
                    <ul style={{ margin: 0, paddingLeft: 18 }}>
                      {complaintReportComposition.summary.slice(0, 5).map((x, idx) => (
                        <li key={`s-${idx}`}>{x}</li>
                      ))}
                    </ul>
                  </div>
                ) : null}
                {complaintReportComposition.suggestions.length > 0 ? (
                  <div style={{ marginBottom: 6 }}>
                    <div className="analytics-artifacts-hint" style={{ marginBottom: 4 }}>Suggestions</div>
                    <ul style={{ margin: 0, paddingLeft: 18 }}>
                      {complaintReportComposition.suggestions.slice(0, 5).map((x, idx) => (
                        <li key={`g-${idx}`}>{x}</li>
                      ))}
                    </ul>
                  </div>
                ) : null}
                {complaintReportComposition.evidence_refs.length > 0 ? (
                  <div>
                    <div className="analytics-artifacts-hint" style={{ marginBottom: 4 }}>Evidence refs</div>
                    <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                      {complaintReportComposition.evidence_refs.slice(0, 10).map((x, idx) => (
                        <span key={`e-${idx}`} className="analytics-pill">
                          {x.requested_id ? `${x.requested_id} -> ` : ''}{x.token}
                        </span>
                      ))}
                    </div>
                  </div>
                ) : null}
              </div>
            ) : null}
          </div>
        ) : null}

        {(inputMatchSummary.length > 0 || unmatchedDiagnostics.length > 0) ? (
          <div style={{ marginTop: 10, border: '1px solid #dbeafe', background: '#f8fbff', borderRadius: 8, padding: 10 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, alignItems: 'center', marginBottom: 6 }}>
              <div style={{ fontWeight: 700 }}>診斷摘要</div>
              <button
                type="button"
                className="btn-secondary"
                onClick={() => setShowDiagnosticsPanel((v) => !v)}
              >
                {showDiagnosticsPanel ? '收合診斷' : '展開診斷'}
              </button>
            </div>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              <span className="analytics-pill">輸入: {inputMatchSummary.length}</span>
              <span className="analytics-pill">未命中: {unmatchedDiagnostics.length}</span>
              <span className="analytics-pill">可關聯: {inputMatchSummary.filter((x) => x.matchedTokens.length > 0).length}</span>
            </div>
            {mappingNotice ? (
              <div className="analytics-artifacts-hint" style={{ marginTop: 6 }}>
                {mappingNotice}
              </div>
            ) : null}
            {showDiagnosticsPanel ? (
              <div style={{ marginTop: 8, display: 'flex', flexDirection: 'column', gap: 8 }}>
                {complaintAnalysis ? (
                  <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                    <span className="analytics-pill">scope_id: {complaintAnalysis.analysis_scope_id}</span>
                    <span className="analytics-pill">scope_tokens: {Number(complaintAnalysis.scope_tokens_count || 0)}</span>
                    <span className="analytics-pill">
                      scope_lock: {complaintAnalysis.consistency?.snapshot_scope_locked && complaintAnalysis.consistency?.report_scope_locked ? 'yes' : 'no'}
                    </span>
                    <span className="analytics-pill">t.resolve: {Number(complaintAnalysis.timing?.resolve_ms || 0)}ms</span>
                    <span className="analytics-pill">t.snapshot: {Number(complaintAnalysis.timing?.snapshot_ms || 0)}ms</span>
                    <span className="analytics-pill">t.report: {Number(complaintAnalysis.timing?.report_ms || 0)}ms</span>
                    <span className="analytics-pill">t.total: {Number(complaintAnalysis.timing?.total_ms || 0)}ms</span>
                  </div>
                ) : null}
                {inputMatchSummary.slice(0, 20).map((x) => (
                  <div key={x.productId} style={{ borderTop: '1px dashed #bfdbfe', paddingTop: 6 }}>
                    <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
                      <code>{x.productId}</code>
                      <span className="analytics-pill">{x.matchedStage || '-'}</span>
                      <span className="analytics-pill">hit:{x.hitCount}</span>
                    </div>
                    {x.matchedTokens.length > 0 ? (
                      <div style={{ marginTop: 4, display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                        {x.matchedTokens.slice(0, 5).map((tk) => (
                          <span key={`${x.productId}:${tk}`} className="analytics-pill">{tk}</span>
                        ))}
                        <button
                          type="button"
                          className="btn-secondary"
                          onClick={() => jumpToMappedDetail(x.matchedTokens)}
                        >
                          關聯查詢
                        </button>
                      </div>
                    ) : (
                      <div className="analytics-artifacts-hint" style={{ marginTop: 4 }}>
                        {x.reasonCode ? `${x.reasonCode}${x.reasonMessage ? ` - ${x.reasonMessage}` : ''}` : '無可用 token'}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            ) : null}
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
            {eventTrendData.length > 0 ? (
              <div className="analytics-chart-wrap" style={{ height: 220, marginTop: 0, marginBottom: 8 }}>
                <ResponsiveContainer>
                  <BarChart data={eventTrendData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="day" tick={{ fontSize: 11 }} />
                    <YAxis allowDecimals={false} />
                    <Tooltip />
                    <Legend />
                    <Bar dataKey="events" name="Events" fill="#2563eb" />
                    <Bar dataKey="iqr" name="IQR Events" fill="#ef4444" />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            ) : null}
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
                  {aggCoreChartData.length > 0 ? (
                    <div className="analytics-chart-wrap" style={{ height: 320, marginTop: 0, marginBottom: 10 }}>
                      <ResponsiveContainer>
                        <BarChart data={aggCoreChartData} layout="vertical" margin={{ left: 30, right: 12 }}>
                          <CartesianGrid strokeDasharray="3 3" />
                          <XAxis type="number" allowDecimals={false} />
                          <YAxis type="category" dataKey="feature" width={180} tick={{ fontSize: 11 }} />
                          <Tooltip />
                          <Legend />
                          <Bar dataKey="IQR" stackId="a" fill="#ef4444" />
                          <Bar dataKey="T2" stackId="a" fill="#2563eb" />
                          <Bar dataKey="SPE" stackId="a" fill="#0ea5e9" />
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                  ) : null}
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
            {weightedScatterData.length > 0 ? (
              <div className="register-block">
                <div className="register-title" style={{ marginBottom: 8 }}>Risk Map（x_T2 vs x_SPE）</div>
                <div className="analytics-chart-wrap" style={{ height: 320, marginTop: 0 }}>
                  <ResponsiveContainer>
                    <ScatterChart margin={{ top: 8, right: 16, left: 8, bottom: 8 }}>
                      <CartesianGrid />
                      <XAxis type="number" dataKey="x" name="x_T2" />
                      <YAxis type="number" dataKey="y" name="x_SPE" />
                      <ZAxis type="number" dataKey="z" range={[40, 220]} />
                      <Tooltip
                        cursor={{ strokeDasharray: '3 3' }}
                        formatter={(value: any, name: any) => [value, name === 'x' ? 'x_T2' : name === 'y' ? 'x_SPE' : name]}
                        labelFormatter={(_, payload) => {
                          const row = payload?.[0]?.payload as any
                          return row?.id ? `ID: ${row.id}` : ''
                        }}
                      />
                      <Scatter data={weightedScatterData} fill="#2563eb" />
                    </ScatterChart>
                  </ResponsiveContainer>
                </div>
              </div>
            ) : null}
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
          <div className="muted">{emptyHint}</div>
          {productIdFilters.length > 0 ? (
            <div className="muted" style={{ marginTop: 6 }}>
              已套用產品編號過濾 {productIdFilters.length} 筆；目前視圖命中 {currentFilteredCount} 筆。
            </div>
          ) : null}
        </div>
      )}
    </div>
  )
}

export type { ViewKey }
