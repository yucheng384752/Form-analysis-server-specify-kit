import { useCallback, useEffect, useMemo, useRef, useState, type KeyboardEventHandler } from 'react'
import { useTranslation } from 'react-i18next'
import type { DateRange } from 'react-day-picker'
import { getTenantId } from '../services/tenant'
import { getTenantLabelById, writeTenantMap } from '../services/tenantMap'
import { clampCustomRange, normalizeDayPickerRange } from '../utils/analyticsDateRange'
import { ArtifactsView, type ViewKey } from '../components/analytics/ArtifactsView'

import type { TenantRow } from '../types/common'
import type {
  AnalysisResult,
  QueryRecordLite,
  QueryResponseLite,
  RangeMode,
  StationSelection,
  TraceabilityData,
  ParetoPoint,
} from './analytics/types'
import {
  PARETO_ENABLED_DAILY,
  PARETO_TOP_N,
  PARETO_CUM_THRESHOLD,
  PARETO_MIN_COUNT,
  PARETO_SHOW_ZERO,
  PARETO_SOURCE_NG,
  PARETO_SOURCE_FEATURE,
} from './analytics/types'
import {
  extractProduceNosFromTrace,
  parseProductIds,
  toYmd,
  getModeBounds,
  parseCounts,
  isPlainObject,
  normalizeAnalysisResult,
  pickOverallNode,
  pct,
  round3,
  toCumsumSeries,
  buildParetoSeries,
} from './analytics/utils'
import { DateRangeSection } from './analytics/DateRangeSection'
import { NgModeSection } from './analytics/NgModeSection'
import { AnalysisResultsSection } from './analytics/AnalysisResultsSection'

import './../styles/analytics-page.css'
import 'react-day-picker/dist/style.css'

import type { DataType } from '../types/common'

export function AnalyticsPage() {
  const { t } = useTranslation()
  const [startDate, setStartDate] = useState(() => {
    const anchor = new Date()
    const bounds = getModeBounds('month', anchor)
    return toYmd(bounds.start)
  })
  const [endDate, setEndDate] = useState(() => {
    const anchor = new Date()
    const bounds = getModeBounds('month', anchor)
    return toYmd(bounds.end)
  })
  const [rangeMode, setRangeMode] = useState<RangeMode>('month')
  const [anchorDate, setAnchorDate] = useState<Date | undefined>(() => new Date())
  const [customRange, setCustomRange] = useState<DateRange | undefined>(undefined)
  const [isCompactCalendar, setIsCompactCalendar] = useState(() => {
    if (typeof window === 'undefined') return false
    return window.matchMedia('(max-width: 860px)').matches
  })
  const [productIdDraft, setProductIdDraft] = useState('')
  const [productIdCommitted, setProductIdCommitted] = useState('')
  const [ran, setRan] = useState(false)
  const [analysisResult, setAnalysisResult] = useState<AnalysisResult | null>(null)
  const [parseError, setParseError] = useState<string>('')
  const [isLoading, setIsLoading] = useState(false)
  const [stations, setStations] = useState<StationSelection>({ p2: true, p3: false, all: false })
  const [tenantMapVersion, setTenantMapVersion] = useState(0)

  const [traceData, setTraceData] = useState<TraceabilityData | null>(null)

  const [ngMode, setNgMode] = useState(false)
  const [ngRecords, setNgRecords] = useState<QueryRecordLite[]>([])
  const [ngLoading, setNgLoading] = useState(false)
  const [ngError, setNgError] = useState('')
  const [ngWinderNumber, setNgWinderNumber] = useState<number | null>(null)

  const [extractionData, setExtractionData] = useState<{
    final_raw_score: Record<string, number>
    boundary_count: Record<string, number>
    spe_score: Record<string, number>
    t2_score: Record<string, number>
  } | null>(null)
  const [extractionLoading, setExtractionLoading] = useState(false)

  const [artifactView, setArtifactView] = useState<ViewKey>('events')
  const [analysisChartMode, setAnalysisChartMode] = useState<'heatmap' | 'bar'>('heatmap')

  const artifactsSectionRef = useRef<HTMLDivElement | null>(null)

  const productIds = useMemo(() => parseProductIds(productIdCommitted), [productIdCommitted])
  const traceProduceNos = useMemo(() => extractProduceNosFromTrace(traceData), [traceData])
  const artifactProductFilters = useMemo(() => {
    const merged = [...productIds, ...traceProduceNos]
    const uniq: string[] = []
    const seen = new Set<string>()
    for (const x of merged) {
      const s = String(x || '').trim()
      if (!s) continue
      const k = s.toLowerCase()
      if (seen.has(k)) continue
      seen.add(k)
      uniq.push(s)
      if (uniq.length >= 50) break
    }
    return uniq
  }, [productIds, traceProduceNos])
  const productIdMode = productIds.length > 0
  const artifactsMode = false

  const ngFeaturePctEntries = useMemo(() => {
    const aggregate = new Map<string, { sum: number; count: number }>()
    for (const r of ngRecords) {
      const additional = r.additional_data as any
      const featurePctObjRaw =
        (additional && typeof additional === 'object'
          ? (additional.feature_pct ??
              additional.featurePct ??
              additional.feature_importance?.feature_pct ??
              additional.featureImportance?.feature_pct)
          : null) as unknown

      if (!isPlainObject(featurePctObjRaw)) continue
      for (const [name, v] of Object.entries(featurePctObjRaw)) {
        if (typeof v !== 'number' || !Number.isFinite(v)) continue
        const prev = aggregate.get(name)
        if (prev) prev.sum += v, prev.count += 1
        else aggregate.set(name, { sum: v, count: 1 })
      }
    }

    return Array.from(aggregate.entries())
      .map(([name, { sum, count }]) => ({ name, pct: count ? sum / count : 0 }))
      .filter((x) => Number.isFinite(x.pct) && x.pct > 0)
      .sort((a, b) => b.pct - a.pct)
  }, [ngRecords])

  const ngFeaturePctChartData = useMemo(() => {
    const top = ngFeaturePctEntries.slice(0, 10)
    return toCumsumSeries(top)
  }, [ngFeaturePctEntries])

  const ngFeaturePctChartHeight = useMemo(() => {
    const count = Math.min(10, ngFeaturePctEntries.length)
    return Math.max(360, 220 + count * 4)
  }, [ngFeaturePctEntries.length])

  const autoRunArmedRef = useRef(false)
  const autoRunTimerRef = useRef<number | null>(null)
  const lastAutoRunKeyRef = useRef<string>('')
  const pendingAutoRunKeyRef = useRef<string>('')
  const analyzeRequestIdRef = useRef(0)

  const tenantId = useMemo(() => getTenantId(), [])
  const tenantLabelRaw = useMemo(() => getTenantLabelById(tenantId), [tenantId, tenantMapVersion])
  const tenantLabel = useMemo(() => {
    const raw = String(tenantLabelRaw || '').trim()
    if (!raw) return ''
    if (raw.toLowerCase() === 'default') return '預設'
    return raw
  }, [tenantLabelRaw])

  const buildTenantHeaders = useCallback(() => {
    if (!tenantId) return {}
    return { 'X-Tenant-Id': tenantId }
  }, [tenantId])

  useEffect(() => {
    const pid = productIds[0]?.trim() ?? ''
    if (!pid) {
      setTraceData(null)
      return
    }

    const controller = new AbortController()
    const headers = buildTenantHeaders()

    void (async () => {
      try {
        const res = await fetch(`/api/traceability/product/${encodeURIComponent(pid)}`, {
          headers,
          signal: controller.signal,
        })
        if (!res.ok) {
          throw new Error(t('analytics.traceabilityFetchFailed'))
        }
        const json = (await res.json()) as TraceabilityData
        setTraceData(json)
      } catch (err: any) {
        if (controller.signal.aborted) return
        setTraceData(null)
      }
    })()

    return () => controller.abort()
  }, [buildTenantHeaders, productIds, t])

  const commitProductId = useCallback(() => {
    const next = productIdDraft.trim()
    if (next === productIdCommitted) return
    autoRunArmedRef.current = parseProductIds(next).length === 0
    setProductIdCommitted(next)
  }, [productIdCommitted, productIdDraft])

  useEffect(() => {
    if (!tenantId) return

    void (async () => {
      try {
        const res = await fetch('/api/tenants')
        if (!res.ok) return
        const tenants = (await res.json()) as TenantRow[]
        if (!Array.isArray(tenants)) return

        writeTenantMap(tenants)
        setTenantMapVersion((v) => v + 1)
      } catch {
        // ignore
      }
    })()
  }, [tenantId])

  useEffect(() => {
    if (!productIdMode) return
    setStations({ p2: true, p3: true, all: false })
  }, [productIdMode])

  useEffect(() => {
    if (!productIdMode) return
    setAnalysisChartMode('bar')
  }, [productIdMode])

  useEffect(() => {
    if (typeof window === 'undefined') return
    const mq = window.matchMedia('(max-width: 860px)')
    const update = () => setIsCompactCalendar(mq.matches)
    update()

    if (typeof mq.addEventListener === 'function') {
      mq.addEventListener('change', update)
      return () => mq.removeEventListener('change', update)
    }

    // Safari/older browsers
    mq.addListener(update)
    return () => mq.removeListener(update)
  }, [])

  const overall = useMemo(() => {
    const result = analysisResult
    if (!result) return { ok: 0, ng: 0, total: 0 }

    const best = pickOverallNode(result)
    if (!best) return { ok: 0, ng: 0, total: 0 }

    return parseCounts(best.node)
  }, [analysisResult])

  const pieData = useMemo(() => {
    return [
      { name: `OK ${pct(overall.ok, overall.total)}%`, value: overall.ok, kind: 'OK' as const },
      { name: `NG ${pct(overall.ng, overall.total)}%`, value: overall.ng, kind: 'NG' as const },
    ]
  }, [overall.ok, overall.ng, overall.total])

  const applyComputedRange = (start: Date, end: Date) => {
    setStartDate(toYmd(start))
    setEndDate(toYmd(end))
  }

  const applyAnchorForMode = (mode: Exclude<RangeMode, 'custom'>, date: Date | undefined) => {
    autoRunArmedRef.current = true
    setAnchorDate(date)
    if (!date) {
      setStartDate('')
      setEndDate('')
      return
    }
    const bounds = getModeBounds(mode, date)
    applyComputedRange(bounds.start, bounds.end)
  }

  const clearDateFilter = () => {
    autoRunArmedRef.current = false
    setStartDate('')
    setEndDate('')
    setAnchorDate(undefined)
    setCustomRange(undefined)
    setAnalysisResult(null)
    setRan(false)
    setNgMode(false)
    setNgRecords([])
    setNgError('')
    setNgWinderNumber(null)
  }

  const handleSelectCustomRange = (range: DateRange | undefined) => {
    autoRunArmedRef.current = true

    const normalized = normalizeDayPickerRange(range)
    setCustomRange(normalized)

    if (!normalized?.from) {
      setStartDate('')
      setEndDate('')
      return
    }

    const from = normalized.from
    const to = normalized.to ?? normalized.from

    if (from.getTime() === to.getTime()) {
      applyComputedRange(from, to)
      return
    }

    const clamped = clampCustomRange(from, to)
    applyComputedRange(clamped.start, clamped.end)
  }

  const handleRangeModeChange = (mode: RangeMode) => {
    autoRunArmedRef.current = true
    setRangeMode(mode)

    if (mode === 'custom') {
      setCustomRange((prev) => {
        if (prev?.from && prev.to) return prev
        if (anchorDate) return { from: anchorDate, to: anchorDate }
        return undefined
      })
      return
    }

    setCustomRange(undefined)
    if (!anchorDate && !startDate && !endDate) {
      return
    }
    const nextAnchor = anchorDate ?? new Date()
    applyAnchorForMode(mode, nextAnchor)
  }

  const handleToggleStation = (key: keyof StationSelection) => {
    if (productIdMode) return
    autoRunArmedRef.current = true
    setStations((prev) => {
      const next = { ...prev }
      next[key] = !prev[key]
      if (key === 'all' && next.all) {
        next.p2 = true
        next.p3 = true
      }
      if ((key === 'p2' || key === 'p3') && (!next.p2 || !next.p3)) {
        next.all = false
      }
      return next
    })
  }

  const categoryCards = useMemo(() => {
    const result = analysisResult
    if (!result) return []
    const categories: Array<{
      category: string
      items: Array<{ key: string; label: string; ok: number; ng: number; total: number }>
    }> = []
    for (const [category, bucket] of Object.entries(result)) {
      const keys = Object.keys(bucket)
      if (keys.length === 0) continue
      const sortedKeys = keys.slice().sort((a, b) => {
        const na = Number(a)
        const nb = Number(b)
        const isNumA = Number.isFinite(na)
        const isNumB = Number.isFinite(nb)
        if (isNumA && isNumB) return na - nb
        return a.localeCompare(b)
      })
      const items = sortedKeys.map((k) => ({
        key: k,
        label: String(bucket[k]?.label ?? k),
        ...parseCounts(bucket[k]),
      }))
      categories.push({ category, items })
    }
    return categories
  }, [analysisResult])

  const analysisHeatmapRows = useMemo(() => {
    const rows: Array<{
      category: string
      key: string
      ok: number
      ng: number
      total: number
      ngRate: number
    }> = []
    for (const cat of categoryCards) {
      for (const item of cat.items) {
        rows.push({
          category: cat.category,
          key: item.key,
          ok: item.ok,
          ng: item.ng,
          total: item.total,
          ngRate: item.total > 0 ? item.ng / item.total : 0,
        })
      }
    }
    rows.sort((a, b) => b.ngRate - a.ngRate || b.total - a.total)
    return rows.slice(0, 80)
  }, [categoryCards])

  const winderChartData = useMemo(() => {
    const winderCat = categoryCards.find((cat) => /winder/i.test(cat.category))
    if (!winderCat) return []
    const sorted = winderCat.items
      .map((item) => ({ name: item.label || item.key, count: item.ng, total: item.total }))
      .filter((d) => d.name)
      .sort((a, b) => b.count - a.count)
    const totalNg = sorted.reduce((s, d) => s + d.count, 0)
    let cum = 0
    return sorted.map((d) => {
      cum += d.count
      return { ...d, cumPct: totalNg > 0 ? round3((cum / totalNg) * 100) : 0 }
    })
  }, [categoryCards])

  const ngParetoData = useMemo(() => {
    if (!PARETO_ENABLED_DAILY || !PARETO_SOURCE_NG || !analysisResult) return [] as ParetoPoint[]
    const candidates = ['P2.NG_code', 'NG_code', 'P3.NG_code']
    let bucket: Record<string, any> | null = null
    for (const key of candidates) {
      const entry = analysisResult[key]
      if (entry && typeof entry === 'object') {
        bucket = entry
        break
      }
    }
    if (!bucket) return []
    const items = Object.entries(bucket)
      .map(([name, node]) => ({
        name,
        value: Number(node?.count_0 ?? 0) || 0,
      }))
    return buildParetoSeries(items, {
      topN: PARETO_TOP_N,
      cumThreshold: PARETO_CUM_THRESHOLD,
      minValue: PARETO_MIN_COUNT,
      showZero: PARETO_SHOW_ZERO,
    })
  }, [analysisResult])

  const featureParetoData = useMemo(() => {
    if (!PARETO_ENABLED_DAILY || !PARETO_SOURCE_FEATURE || !extractionData) return [] as ParetoPoint[]
    const items = Object.entries(extractionData.final_raw_score || {}).map(
      ([name, value]) => ({ name, value: Number(value) || 0 })
    )
    return buildParetoSeries(items, {
      topN: PARETO_TOP_N,
      cumThreshold: PARETO_CUM_THRESHOLD,
      minValue: PARETO_MIN_COUNT,
      showZero: PARETO_SHOW_ZERO,
    })
  }, [extractionData])

  const heatColor = useCallback((rate: number) => {
    const r = Math.max(0, Math.min(1, Number.isFinite(rate) ? rate : 0))
    const lightness = 96 - r * 42
    return `hsl(0 82% ${lightness}%)`
  }, [])

  const computeAutoRunKey = useCallback(() => {
    return JSON.stringify({ startDate, endDate, stations })
  }, [startDate, endDate, stations])

  const handleRun = useCallback((_opts?: { productIdOverride?: string }) => {
    void (async () => {
      setParseError('')
      setIsLoading(true)
      setNgMode(false)
      setNgRecords([])
      setNgError('')

      const currentRequestId = ++analyzeRequestIdRef.current

      try {
        const chosenStations: Array<'P2' | 'P3' | 'ALL'> = []
        if (stations.all) {
          chosenStations.push('ALL')
        } else {
          if (stations.p2) chosenStations.push('P2')
          if (stations.p3) chosenStations.push('P3')
        }

        if (chosenStations.length === 0) {
          setParseError(t('analytics.stationPickError'))
          return
        }

        const overrideInput = String(_opts?.productIdOverride ?? '').trim()
        const committedInput = productIdCommitted.trim()
        const productInput = overrideInput || committedInput
        const effectiveProductIds = parseProductIds(productInput)
        const hasProductIds = effectiveProductIds.length > 0
        console.log('[Analytics] product_id count:', effectiveProductIds.length)

        const requestAnalyze = async (stationsParam: Array<'P2' | 'P3' | 'ALL'>): Promise<AnalysisResult | null> => {
          console.log('[Analytics] Sending request:', { requestId: currentRequestId, startDate, endDate, stations: stationsParam })
          const res = await fetch('/api/v2/analytics/analyze', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', ...buildTenantHeaders() },
            body: JSON.stringify({
              start_date: hasProductIds ? null : startDate || null,
              end_date: hasProductIds ? null : endDate || null,
              product_id: null,
              product_ids: hasProductIds ? effectiveProductIds : [],
              stations: stationsParam,
            }),
          })

          if (!res.ok) {
            const text = await res.text().catch(() => '')
            throw new Error(text || t('analytics.analyzeRequestFailed', { status: res.status }))
          }

          const json = (await res.json()) as Record<string, unknown>
          console.log('[Analytics] response keys:', Object.keys(json || {}))
          const p2Keys = Object.keys(json || {}).filter((key) => key.startsWith('P2.'))
          console.log('[Analytics] P2 keys (raw):', p2Keys)
          const normalized = normalizeAnalysisResult(json)
          const normalizedP2 = normalized ? Object.keys(normalized).filter((key) => key.startsWith('P2.')) : []
          console.log('[Analytics] P2 keys (normalized):', normalizedP2)
          return normalized
        }

        const normalized = await requestAnalyze(hasProductIds ? ['P2', 'P3'] : chosenStations)

        if (currentRequestId !== analyzeRequestIdRef.current) {
          console.log('[Analytics] Ignoring stale response, requestId:', currentRequestId, 'current:', analyzeRequestIdRef.current)
          return
        }

        if (!normalized) {
          setParseError(t('analytics.notFound'))
          setAnalysisResult(null)
          setRan(false)
          return
        }

        const hasAnyData = Object.values(normalized).some((bucket) =>
          Object.values(bucket).some((node) => (Number((node as any)?.total_count ?? 0) || 0) > 0),
        )

        if (!hasAnyData) {
          setParseError(t('analytics.notFound'))
          setAnalysisResult(null)
          setRan(false)
          return
        }

        setAnalysisResult(normalized)
        setRan(true)
      } catch (e) {
        setParseError(t('analytics.analyzeFailedWithDetail', { detail: String(e) }))
        setAnalysisResult(null)
        setRan(false)
      } finally {
        setIsLoading(false)
      }
    })()
  }, [buildTenantHeaders, endDate, productIdCommitted, startDate, stations, t])

  const runNow = useCallback(() => {
    const overrideProductId = productIdDraft.trim()
    const nextIds = parseProductIds(overrideProductId)
    setProductIdCommitted(overrideProductId)

    if (nextIds.length > 0) {
      autoRunArmedRef.current = false
      handleRun({ productIdOverride: overrideProductId })
      return
    }

    autoRunArmedRef.current = true

    pendingAutoRunKeyRef.current = ''
    lastAutoRunKeyRef.current = JSON.stringify({ startDate, endDate, stations })
    if (autoRunTimerRef.current) {
      window.clearTimeout(autoRunTimerRef.current)
      autoRunTimerRef.current = null
    }
    handleRun({ productIdOverride: overrideProductId })
  }, [endDate, handleRun, productIdDraft, startDate, stations])

  const isNgLikeValue = useCallback((value: unknown): boolean => {
    if (value === null || value === undefined) return false
    if (typeof value === 'number') return value === 0
    const s = String(value).trim()
    if (!s) return false
    const n = Number(s)
    return Number.isFinite(n) && n === 0
  }, [])

  const normalizeRowKey = useCallback((key: string): string => {
    return key.replace(/\s+/g, ' ').trim().toLowerCase()
  }, [])

  const rowHasNg = useCallback((row: unknown, keys: string[]): boolean => {
    if (!row || typeof row !== 'object' || Array.isArray(row)) return false
    const obj = row as Record<string, unknown>

    const normalizedEntries = Object.entries(obj).map(([k, v]) => [normalizeRowKey(k), v] as const)
    const wanted = keys.map((k) => normalizeRowKey(k))

    for (const wantKey of wanted) {
      const found = normalizedEntries.find(([k]) => k === wantKey)
      if (found && isNgLikeValue(found[1])) return true
    }
    return false
  }, [isNgLikeValue, normalizeRowKey])

  const formatCellValue = useCallback((value: unknown): string => {
    if (value === null || value === undefined) return '-'
    if (typeof value === 'string') return value.trim() || '-'
    if (typeof value === 'number' || typeof value === 'boolean') return String(value)
    try {
      return JSON.stringify(value)
    } catch {
      return String(value)
    }
  }, [])

  const getNgKeyCandidates = useCallback((record: QueryRecordLite): string[] => {
    if (record.data_type === 'P2') {
      return [
        'Striped Results',
        'Striped results',
        'striped results',
        'striped result',
        '分條結果',
      ]
    }
    return []
  }, [])

  const parseWinderCategoryKey = useCallback((key: unknown): number | null => {
    const s = String(key ?? '').trim()
    if (!s) return null
    const matched = s.match(/-?\d+/)
    if (!matched) return null
    const n = Number.parseInt(matched[0], 10)
    return Number.isFinite(n) ? n : null
  }, [])

  const sortRowsNgFirst = useCallback((rows: unknown[], keys: string[]) => {
    if (!Array.isArray(rows) || rows.length <= 1) return rows
    return rows
      .map((row, idx) => ({ row, idx }))
      .sort((a, b) => {
        const aNg = rowHasNg(a.row, keys)
        const bNg = rowHasNg(b.row, keys)
        if (aNg !== bNg) return aNg ? -1 : 1
        return a.idx - b.idx
      })
      .map((x) => x.row)
  }, [rowHasNg])

  const recordHasNg = useCallback((record: QueryRecordLite): boolean => {
    const additional = record.additional_data as any
    const rows = Array.isArray(additional?.rows) ? (additional.rows as unknown[]) : []
    if (record.data_type === 'P2') {
      return rows.some((r) =>
        rowHasNg(r, [
          'Striped Results',
          'Striped results',
          'striped results',
          'striped result',
          '分條結果',
        ]),
      )
    }
    return false
  }, [rowHasNg])

  const fetchNgRecords = useCallback(async (opts?: { winderNumber?: number | null }) => {
    setNgError('')
    setNgLoading(true)
    try {
      const wantedTypes: DataType[] = []
      if (stations.all) {
        wantedTypes.push('P2', 'P3')
      } else {
        if (stations.p2) wantedTypes.push('P2')
        if (stations.p3) wantedTypes.push('P3')
      }

      if (wantedTypes.length === 0) {
        setNgError(t('analytics.stationPickError'))
        setNgLoading(false)
        return
      }

      const results = await Promise.all(
        wantedTypes.map(async (dt) => {
          const baseFilters: Array<{ field: string; op: string; value: any }> = []

          if (startDate && endDate) {
            if (startDate === endDate) {
              baseFilters.push({ field: 'production_date', op: 'eq', value: startDate })
            } else {
              baseFilters.push({ field: 'production_date', op: 'between', value: [startDate, endDate] })
            }
          } else if (startDate) {
            baseFilters.push({ field: 'production_date', op: 'gte', value: startDate })
          } else if (endDate) {
            baseFilters.push({ field: 'production_date', op: 'lte', value: endDate })
          }

          if (dt === 'P2' && opts?.winderNumber !== undefined && opts.winderNumber !== null) {
            baseFilters.push({ field: 'winder_number', op: 'eq', value: String(opts.winderNumber) })
          }

          const queryDynamic = async (filters: Array<{ field: string; op: string; value: any }>) => {
            const res = await fetch(`/api/v2/query/records/dynamic`, {
              method: 'POST',
              headers: { ...buildTenantHeaders(), 'Content-Type': 'application/json' },
              body: JSON.stringify({
                data_type: dt,
                filters,
                page: 1,
                page_size: 200,
              }),
            })
            if (!res.ok) {
              const text = await res.text().catch(() => '')
              throw new Error(text || `HTTP ${res.status}`)
            }
            return (await res.json()) as QueryResponseLite
          }

          if (dt === 'P2') {
            try {
              return await queryDynamic([
                ...baseFilters,
                { field: 'slitting_result', op: 'eq', value: 0 },
              ])
            } catch (e) {
              const msg = String(e)
              const unsupportedSlittingResult =
                msg.includes('Unsupported field(s)') && msg.includes('slitting_result')
              const invalidSlittingResultField = msg.includes('Invalid field: slitting_result')
              const invalidSlittingResultOp = msg.includes('Invalid operator for slitting_result')
              if (
                !unsupportedSlittingResult &&
                !invalidSlittingResultField &&
                !invalidSlittingResultOp
              ) {
                throw e
              }
              return await queryDynamic([
                ...baseFilters,
                { field: 'row_data.Striped Results', op: 'eq', value: 0 },
              ])
            }
          } else if (dt === 'P3') {
            try {
              return await queryDynamic([
                ...baseFilters,
                { field: 'row_data.Finish', op: 'eq', value: 0 },
              ])
            } catch (e) {
              const msg = String(e)
              if (msg.includes('Invalid') || msg.includes('Unsupported')) {
                return await queryDynamic([
                  ...baseFilters,
                  { field: 'row_data.finish', op: 'eq', value: 0 },
                ])
              }
              throw e
            }
          }

          return { records: [], total_count: 0, page: 1, page_size: 200 } as QueryResponseLite
        }),
      )

      const merged = results.flatMap((r) => (Array.isArray(r.records) ? r.records : []))
      const onlyNg = merged.filter(recordHasNg)
      setNgRecords(onlyNg)
      if (onlyNg.length === 0) {
        setNgError(t('analytics.notFound'))
      }
    } catch (e) {
      setNgError(String(e))
      setNgRecords([])
    } finally {
      setNgLoading(false)
    }
  }, [buildTenantHeaders, endDate, recordHasNg, startDate, stations, t])

  const fetchExtractionAnalysis = useCallback(async () => {
    setExtractionLoading(true)
    setExtractionData(null)
    try {
      const station = stations.p2 || stations.all ? 'P2' : stations.p3 ? 'P3' : 'P2'
      const res = await fetch('/api/v2/analytics/extraction-analysis', {
        method: 'POST',
        headers: { ...buildTenantHeaders(), 'Content-Type': 'application/json' },
        body: JSON.stringify({
          start_date: startDate || undefined,
          end_date: endDate || undefined,
          station,
        }),
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = await res.json()
      if (data.final_raw_score && Object.keys(data.final_raw_score).length > 0) {
        setExtractionData({
          final_raw_score: data.final_raw_score,
          boundary_count: data.boundary_count ?? {},
          spe_score: data.spe_score ?? {},
          t2_score: data.t2_score ?? {},
        })
      }
    } catch (e) {
      console.warn('Extraction analysis failed:', e)
    } finally {
      setExtractionLoading(false)
    }
  }, [buildTenantHeaders, startDate, endDate, stations])

  const enterNgMode = useCallback((opts?: { winderNumber?: number | null }) => {
    autoRunArmedRef.current = true
    setNgMode(true)
    const nextWinder = opts?.winderNumber ?? null
    setNgWinderNumber(nextWinder)
    void fetchNgRecords({ winderNumber: nextWinder })
    void fetchExtractionAnalysis()
  }, [fetchNgRecords, fetchExtractionAnalysis])

  const exitNgMode = useCallback(() => {
    setNgMode(false)
    setNgRecords([])
    setNgError('')
    setNgWinderNumber(null)
    setExtractionData(null)
  }, [])

  useEffect(() => {
    if (!autoRunArmedRef.current) return
    if (productIdMode) return
    if (isLoading) return

    const key = computeAutoRunKey()
    if (key === lastAutoRunKeyRef.current) return
    if (key === pendingAutoRunKeyRef.current) return

    if (autoRunTimerRef.current) window.clearTimeout(autoRunTimerRef.current)
    pendingAutoRunKeyRef.current = key
    autoRunTimerRef.current = window.setTimeout(() => {
      pendingAutoRunKeyRef.current = ''
      lastAutoRunKeyRef.current = key
      handleRun()
    }, 300)

    return () => {
      if (autoRunTimerRef.current) {
        window.clearTimeout(autoRunTimerRef.current)
        autoRunTimerRef.current = null
      }
    }
  }, [productIdMode, computeAutoRunKey, handleRun, isLoading])

  const handleFilterKeyDown: KeyboardEventHandler<HTMLTextAreaElement> = (e) => {
    if (e.key !== 'Enter' || e.shiftKey) return
    e.preventDefault()
    if (isLoading) return
    commitProductId()
    runNow()
  }

  const productIdTextareaRef = useRef<HTMLTextAreaElement | null>(null)
  const syncProductIdTextareaHeight = useCallback(() => {
    const el = productIdTextareaRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${el.scrollHeight}px`
  }, [])

  useEffect(() => {
    syncProductIdTextareaHeight()
  }, [productIdDraft, syncProductIdTextareaHeight])

  return (
    <div className="analytics-page">
      <section className="register-card">
        <div className="analytics-header">
          <h2 className="analytics-title">{t('analytics.title')}</h2>
          <div className="register-hint">
            {tenantId ? (
              <>
                {t('analytics.tenantCurrent')}<strong title={tenantId}>{tenantLabel || t('analytics.tenantUnknown')}</strong>
              </>
            ) : (
              <>{t('analytics.tenantCurrent')}<span className="muted">{t('analytics.tenantNotSelected')}</span></>
            )}
          </div>
        </div>

        <div className="analytics-filters">
          <DateRangeSection
            rangeMode={rangeMode}
            anchorDate={anchorDate}
            customRange={customRange}
            startDate={startDate}
            endDate={endDate}
            isCompactCalendar={isCompactCalendar}
            onRangeModeChange={handleRangeModeChange}
            onSelectCustomRange={handleSelectCustomRange}
            onApplyAnchorForMode={applyAnchorForMode}
            onClearDateFilter={clearDateFilter}
          />

          <div className="analytics-filter-block">
            <div className="analytics-filter-title">{t('analytics.productId')}</div>
            <textarea
              ref={productIdTextareaRef}
              className="register-input analytics-product-textarea"
              rows={1}
              placeholder="輸入 產品編號（可多筆，以逗號/空白/換行分隔）→ 觸發 分析"
              value={productIdDraft}
              onChange={(e) => {
                setProductIdDraft(e.target.value)
                window.setTimeout(() => syncProductIdTextareaHeight(), 0)
              }}
              onBlur={commitProductId}
              onKeyDown={handleFilterKeyDown}
            />

            <div className="analytics-trace-actions">
              {productIdDraft.trim() ? (
                <button
                  type="button"
                  className="btn-secondary"
                  onClick={() => {
                    autoRunArmedRef.current = true
                    setProductIdDraft('')
                    setProductIdCommitted('')
                  }}
                >
                  清除 產品編號
                </button>
              ) : null}
            </div>
          </div>

          <div className="analytics-filter-block">
            <div className="analytics-filter-title">{t('analytics.stations')}</div>
            <div className="analytics-checkbox-row">
              <label className="analytics-checkbox">
                <input type="checkbox" checked={stations.p2} onChange={() => handleToggleStation('p2')} disabled={productIdMode} />
                P2
              </label>
              <label className="analytics-checkbox">
                <input type="checkbox" checked={stations.p3} onChange={() => handleToggleStation('p3')} disabled={productIdMode} />
                P3
              </label>
              {productIdMode ? null : (
                <label className="analytics-checkbox">
                  <input type="checkbox" checked={stations.all} onChange={() => handleToggleStation('all')} />
                  ALL
                </label>
              )}
            </div>
            {productIdMode ? <div className="analytics-date-preview">product_id 模式固定使用 P2 + P3</div> : null}
          </div>
        </div>

        <div className="analytics-actions">
          <button
            className="btn-primary"
            onClick={() => {
              runNow()
            }}
            disabled={isLoading}
          >
            {isLoading ? t('analytics.analyzing') : t('analytics.analyze')}
          </button>
        </div>

        {parseError ? <div className="analytics-error">{parseError}</div> : null}
      </section>

        {artifactsMode ? (
          <>
            <div ref={artifactsSectionRef} className="analytics-section-header">改善報告</div>
            <section className="analytics-card">
              <div className="analytics-actions" style={{ justifyContent: 'flex-start', marginTop: 0, gap: 8, flexWrap: 'wrap' }}>
                {([
                  ['events', 'Events'],
                  ['aggregated', 'Aggregated'],
                  ['weighted', 'Weighted'],
                  ['rag', 'RAG'],
                  ['llm', 'LLM'],
                ] as Array<[ViewKey, string]>).map(([key, label]) => (
                  <button
                    key={key}
                    type="button"
                    className={artifactView === key ? 'btn-primary' : 'btn-secondary'}
                    onClick={() => setArtifactView(key)}
                  >
                    {label}
                  </button>
                ))}
              </div>

              <ArtifactsView
                view={artifactView}
                tenantHeaders={buildTenantHeaders()}
                productIds={artifactProductFilters}
              />
            </section>
          </>
        ) : null}

      {ngMode ? (
        <NgModeSection
          ngWinderNumber={ngWinderNumber}
          ngLoading={ngLoading}
          ngError={ngError}
          ngRecords={ngRecords}
          ngParetoData={ngParetoData}
          featureParetoData={featureParetoData}
          extractionLoading={extractionLoading}
          extractionData={extractionData}
          ngFeaturePctEntries={ngFeaturePctEntries}
          ngFeaturePctChartData={ngFeaturePctChartData}
          ngFeaturePctChartHeight={ngFeaturePctChartHeight}
          onExitNgMode={exitNgMode}
          onClearWinder={() => {
            setNgWinderNumber(null)
            void fetchNgRecords({ winderNumber: null })
          }}
          onRefresh={() => void fetchNgRecords({ winderNumber: ngWinderNumber })}
          getNgKeyCandidates={getNgKeyCandidates}
          sortRowsNgFirst={sortRowsNgFirst}
          rowHasNg={rowHasNg}
          formatCellValue={formatCellValue}
        />
      ) : ran ? (
        <AnalysisResultsSection
          overall={overall}
          pieData={pieData}
          categoryCards={categoryCards}
          analysisHeatmapRows={analysisHeatmapRows}
          winderChartData={winderChartData}
          analysisChartMode={analysisChartMode}
          productIdMode={productIdMode}
          heatColor={heatColor}
          onSetChartMode={setAnalysisChartMode}
          onEnterNgMode={enterNgMode}
          parseWinderCategoryKey={parseWinderCategoryKey}
        />
      ) : null}
    </div>
  )
}
