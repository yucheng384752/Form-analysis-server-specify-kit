import { useCallback, useEffect, useMemo, useRef, useState, type KeyboardEventHandler } from 'react'
import { useTranslation } from 'react-i18next'
import { DayPicker, type DateRange } from 'react-day-picker'
import { endOfMonth, endOfWeek, format, startOfMonth, startOfWeek } from 'date-fns'
import { enUS, zhTW } from 'date-fns/locale'
import { ResponsiveContainer, Pie, PieChart, Cell, Tooltip, Legend, ComposedChart, BarChart, Bar, Line, XAxis, YAxis, CartesianGrid } from 'recharts'
import { getTenantId } from '../services/tenant'
import { getTenantLabelById, writeTenantMap } from '../services/tenantMap'
import { Drawer, DrawerContent } from '../components/ui/drawer'
import { TraceabilityFlow } from '../components/TraceabilityFlow'

import './../styles/analytics-page.css'
import 'react-day-picker/dist/style.css'

type RatioNode = {
  '0'?: number
  '1'?: number
  total_count?: number
  count_0?: number
}

type AnalysisResult = Record<string, Record<string, RatioNode>>

type StationSelection = {
  p2: boolean
  p3: boolean
  all: boolean
}

type DataType = 'P1' | 'P2' | 'P3'

type QueryRecordLite = {
  id: string
  lot_no: string
  data_type: DataType
  production_date?: string
  created_at: string
  display_name?: string
  product_id?: string
  machine_no?: string
  mold_no?: string
  additional_data?: Record<string, unknown>
}

type QueryResponseLite = {
  total_count: number
  page: number
  page_size: number
  records: QueryRecordLite[]
}

type TraceabilityData = {
  product_id: string
  p3: any
  p2: any
  p1: any
  trace_complete: boolean
  missing_links: string[]
}

type TenantRow = {
  id: string
  name?: string
  code?: string
}

const UT_FEATURE_PCT_DEMO: ReadonlyArray<{ name: string; pct: number }> = [
  { name: 'Thickness diff', pct: 16.66666666666669 },
  { name: 'Semi-finished impedance', pct: 16.666666666666686 },
  { name: 'Board Width(mm)', pct: 16.666666666666675 },
  { name: 'Thicknessss Low(μm)', pct: 16.666666666666664 },
  { name: 'Thicknessss High(μm)', pct: 16.666666666666657 },
  { name: 'Rubber wheel gasket thickness (in)', pct: 16.66666666666663 },
  { name: 'Heat gun temperature', pct: 8.758818145756964e-31 },
  { name: 'Slitting speed', pct: 2.0941660441376297e-31 },
  { name: 'Rubber wheel gasket thickness (out)', pct: 1.4956287073050555e-31 },
  { name: 'Rewind torque', pct: 5.235325593684113e-32 },
  { name: 'rough edge', pct: 0.0 },
  { name: 'Appearance', pct: 0.0 },
]

// Date granularity: min = week, max = half-year.
type RangeMode = 'week' | 'month' | 'quarter' | 'halfYear' | 'custom'

const MIN_RANGE_DAYS = 7
const MAX_RANGE_DAYS = 184 // approx half-year

function addDays(date: Date, days: number): Date {
  const d = new Date(date)
  d.setDate(d.getDate() + days)
  return d
}

function clampCustomRange(from: Date, to: Date): { start: Date; end: Date } {
  const start = new Date(from)
  const end = new Date(to)

  // Normalize order
  if (end.getTime() < start.getTime()) {
    return clampCustomRange(end, start)
  }

  const diffDays = Math.floor((end.getTime() - start.getTime()) / (24 * 60 * 60 * 1000)) + 1
  if (diffDays < MIN_RANGE_DAYS) {
    return { start, end: addDays(start, MIN_RANGE_DAYS - 1) }
  }
  if (diffDays > MAX_RANGE_DAYS) {
    return { start, end: addDays(start, MAX_RANGE_DAYS - 1) }
  }
  return { start, end }
}

function toYmd(date: Date): string {
  return format(date, 'yyyy-MM-dd')
}

function getHalfYearBounds(date: Date): { start: Date; end: Date } {
  const year = date.getFullYear()
  const month = date.getMonth() // 0-11
  if (month < 6) {
    return { start: new Date(year, 0, 1), end: new Date(year, 6, 0) }
  }
  return { start: new Date(year, 6, 1), end: new Date(year + 1, 0, 0) }
}

function getQuarterBounds(date: Date): { start: Date; end: Date } {
  const year = date.getFullYear()
  const month = date.getMonth() // 0-11
  const quarterStartMonth = Math.floor(month / 3) * 3
  return {
    start: new Date(year, quarterStartMonth, 1),
    end: new Date(year, quarterStartMonth + 3, 0),
  }
}

function getModeBounds(mode: Exclude<RangeMode, 'custom'>, anchor: Date): { start: Date; end: Date } {
  switch (mode) {
    case 'week':
      return {
        start: startOfWeek(anchor, { weekStartsOn: 1 }),
        end: endOfWeek(anchor, { weekStartsOn: 1 }),
      }
    case 'month':
      return { start: startOfMonth(anchor), end: endOfMonth(anchor) }
    case 'quarter':
      return getQuarterBounds(anchor)
    case 'halfYear':
      return getHalfYearBounds(anchor)
  }
}

function getIsoWeekYear(date: Date): number {
  const d = new Date(Date.UTC(date.getFullYear(), date.getMonth(), date.getDate()))
  const day = d.getUTCDay() || 7
  d.setUTCDate(d.getUTCDate() + 4 - day)
  return d.getUTCFullYear()
}

function getIsoWeekNumber(date: Date): number {
  const d = new Date(Date.UTC(date.getFullYear(), date.getMonth(), date.getDate()))
  const day = d.getUTCDay() || 7
  d.setUTCDate(d.getUTCDate() + 4 - day)
  const yearStart = new Date(Date.UTC(d.getUTCFullYear(), 0, 1))
  const diffDays = Math.floor((d.getTime() - yearStart.getTime()) / (24 * 60 * 60 * 1000)) + 1
  return Math.ceil(diffDays / 7)
}

function isoWeekStartDate(weekYear: number, weekNumber: number): Date {
  const safeWeek = Math.max(1, Math.min(53, Math.floor(weekNumber || 1)))
  const simple = new Date(Date.UTC(weekYear, 0, 1 + (safeWeek - 1) * 7))
  const dow = simple.getUTCDay() || 7
  const mondayUtc = new Date(simple)
  mondayUtc.setUTCDate(simple.getUTCDate() - dow + 1)
  return new Date(mondayUtc.getUTCFullYear(), mondayUtc.getUTCMonth(), mondayUtc.getUTCDate())
}

function parseCounts(node: RatioNode | undefined): { ok: number; ng: number; total: number } {
  const total = Math.max(0, Number(node?.total_count ?? 0) || 0)
  const ng = Math.max(0, Number(node?.count_0 ?? 0) || 0)
  const ok = Math.max(0, total - ng)
  return { ok, ng, total }
}

function isPlainObject(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value)
}

function normalizeAnalysisResult(input: unknown): AnalysisResult | null {
  if (!isPlainObject(input)) return null
  const result: AnalysisResult = {}
  for (const [category, bucket] of Object.entries(input)) {
    if (!isPlainObject(bucket)) continue
    const inner: Record<string, RatioNode> = {}
    for (const [key, rawNode] of Object.entries(bucket)) {
      if (!isPlainObject(rawNode)) continue
      const node = rawNode as RatioNode
      inner[key] = node
    }
    if (Object.keys(inner).length > 0) result[category] = inner
  }
  return Object.keys(result).length > 0 ? result : null
}

function pickOverallNode(result: AnalysisResult): { category: string; key: string; node: RatioNode } | null {
  let best: { category: string; key: string; node: RatioNode } | null = null
  let bestTotal = -1
  let bestNg = -1
  for (const [category, bucket] of Object.entries(result)) {
    for (const [key, node] of Object.entries(bucket)) {
      const total = Number(node?.total_count ?? 0) || 0
      const ng = Number(node?.count_0 ?? 0) || 0
      if (total > bestTotal || (total === bestTotal && ng > bestNg)) {
        best = { category, key, node }
        bestTotal = total
        bestNg = ng
      }
    }
  }
  return best
}

function pct(n: number, d: number): number {
  if (!d) return 0
  return Math.round((n / d) * 1000) / 10
}

function round3(n: number): number {
  return Math.round(n * 1000) / 1000
}

function toCumsumSeries(items: ReadonlyArray<{ name: string; pct: number }>): Array<{ name: string; pct: number; cumPct: number }> {
  let cum = 0
  return items.map((x) => {
    const pct3 = round3(x.pct)
    cum = Math.min(100, round3(cum + pct3))
    return { name: x.name, pct: pct3, cumPct: cum }
  })
}

export function AnalyticsPage() {
  const { t, i18n } = useTranslation()
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
  const [traceLoading, setTraceLoading] = useState(false)
  const [traceError, setTraceError] = useState('')
  const [traceDrawerOpen, setTraceDrawerOpen] = useState(false)

  const [ngMode, setNgMode] = useState(false)
  const [ngRecords, setNgRecords] = useState<QueryRecordLite[]>([])
  const [ngLoading, setNgLoading] = useState(false)
  const [ngError, setNgError] = useState('')
  const [ngWinderNumber, setNgWinderNumber] = useState<number | null>(null)

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

  const utFeaturePctChartData = useMemo(() => {
    const sorted = [...UT_FEATURE_PCT_DEMO].sort((a, b) => b.pct - a.pct)
    return toCumsumSeries(sorted)
  }, [])

  const ngFeaturePctChartHeight = useMemo(() => {
    const count = Math.min(10, ngFeaturePctEntries.length)
    // For horizontal bars, reserve space for long X-axis labels.
    return Math.max(360, 220 + count * 4)
  }, [ngFeaturePctEntries.length])

  const autoRunArmedRef = useRef(false)
  const autoRunTimerRef = useRef<number | null>(null)
  const lastAutoRunKeyRef = useRef<string>('')
  const pendingAutoRunKeyRef = useRef<string>('')

  const tenantId = useMemo(() => getTenantId(), [])
  const tenantLabel = useMemo(() => getTenantLabelById(tenantId), [tenantId, tenantMapVersion])

  const buildTenantHeaders = useCallback(() => {
    if (!tenantId) return {}
    return { 'X-Tenant-Id': tenantId }
  }, [tenantId])

  useEffect(() => {
    const pid = productIdCommitted.trim()
    if (!pid) {
      setTraceData(null)
      setTraceError('')
      setTraceLoading(false)
      return
    }

    const controller = new AbortController()
    const headers = buildTenantHeaders()

    void (async () => {
      try {
        setTraceLoading(true)
        setTraceError('')

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
        setTraceError(String(err?.message || t('analytics.traceabilityFetchFailed')))
      } finally {
        if (controller.signal.aborted) return
        setTraceLoading(false)
      }
    })()

    return () => controller.abort()
  }, [buildTenantHeaders, productIdCommitted, t])

  const commitProductId = useCallback(() => {
    const next = productIdDraft.trim()
    if (next === productIdCommitted) return
    autoRunArmedRef.current = true
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
    if (typeof window === 'undefined') return
    const mq = window.matchMedia('(max-width: 860px)')
    const update = () => setIsCompactCalendar(mq.matches)
    update()

    if (typeof mq.addEventListener === 'function') {
      mq.addEventListener('change', update)
      return () => mq.removeEventListener('change', update)
    }

    // Safari/older browsers
    // eslint-disable-next-line deprecation/deprecation
    mq.addListener(update)
    // eslint-disable-next-line deprecation/deprecation
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

  const OK_COLOR = '#2563eb'
  const NG_COLOR = '#dc2626'
  const colors = [OK_COLOR, NG_COLOR]

  const pickerLocale = useMemo(() => {
    return i18n.language === 'en' ? enUS : zhTW
  }, [i18n.language])

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
    autoRunArmedRef.current = true
    setStartDate('')
    setEndDate('')
    setAnchorDate(undefined)
    setCustomRange(undefined)
  }

  const handleSelectCustomRange = (range: DateRange | undefined) => {
    autoRunArmedRef.current = true
    setCustomRange(range)
    if (!range?.from) {
      setStartDate('')
      setEndDate('')
      return
    }
    if (!range.to) {
      // Min granularity is week: if only one day is picked, expand to the week.
      const bounds = getModeBounds('week', range.from)
      applyComputedRange(bounds.start, bounds.end)
      return
    }
    const clamped = clampCustomRange(range.from, range.to)
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
      items: Array<{ key: string; ok: number; ng: number; total: number }>
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
      const items = sortedKeys.map((k) => ({ key: k, ...parseCounts(bucket[k]) }))
      categories.push({ category, items })
    }
    return categories
  }, [analysisResult])

  const computeAutoRunKey = useCallback(() => {
    return JSON.stringify({ startDate, endDate, productId: productIdCommitted, stations })
  }, [startDate, endDate, productIdCommitted, stations])

  const handleRun = useCallback((opts?: { productIdOverride?: string }) => {
    void (async () => {
      setParseError('')
      setIsLoading(true)
      setNgMode(false)
      setNgRecords([])
      setNgError('')
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

        const res = await fetch('/api/v2/analytics/analyze', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', ...buildTenantHeaders() },
          body: JSON.stringify({
            start_date: startDate || null,
            end_date: endDate || null,
            product_id: (opts?.productIdOverride ?? productIdCommitted) || null,
            stations: chosenStations,
          }),
        })

        if (!res.ok) {
          const text = await res.text().catch(() => '')
          setParseError(text || t('analytics.analyzeRequestFailed', { status: res.status }))
          return
        }

        const json = (await res.json()) as unknown
        const normalized = normalizeAnalysisResult(json)
        if (!normalized) {
          // empty object/empty buckets -> treat as not found
          const isEmptyObject =
            json && typeof json === 'object' && !Array.isArray(json) && Object.keys(json as Record<string, unknown>).length === 0

          const isEmptyBuckets =
            isPlainObject(json) &&
            Object.values(json).length > 0 &&
            Object.values(json).every((v) => isPlainObject(v) && Object.keys(v).length === 0)

          if (isEmptyObject || isEmptyBuckets) {
            setParseError(t('analytics.notFound'))
          } else {
            setParseError(t('analytics.invalidResponse'))
          }
          setAnalysisResult(null)
          setRan(false)
          return
        }

        // 自動化：收到 response 後立刻顯示繪圖結果
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
    autoRunArmedRef.current = true

    const overrideProductId = productIdDraft.trim()
    setProductIdCommitted(overrideProductId)

    pendingAutoRunKeyRef.current = ''
    lastAutoRunKeyRef.current = JSON.stringify({ startDate, endDate, productId: overrideProductId, stations })
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
    const upper = s.toUpperCase()
    return upper === 'X' || upper === 'NG' || upper.includes('NG') || upper === '0'
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
        'Appearance',
        'appearance',
        'rough edge',
        'rough_edge',
      ]
    }
    if (record.data_type === 'P3') {
      return ['Finish', 'finish', '結果', 'result']
    }
    return []
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
          'Appearance',
          'appearance',
          'rough edge',
          'rough_edge',
        ]),
      )
    }
    if (record.data_type === 'P3') {
      return rows.some((r) => rowHasNg(r, ['Finish', 'finish', '結果', 'result']))
    }
    return false
  }, [rowHasNg])

  const fetchNgRecords = useCallback(async (opts?: { winderNumber?: number | null }) => {
    setNgError('')
    setNgLoading(true)
    try {
      const wantedTypes: DataType[] = stations.all
        ? ['P2', 'P3']
        : ([stations.p2 ? 'P2' : null, stations.p3 ? 'P3' : null].filter(Boolean) as DataType[])

      if (wantedTypes.length === 0) {
        setNgError(t('analytics.stationPickError'))
        setNgRecords([])
        return
      }

      const results = await Promise.all(
        wantedTypes.map(async (dt) => {
          const filters: Array<{ field: string; op: string; value: any }> = []

          if (startDate && endDate) {
            if (startDate === endDate) {
              filters.push({ field: 'production_date', op: 'eq', value: startDate })
            } else {
              filters.push({ field: 'production_date', op: 'between', value: [startDate, endDate] })
            }
          } else if (startDate) {
            filters.push({ field: 'production_date', op: 'eq', value: startDate })
          } else if (endDate) {
            filters.push({ field: 'production_date', op: 'eq', value: endDate })
          }

          if (productIdCommitted) {
            filters.push({ field: 'product_id', op: 'contains', value: productIdCommitted })
          }

          if (opts?.winderNumber) {
            filters.push({ field: 'winder_number', op: 'eq', value: String(opts.winderNumber) })
          }

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
  }, [buildTenantHeaders, endDate, productIdCommitted, recordHasNg, startDate, stations, t])

  const enterNgMode = useCallback((opts?: { winderNumber?: number | null }) => {
    autoRunArmedRef.current = true
    setNgMode(true)
    const nextWinder = opts?.winderNumber ?? null
    setNgWinderNumber(nextWinder)
    void fetchNgRecords({ winderNumber: nextWinder })
  }, [fetchNgRecords])

  const exitNgMode = useCallback(() => {
    setNgMode(false)
    setNgRecords([])
    setNgError('')
    setNgWinderNumber(null)
  }, [])

  useEffect(() => {
    if (!autoRunArmedRef.current) return
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
  }, [computeAutoRunKey, handleRun, isLoading])

  const handleFilterKeyDown: KeyboardEventHandler<HTMLInputElement> = (e) => {
    if (e.key !== 'Enter') return
    e.preventDefault()
    if (isLoading) return
    commitProductId()
    runNow()
  }

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
          <div className="analytics-filter-block analytics-date-block">
            <div className="analytics-date-block-top">
              <div>
                <div className="analytics-filter-title">{t('analytics.dateRangeMode')}</div>
                <div className="analytics-date-mode">
                  <select
                    className="register-input analytics-date-select"
                    value={rangeMode}
                    onChange={(e) => handleRangeModeChange(e.target.value as RangeMode)}
                  >
                    <option value="week">{t('analytics.modeWeek')}</option>
                    <option value="month">{t('analytics.modeMonth')}</option>
                    <option value="quarter">{t('analytics.modeQuarter')}</option>
                    <option value="halfYear">{t('analytics.modeHalfYear')}</option>
                    <option value="custom">{t('analytics.modeCustom')}</option>
                  </select>
                </div>
                <div className="analytics-date-preview">{t('analytics.rangePreview', { start: startDate || '-', end: endDate || '-' })}</div>
              </div>
              <div className="analytics-date-actions">
                <button type="button" className="btn-secondary" onClick={clearDateFilter}>
                  {t('common.clear')}
                </button>
              </div>
            </div>

            <div className="analytics-date-picker">
              <div className="analytics-filter-title">{rangeMode === 'custom' ? t('analytics.pickRange') : t('analytics.pickPreset')}</div>
              {rangeMode === 'custom' ? (
                <DayPicker
                  mode="range"
                  selected={customRange}
                  onSelect={handleSelectCustomRange}
                  showOutsideDays
                  numberOfMonths={isCompactCalendar ? 1 : 2}
                  locale={pickerLocale}
                  weekStartsOn={1}
                />
              ) : (
                (() => {
                  const today = new Date()
                  const hasAnchor = Boolean(anchorDate)
                  const anchor = anchorDate ?? today

                  const baseYear = anchor.getFullYear()
                  const years = Array.from({ length: 9 }, (_, i) => baseYear - 4 + i)

                  const month = anchor.getMonth() + 1
                  const quarter = Math.floor(anchor.getMonth() / 3) + 1
                  const half = anchor.getMonth() < 6 ? 1 : 2

                  const isoWeekYear = getIsoWeekYear(anchor)
                  const isoWeek = getIsoWeekNumber(anchor)

                  if (rangeMode === 'month') {
                    const yearValue = hasAnchor ? String(baseYear) : ''
                    const monthValue = hasAnchor ? String(month) : ''
                    return (
                      <div className="analytics-date-presets">
                        <label className="analytics-date-label">
                          {t('analytics.yearLabel')}
                          <select
                            className="register-input analytics-date-select"
                            value={yearValue}
                            onChange={(e) => {
                              if (!e.target.value) {
                                applyAnchorForMode('month', undefined)
                                return
                              }
                              const y = Number(e.target.value)
                              if (!Number.isFinite(y)) return
                              applyAnchorForMode('month', new Date(y, month - 1, 1))
                            }}
                          >
                            {!hasAnchor ? <option value="">-</option> : null}
                            {years.map((y) => (
                              <option key={y} value={String(y)}>
                                {y}
                              </option>
                            ))}
                          </select>
                        </label>
                        <label className="analytics-date-label">
                          {t('analytics.monthLabel')}
                          <select
                            className="register-input analytics-date-select"
                            value={monthValue}
                            onChange={(e) => {
                              if (!e.target.value) {
                                applyAnchorForMode('month', undefined)
                                return
                              }
                              const m = Number(e.target.value)
                              if (!Number.isFinite(m)) return
                              applyAnchorForMode('month', new Date(baseYear, Math.max(1, Math.min(12, m)) - 1, 1))
                            }}
                          >
                            {!hasAnchor ? <option value="">-</option> : null}
                            {Array.from({ length: 12 }, (_, i) => i + 1).map((m) => (
                              <option key={m} value={String(m)}>
                                {m}
                              </option>
                            ))}
                          </select>
                        </label>
                      </div>
                    )
                  }

                  if (rangeMode === 'quarter') {
                    const yearValue = hasAnchor ? String(baseYear) : ''
                    const quarterValue = hasAnchor ? String(quarter) : ''
                    return (
                      <div className="analytics-date-presets">
                        <label className="analytics-date-label">
                          {t('analytics.yearLabel')}
                          <select
                            className="register-input analytics-date-select"
                            value={yearValue}
                            onChange={(e) => {
                              if (!e.target.value) {
                                applyAnchorForMode('quarter', undefined)
                                return
                              }
                              const y = Number(e.target.value)
                              if (!Number.isFinite(y)) return
                              applyAnchorForMode('quarter', new Date(y, (quarter - 1) * 3, 1))
                            }}
                          >
                            {!hasAnchor ? <option value="">-</option> : null}
                            {years.map((y) => (
                              <option key={y} value={String(y)}>
                                {y}
                              </option>
                            ))}
                          </select>
                        </label>
                        <label className="analytics-date-label">
                          {t('analytics.quarterLabel')}
                          <select
                            className="register-input analytics-date-select"
                            value={quarterValue}
                            onChange={(e) => {
                              if (!e.target.value) {
                                applyAnchorForMode('quarter', undefined)
                                return
                              }
                              const q = Number(e.target.value)
                              if (!Number.isFinite(q)) return
                              const qq = Math.max(1, Math.min(4, q))
                              applyAnchorForMode('quarter', new Date(baseYear, (qq - 1) * 3, 1))
                            }}
                          >
                            {!hasAnchor ? <option value="">-</option> : null}
                            {[1, 2, 3, 4].map((q) => (
                              <option key={q} value={String(q)}>
                                Q{q}
                              </option>
                            ))}
                          </select>
                        </label>
                      </div>
                    )
                  }

                  if (rangeMode === 'halfYear') {
                    const yearValue = hasAnchor ? String(baseYear) : ''
                    const halfValue = hasAnchor ? String(half) : ''
                    return (
                      <div className="analytics-date-presets">
                        <label className="analytics-date-label">
                          {t('analytics.yearLabel')}
                          <select
                            className="register-input analytics-date-select"
                            value={yearValue}
                            onChange={(e) => {
                              if (!e.target.value) {
                                applyAnchorForMode('halfYear', undefined)
                                return
                              }
                              const y = Number(e.target.value)
                              if (!Number.isFinite(y)) return
                              applyAnchorForMode('halfYear', new Date(y, half === 1 ? 0 : 6, 1))
                            }}
                          >
                            {!hasAnchor ? <option value="">-</option> : null}
                            {years.map((y) => (
                              <option key={y} value={String(y)}>
                                {y}
                              </option>
                            ))}
                          </select>
                        </label>
                        <label className="analytics-date-label">
                          {t('analytics.halfYearLabel')}
                          <select
                            className="register-input analytics-date-select"
                            value={halfValue}
                            onChange={(e) => {
                              if (!e.target.value) {
                                applyAnchorForMode('halfYear', undefined)
                                return
                              }
                              const h = Number(e.target.value)
                              if (!Number.isFinite(h)) return
                              const hh = Math.max(1, Math.min(2, h))
                              applyAnchorForMode('halfYear', new Date(baseYear, hh === 1 ? 0 : 6, 1))
                            }}
                          >
                            {!hasAnchor ? <option value="">-</option> : null}
                            <option value="1">{t('analytics.halfYearH1')}</option>
                            <option value="2">{t('analytics.halfYearH2')}</option>
                          </select>
                        </label>
                      </div>
                    )
                  }

                  // week
                  const yearValue = hasAnchor ? String(isoWeekYear) : ''
                  const weekValue = hasAnchor ? String(isoWeek) : ''
                  return (
                    <div className="analytics-date-presets">
                      <label className="analytics-date-label">
                        {t('analytics.yearLabel')}
                        <select
                          className="register-input analytics-date-select"
                          value={yearValue}
                          onChange={(e) => {
                            if (!e.target.value) {
                              applyAnchorForMode('week', undefined)
                              return
                            }
                            const y = Number(e.target.value)
                            if (!Number.isFinite(y)) return
                            applyAnchorForMode('week', isoWeekStartDate(y, isoWeek))
                          }}
                        >
                          {!hasAnchor ? <option value="">-</option> : null}
                          {Array.from({ length: 9 }, (_, i) => isoWeekYear - 4 + i).map((y) => (
                            <option key={y} value={String(y)}>
                              {y}
                            </option>
                          ))}
                        </select>
                      </label>
                      <label className="analytics-date-label">
                        {t('analytics.weekNumberLabel')}
                        <input
                          className="register-input analytics-date-input"
                          type="number"
                          min={1}
                          max={53}
                          value={weekValue}
                          onChange={(e) => {
                            if (!e.target.value) {
                              applyAnchorForMode('week', undefined)
                              return
                            }
                            const w = Number(e.target.value)
                            if (!Number.isFinite(w)) return
                            applyAnchorForMode('week', isoWeekStartDate(isoWeekYear, w))
                          }}
                        />
                      </label>
                    </div>
                  )
                })()
              )}
            </div>
          </div>

          <div className="analytics-filter-block">
            <div className="analytics-filter-title">{t('analytics.productId')}</div>
            <input
              className="register-input"
              type="text"
              placeholder={t('analytics.productIdPlaceholder')}
              value={productIdDraft}
              onChange={(e) => setProductIdDraft(e.target.value)}
              onBlur={commitProductId}
              onKeyDown={handleFilterKeyDown}
            />

            <div className="analytics-trace-actions">
              <button
                type="button"
                className="btn-secondary"
                onClick={() => {
                  commitProductId()
                  const pid = productIdDraft.trim()
                  if (!pid) return
                  setTraceDrawerOpen(true)
                }}
                disabled={!productIdDraft.trim()}
              >
                {t('analytics.traceabilityOpen')}
              </button>
            </div>

            {productIdCommitted ? (
              <div className="analytics-trace-panel">
                <div className="analytics-trace-title">{t('analytics.traceabilityTitle')}</div>
                {traceLoading ? <div className="muted">{t('analytics.loading')}</div> : null}
                {traceError ? <div className="analytics-error">{traceError}</div> : null}
                {!traceLoading && !traceError && traceData ? (
                  <div className="analytics-trace-grid">
                    <div className="analytics-trace-item">
                      <div className="analytics-trace-label">P1</div>
                      <div className="analytics-trace-value">{traceData.p1?.lot_no ?? t('common.noData')}</div>
                    </div>
                    <div className="analytics-trace-item">
                      <div className="analytics-trace-label">P2</div>
                      <div className="analytics-trace-value">
                        {traceData.p2?.lot_no ?? t('common.noData')}
                        {traceData.p2?.winder_number ? ` · W${traceData.p2.winder_number}` : ''}
                      </div>
                    </div>
                    <div className="analytics-trace-item">
                      <div className="analytics-trace-label">P3</div>
                      <div className="analytics-trace-value">{traceData.p3?.product_id ?? t('common.noData')}</div>
                    </div>
                    {!traceData.trace_complete ? (
                      <div className="analytics-trace-warning">
                        {t('analytics.traceabilityIncomplete', { missing: (traceData.missing_links || []).join(', ') })}
                      </div>
                    ) : null}
                  </div>
                ) : null}
              </div>
            ) : null}
          </div>

          <div className="analytics-filter-block">
            <div className="analytics-filter-title">{t('analytics.stations')}</div>
            <div className="analytics-checkbox-row">
              <label className="analytics-checkbox">
                <input type="checkbox" checked={stations.p2} onChange={() => handleToggleStation('p2')} />
                P2
              </label>
              <label className="analytics-checkbox">
                <input type="checkbox" checked={stations.p3} onChange={() => handleToggleStation('p3')} />
                P3
              </label>
              <label className="analytics-checkbox">
                <input type="checkbox" checked={stations.all} onChange={() => handleToggleStation('all')} />
                ALL
              </label>
            </div>
          </div>
        </div>

        <div className="analytics-actions">
          <button className="btn-primary" onClick={runNow} disabled={isLoading}>{isLoading ? t('analytics.analyzing') : t('analytics.analyze')}</button>
        </div>

        {parseError ? <div className="analytics-error">{parseError}</div> : null}
      </section>

        <Drawer open={traceDrawerOpen} onOpenChange={setTraceDrawerOpen}>
          <DrawerContent>
            <TraceabilityFlow
              productId={productIdCommitted || productIdDraft.trim()}
              {...(traceData ? { preloadedData: traceData } : {})}
              tenantId={tenantId}
              onClose={() => setTraceDrawerOpen(false)}
            />
          </DrawerContent>
        </Drawer>

      {ngMode ? (
        <>
          <div className="analytics-section-header">{t('analytics.ngOnlyTitle')}{ngWinderNumber ? ` · W${ngWinderNumber}` : ''}</div>

          <section className="analytics-card">
            <div className="analytics-actions" style={{ justifyContent: 'space-between', marginTop: 0 }}>
              <button type="button" className="btn-secondary" onClick={exitNgMode}>
                {t('analytics.backToAnalysis')}
              </button>

              <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                {ngWinderNumber ? (
                  <button
                    type="button"
                    className="btn-secondary"
                    onClick={() => {
                      setNgWinderNumber(null)
                      void fetchNgRecords({ winderNumber: null })
                    }}
                    disabled={ngLoading}
                  >
                    {t('common.clear')}
                  </button>
                ) : null}

                <button type="button" className="btn-primary" onClick={() => void fetchNgRecords({ winderNumber: ngWinderNumber })} disabled={ngLoading}>
                  {ngLoading ? t('analytics.loading') : t('analytics.refresh')}
                </button>
              </div>
            </div>

            {ngFeaturePctEntries.length > 0 ? (
              <div className="analytics-ng-feature-chart" aria-label={t('analytics.featurePct.title')}>
                <div className="analytics-ng-feature-chart-title">{t('analytics.featurePct.title')}</div>
                <div className="analytics-ng-feature-chart-body" style={{ height: ngFeaturePctChartHeight }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <ComposedChart
                      data={ngFeaturePctChartData}
                      margin={{ top: 8, right: 16, bottom: 80, left: 12 }}
                    >
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis
                        type="category"
                        dataKey="name"
                        interval={0}
                        angle={-35}
                        height={80}
                        textAnchor="end"
                        tick={{ fontSize: 12 }}
                      />
                      <YAxis type="number" domain={[0, 100]} tickFormatter={(v) => `${v}%`} />
                      <Tooltip
                        formatter={(value, name) => {
                          const n = typeof value === 'number' ? value : Number(value)
                          const label = name === 'cumPct' ? '累積' : '占比'
                          if (!Number.isFinite(n)) return [String(value), label]
                          return [`${round3(n).toFixed(3)}%`, label]
                        }}
                      />
                      <Legend />
                      <Bar dataKey="pct" name="占比" fill="#2563eb" radius={[6, 6, 0, 0]} />
                      <Line dataKey="cumPct" name="累積" type="monotone" stroke="#ef4444" strokeWidth={2} dot={{ r: 2 }} />
                    </ComposedChart>
                  </ResponsiveContainer>
                </div>
              </div>
            ) : null}

            <div className="analytics-ng-extra">
              <div className="analytics-ng-feature-chart" aria-label={t('analytics.featurePct.title')}>
                <div className="analytics-ng-feature-chart-title">{t('analytics.featurePct.title')}（UT）</div>
                <div className="analytics-ng-feature-chart-body" style={{ height: 380 }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <ComposedChart
                      data={utFeaturePctChartData}
                      margin={{ top: 8, right: 16, bottom: 90, left: 12 }}
                    >
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis
                        type="category"
                        dataKey="name"
                        interval={0}
                        angle={-35}
                        height={90}
                        textAnchor="end"
                        tick={{ fontSize: 12 }}
                      />
                      <YAxis type="number" domain={[0, 100]} tickFormatter={(v) => `${v}%`} />
                      <Tooltip
                        formatter={(value, name) => {
                          const n = typeof value === 'number' ? value : Number(value)
                          const label = name === 'cumPct' ? '累積' : '占比'
                          if (!Number.isFinite(n)) return [String(value), label]
                          return [`${round3(n).toFixed(3)}%`, label]
                        }}
                      />
                      <Legend />
                      <Bar dataKey="pct" name="占比" fill="#0ea5e9" radius={[6, 6, 0, 0]} />
                      <Line dataKey="cumPct" name="累積" type="monotone" stroke="#ef4444" strokeWidth={2} dot={{ r: 2 }} />
                    </ComposedChart>
                  </ResponsiveContainer>
                </div>
              </div>
            </div>

            {ngError ? <div className="analytics-error">{ngError}</div> : null}

            <div className="analytics-ng-results">
              {ngLoading && ngRecords.length === 0 ? <div className="analytics-empty">{t('analytics.loading')}</div> : null}
              {!ngLoading && ngRecords.length === 0 ? <div className="analytics-empty">{t('analytics.notFound')}</div> : null}

              {ngRecords.map((r) => (
                <div key={r.id} className="analytics-ng-card">
                  <div className="analytics-ng-card-head">
                    <div className="analytics-ng-card-title">
                      <strong>{r.lot_no}</strong>
                      <span className="analytics-ng-pill">{r.data_type}</span>
                    </div>
                    <div className="muted" style={{ fontSize: '0.9rem' }}>
                      {r.production_date ? `${t('query.productionDate')}: ${r.production_date}` : null}
                      {r.production_date && r.product_id ? ' · ' : null}
                      {r.product_id ? `${t('query.productId')}: ${r.product_id}` : null}
                    </div>
                  </div>
                  <details>
                    <summary>{t('analytics.viewDetails')}</summary>
                    {(() => {
                      const additional = r.additional_data as any
                      const featurePctObjRaw =
                        (additional && typeof additional === 'object'
                          ? (additional.feature_pct ??
                              additional.featurePct ??
                              additional.feature_importance?.feature_pct ??
                              additional.featureImportance?.feature_pct)
                          : null) as unknown

                      const featurePctObj = isPlainObject(featurePctObjRaw) ? (featurePctObjRaw as Record<string, unknown>) : null
                      const featurePctEntries = featurePctObj
                        ? Object.entries(featurePctObj)
                            .filter(([, v]) => typeof v === 'number' && Number.isFinite(v as number))
                            .map(([name, v]) => ({ name, pct: Number(v) }))
                            .sort((a, b) => b.pct - a.pct)
                        : []

                      const rows: unknown[] = Array.isArray(additional?.rows) ? additional.rows : []
                      if (rows.length === 0) {
                        return <div className="analytics-empty">{t('common.noData')}</div>
                      }
                      const keys = getNgKeyCandidates(r)
                      const sorted = sortRowsNgFirst(rows, keys)
                      const ngOnly = sorted.filter((row) => rowHasNg(row, keys))
                      const firstRow = sorted.find((x) => x && typeof x === 'object' && !Array.isArray(x)) as Record<string, unknown> | undefined
                      const headers = firstRow ? Object.keys(firstRow) : []
                      const ngCount = ngOnly.length
                      if (ngOnly.length === 0) {
                        return <div className="analytics-empty">{t('common.noData')}</div>
                      }
                      return (
                        <div className="analytics-ng-details">
                          {featurePctEntries.length > 0 ? (
                            <div
                              className="analytics-ng-feature-pct"
                              style={{
                                border: '1px solid #e5e7eb',
                                borderRadius: 10,
                                padding: '12px 12px',
                                marginBottom: 12,
                                background: '#fafafa',
                              }}
                            >
                              <div style={{ fontWeight: 700, marginBottom: 8 }}>
                                {t('analytics.featurePct.title')}
                              </div>
                              <div
                                style={{
                                  display: 'grid',
                                  gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
                                  gap: 8,
                                }}
                              >
                                {featurePctEntries.slice(0, 12).map((x) => (
                                  <div key={x.name} style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                                    <div style={{ flex: '1 1 auto', minWidth: 0 }} title={x.name}>
                                      <div style={{ fontSize: '0.92rem', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                                        {x.name}
                                      </div>
                                      <div style={{ height: 6, background: '#e5e7eb', borderRadius: 999, overflow: 'hidden', marginTop: 4 }}>
                                        <div
                                          style={{
                                            height: '100%',
                                            width: `${Math.max(0, Math.min(100, x.pct))}%`,
                                            background: '#2563eb',
                                          }}
                                        />
                                      </div>
                                    </div>
                                    <div style={{ width: 62, textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>
                                      {t('analytics.featurePct.percent', { percent: x.pct.toFixed(2) })}
                                    </div>
                                  </div>
                                ))}
                              </div>
                            </div>
                          ) : null}
                          <div className="analytics-ng-details-meta muted">
                            Rows: {rows.length} · NG: {ngCount}
                          </div>
                          <div className="analytics-ng-table">
                            <div className="table-container">
                              <table className="data-table">
                                <thead>
                                  <tr>
                                    {headers.map((h) => (
                                      <th key={h}>{h}</th>
                                    ))}
                                  </tr>
                                </thead>
                                <tbody>
                                  {ngOnly.map((row, idx) => {
                                    const rowObj = (row && typeof row === 'object' && !Array.isArray(row) ? (row as Record<string, unknown>) : {})
                                    const isNg = rowHasNg(rowObj, keys)
                                    return (
                                      <tr key={idx} className={isNg ? 'analytics-ng-row' : undefined}>
                                        {headers.map((h) => (
                                          <td key={h}>{formatCellValue(rowObj?.[h])}</td>
                                        ))}
                                      </tr>
                                    )
                                  })}
                                </tbody>
                              </table>
                            </div>
                          </div>
                        </div>
                      )
                    })()}
                  </details>
                </div>
              ))}
            </div>
          </section>
        </>
      ) : ran ? (
        <>
          <div className="analytics-section-header">{t('analytics.yield')}</div>

          <div className="analytics-note">{t('analytics.ngDrilldownHint')}</div>

          <section className="analytics-card">
            <div className="analytics-card-title">{t('analytics.totalProducts')}</div>
            <div className="analytics-grid-2">
              <div>
                <div className="analytics-kv">
                  <div className="analytics-k">{t('analytics.ok')}</div>
                  <div className="analytics-v">{overall.ok}</div>
                  <div className="analytics-k">{t('analytics.ng')}</div>
                  <div className="analytics-v">{overall.ng}</div>
                </div>
              </div>
              <div className="analytics-chart-wrap">
                <ResponsiveContainer>
                  <PieChart>
                    <Pie
                      data={pieData}
                      dataKey="value"
                      nameKey="name"
                      outerRadius={90}
                      label
                      onClick={(data: any) => {
                        if (data?.payload?.kind === 'NG') enterNgMode()
                      }}
                    >
                      {pieData.map((_, idx) => (
                        <Cell key={idx} fill={colors[idx % colors.length]} />
                      ))}
                    </Pie>
                    <Tooltip />
                    <Legend />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            </div>
          </section>

          <div className="analytics-section-header">{t('analytics.moldingAnalysis')}</div>

          <section className="analytics-card">
            {categoryCards.length > 0 ? (
              categoryCards.map((cat) => {
                const title = cat.category
                const isWinderCategory = /winder/i.test(String(title))
                return (
                  <div key={cat.category} style={{ marginBottom: '1.5rem' }}>
                    <div className="analytics-card-title">{title}</div>
                    <div className="analytics-grid-2" style={{ marginTop: '0.75rem' }}>
                      {cat.items.map((item) => {
                        const barData = [
                          { name: 'OK', value: item.ok },
                          { name: 'NG', value: item.ng },
                        ]
                        return (
                          <div key={`${cat.category}:${item.key}`}>
                            <div className="analytics-card-title">{item.key}</div>
                            <div className="muted" style={{ fontSize: '0.9rem' }}>
                              {t('analytics.summary.productionNg', { total: item.total, ng: item.ng, percent: pct(item.ng, item.total) })}
                            </div>
                            <div className="analytics-chart-wrap">
                              <ResponsiveContainer>
                                <BarChart data={barData} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
                                  <CartesianGrid strokeDasharray="3 3" />
                                  <XAxis dataKey="name" />
                                  <YAxis allowDecimals={false} />
                                  <Tooltip />
                                  <Bar
                                    dataKey="value"
                                    onClick={(data: any) => {
                                      if (data?.payload?.name !== 'NG') return
                                      if (isWinderCategory) {
                                        const w = parseInt(String(item.key), 10)
                                        enterNgMode({ winderNumber: Number.isFinite(w) ? w : null })
                                        return
                                      }
                                      enterNgMode()
                                    }}
                                  >
                                    {barData.map((entry, idx) => (
                                      <Cell
                                        key={`cell-${idx}`}
                                        fill={entry.name === 'NG' ? NG_COLOR : OK_COLOR}
                                      />
                                    ))}
                                  </Bar>
                                </BarChart>
                              </ResponsiveContainer>
                            </div>
                          </div>
                        )
                      })}
                    </div>
                  </div>
                )
              })
            ) : (
              <div className="analytics-empty">{t('analytics.noData')}</div>
            )}
          </section>

        </>
      ) : null}
    </div>
  )
}
