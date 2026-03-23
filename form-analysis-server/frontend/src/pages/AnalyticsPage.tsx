import { ParetoChart } from '../components/analytics/ParetoChart'
import { useCallback, useEffect, useMemo, useRef, useState, type KeyboardEventHandler } from 'react'
import { useTranslation } from 'react-i18next'
import { DayPicker, type DateRange } from 'react-day-picker'
import { endOfMonth, endOfWeek, format, startOfMonth, startOfWeek } from 'date-fns'
import { enUS, zhTW } from 'date-fns/locale'
import { ResponsiveContainer, Pie, PieChart, Cell, Tooltip, Legend, ComposedChart, BarChart, Bar, Line, XAxis, YAxis, CartesianGrid } from 'recharts'
import { getTenantId } from '../services/tenant'
import { getTenantLabelById, writeTenantMap } from '../services/tenantMap'
import { clampCustomRange, normalizeDayPickerRange } from '../utils/analyticsDateRange'
import { ArtifactsView, type ViewKey } from '../components/analytics/ArtifactsView'

import './../styles/analytics-page.css'
import 'react-day-picker/dist/style.css'

type RatioNode = {
  '0'?: number
  '1'?: number
  total_count?: number
  count_0?: number
  label?: string
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

function extractProduceNosFromTrace(data: TraceabilityData | null): string[] {
  if (!data || !data.p3 || typeof data.p3 !== 'object') return []

  const out: string[] = []
  const seen = new Set<string>()
  const push = (value: unknown) => {
    const s = String(value ?? '').trim()
    if (!s) return
    const key = s.toLowerCase()
    if (seen.has(key)) return
    seen.add(key)
    out.push(s)
  }

  const p3: any = data.p3
  const rows = p3?.additional_data?.rows
  if (Array.isArray(rows)) {
    for (const row of rows) {
      if (!row || typeof row !== 'object') continue
      const r: any = row
      push(r['Produce_No.'])
      push(r['Produce_No'])
      push(r['produce_no'])
      push(r['P3_No.'])
      if (out.length >= 10) break
    }
  }

  return out
}

type TenantRow = {
  id: string
  name?: string
  code?: string
}


// Preset modes are week/month/quarter/half-year; custom supports day-level.
type RangeMode = 'week' | 'month' | 'quarter' | 'halfYear' | 'custom'

function parseProductIds(input: string): string[] {
  const normalizeProductId = (value: string): string => {
    const s = value.trim()
    if (!s) return s

    // Screenshot format examples:
    //   250902-P24-2382-301
    // Desired DB/CSV format:
    //   20250902_P24_238-2_301
    const m = s.match(/^([0-9]{6})-(P[0-9]{2})-([0-9]{4})-([0-9]{3})$/i)
    if (m) {
      const yymmdd = m[1]
      const station = m[2].toUpperCase()
      const film = m[3]
      const seq = m[4]

      const yyyy = `20${yymmdd.slice(0, 2)}`
      const mm = yymmdd.slice(2, 4)
      const dd = yymmdd.slice(4, 6)
      const yyyymmdd = `${yyyy}${mm}${dd}`

      // film: 2382 -> 238-2
      const filmFmt = `${film.slice(0, 3)}-${film.slice(3)}`

      return `${yyyymmdd}_${station}_${filmFmt}_${seq}`
    }

    return s
  }

  const raw = input
    .split(/[\s,，;；]+/g)
    .map((s) => normalizeProductId(s))
    .filter(Boolean)
  const uniq: string[] = []
  const seen = new Set<string>()
  for (const x of raw) {
    const key = x.toLowerCase()
    if (seen.has(key)) continue
    seen.add(key)
    uniq.push(x)
    if (uniq.length >= 50) break
  }
  return uniq
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
  let missingSkipped = 0
  for (const [category, bucket] of Object.entries(input)) {
    if (!isPlainObject(bucket)) continue
    const inner: Record<string, RatioNode> = {}
    for (const [key, rawNode] of Object.entries(bucket)) {
      if (key === '__MISSING__') { missingSkipped++; continue }
      if (!isPlainObject(rawNode)) continue
      const node = rawNode as RatioNode
      inner[key] = node
    }
    if (Object.keys(inner).length > 0) result[category] = inner
  }
  if (missingSkipped > 0) {
    console.log(`[Analytics] 過濾掉 __MISSING__ 分類：${missingSkipped} 個`)
  }
  console.log('[Analytics] normalizeAnalysisResult → 分類數:', Object.keys(result).length, '分類列表:', Object.keys(result))
  return Object.keys(result).length > 0 ? result : null
}


function pickOverallNode(result: AnalysisResult): { category: string; key: string; node: RatioNode } | null {
  let bestCategory: string | null = null
  let bestTotal = -1
  let bestNg = -1
  const summary: Record<string, { total: number; ng: number; keyCount: number }> = {}
  for (const [category, bucket] of Object.entries(result)) {
    let catTotal = 0
    let catNg = 0
    for (const node of Object.values(bucket)) {
      catTotal += Number(node?.total_count ?? 0) || 0
      catNg += Number(node?.count_0 ?? 0) || 0
    }
    summary[category] = { total: catTotal, ng: catNg, keyCount: Object.keys(bucket).length }
    if (catTotal > bestTotal || (catTotal === bestTotal && catNg > bestNg)) {
      bestCategory = category
      bestTotal = catTotal
      bestNg = catNg
    }
  }
  console.log('[Analytics] pickOverallNode 各分類彙總:', summary)
  console.log(`[Analytics] pickOverallNode → 最佳分類: "${bestCategory}", total=${bestTotal}, NG=${bestNg}, NG率=${bestTotal ? ((bestNg / bestTotal) * 100).toFixed(2) : 0}%`)
  if (!bestCategory) return null
  const syntheticNode: RatioNode = { total_count: bestTotal, count_0: bestNg }
  return { category: bestCategory, key: '__all__', node: syntheticNode }
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

type ParetoItem = { name: string; value: number }
type ParetoPoint = { name: string; value: number; cumPct: number }

const PARETO_ENABLED_DAILY = true
const PARETO_TOP_N = 12
const PARETO_CUM_THRESHOLD = 0.8
const PARETO_MIN_COUNT = 1
const PARETO_SHOW_ZERO = false
const PARETO_SOURCE_NG = true
const PARETO_SOURCE_FEATURE = true

const DEMO_PARETO_OVERRIDE = true
const DEMO_FINAL_RAW_SCORE: Record<string, number> = {
  'Thicknessss Low(μm)': 7.492635216665868,
  'Thicknessss High(μm)': 0.5006222690021331,
  'Slitting speed': 0.0,
  'Thickness diff': 1.8353439288498945,
  'Rubber wheel gasket thickness (in)': 0.07496027169079686,
  'Rubber wheel gasket thickness (out)': 2.4980288594561424,
  Appearance: 0.0,
  'Board Width(mm)': 5.056269841777992,
  'Semi-finished impedance': 3.9463953680202946,
  'Heat gun temperature': 0.060940332260790625,
  'Rewind torque': 0.0,
}

function buildParetoSeries(
  items: ReadonlyArray<ParetoItem>,
  options: {
    topN?: number
    cumThreshold?: number
    minValue?: number
    showZero?: boolean
  }
): ParetoPoint[] {
  const minValue = options.minValue ?? 0
  const showZero = options.showZero ?? false
  const topN = options.topN
  const cumThreshold = options.cumThreshold

  const filtered = items
    .map((item) => ({
      name: String(item.name || '').trim(),
      value: Number(item.value) || 0,
    }))
    .filter((item) => item.name && (showZero ? item.value >= minValue : item.value >= minValue))
    .sort((a, b) => b.value - a.value)

  if (filtered.length === 0) return []

  const total = filtered.reduce((acc, item) => acc + item.value, 0) || 0
  let running = 0
  const out: ParetoPoint[] = []
  for (const item of filtered) {
    running += item.value
    const cumPct = total > 0 ? round3((running / total) * 100) : 0
    out.push({ name: item.name, value: item.value, cumPct })
    if (topN && out.length >= topN) break
    if (cumThreshold && total > 0 && running / total >= cumThreshold) break
  }

  return out
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
    // For horizontal bars, reserve space for long X-axis labels.
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
    // Default behavior: date-based analysis auto-run. product_id input switches to manual run.
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
    // 清除日期時不觸發 auto-run，避免查詢所有資料
    autoRunArmedRef.current = false
    setStartDate('')
    setEndDate('')
    setAnchorDate(undefined)
    setCustomRange(undefined)
    // Keep complaint(product_id)-driven state untouched.
    // Date clear should only reset date-mode outputs.
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

    // Single-day selection stays day-level (no forced expansion).
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
    let bucket: Record<string, RatioNode> | null = null
    for (const key of candidates) {
      const entry = analysisResult[key]
      if (entry && typeof entry === 'object') {
        bucket = entry as Record<string, RatioNode>
        break
      }
    }
    if (!bucket) return []
    const items: ParetoItem[] = Object.entries(bucket)
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
    if (!PARETO_ENABLED_DAILY || !PARETO_SOURCE_FEATURE) return [] as ParetoPoint[]
    const source = DEMO_PARETO_OVERRIDE ? DEMO_FINAL_RAW_SCORE : extractionData?.final_raw_score
    if (!source || Object.keys(source).length === 0) return [] as ParetoPoint[]
    const items: ParetoItem[] = Object.entries(source).map(
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
    // Date analysis key should not depend on product_id; product_id uses manual run.
    return JSON.stringify({ startDate, endDate, stations })
  }, [startDate, endDate, stations])

  const handleRun = useCallback((_opts?: { productIdOverride?: string }) => {
    void (async () => {
      setParseError('')
      setIsLoading(true)
      setNgMode(false)
      setNgRecords([])
      setNgError('')
      
      // Race condition prevention: increment request ID and capture it
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

        // Race condition check: ignore stale responses
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
      // Use user-selected stations instead of hardcoded P2
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

          // Keep NG query date-based; product_id is handled via manual run.

          // winder_number filter only applies to P2
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

          // P2 uses slitting_result, P3 uses Finish for NG detection
          if (dt === 'P2') {
            try {
              // Prefer materialized column for better index usage.
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
              // Backward-compatible fallback for older backends.
              return await queryDynamic([
                ...baseFilters,
                { field: 'row_data.Striped Results', op: 'eq', value: 0 },
              ])
            }
          } else if (dt === 'P3') {
            // P3 uses Finish field for NG (0 = NG)
            try {
              return await queryDynamic([
                ...baseFilters,
                { field: 'row_data.Finish', op: 'eq', value: 0 },
              ])
            } catch (e) {
              const msg = String(e)
              // Try lowercase variant if needed
              if (msg.includes('Invalid') || msg.includes('Unsupported')) {
                return await queryDynamic([
                  ...baseFilters,
                  { field: 'row_data.finish', op: 'eq', value: 0 },
                ])
              }
              throw e
            }
          }
          
          // Fallback: return empty result for unknown data type
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
            <textarea
              ref={productIdTextareaRef}
              className="register-input analytics-product-textarea"
              rows={1}
              placeholder="輸入 產品編號（可多筆，以逗號/空白/換行分隔）→ 觸發 分析"
              value={productIdDraft}
              onChange={(e) => {
                setProductIdDraft(e.target.value)
                // Keep height in sync for immediate feedback.
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
        <>
          <div className="analytics-section-header">{t('analytics.ngOnlyTitle')}{ngWinderNumber ? ` · W${ngWinderNumber}` : ''}</div>

          <section className="analytics-card">
            <div className="analytics-actions" style={{ justifyContent: 'space-between', marginTop: 0 }}>
              <button type="button" className="btn-secondary" onClick={exitNgMode}>
                {t('analytics.backToAnalysis')}
              </button>

              <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                {ngWinderNumber !== null ? (
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

            {ngError ? <div className="analytics-error">{ngError}</div> : null}

            {PARETO_ENABLED_DAILY ? (
              <div style={{ marginBottom: 16 }}>
                <div
                  style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
                    gap: 12,
                  }}
                >
                  {PARETO_SOURCE_NG ? (
                    ngParetoData.length > 0 ? (
                      <ParetoChart
                        title="NG Pareto (count_0)"
                        data={ngParetoData}
                        valueLabel="NG數量"
                        cumLabel="累積%"
                      />
                    ) : (
                      <div className="analytics-empty">NG Pareto 暫無資料</div>
                    )
                  ) : null}

                  {PARETO_SOURCE_FEATURE ? (
                    extractionLoading ? (
                      <div className="analytics-empty">{t('analytics.loading')} (Feature Pareto)</div>
                    ) : featureParetoData.length > 0 ? (
                      <ParetoChart
                        title="Feature Pareto (final_raw_score)"
                        data={featureParetoData}
                        valueLabel="Final Score"
                        cumLabel="累積%"
                      />
                    ) : (
                      <div className="analytics-empty">Feature Pareto 暫無資料</div>
                    )
                  ) : null}
                </div>

                {PARETO_SOURCE_FEATURE && extractionData ? (
                  <details style={{ marginTop: 8 }}>
                    <summary style={{ cursor: 'pointer', fontSize: '0.85rem', color: '#666' }}>
                      {t('analytics.viewDetails')}
                    </summary>
                    <table style={{ width: '100%', fontSize: '0.82rem', borderCollapse: 'collapse', marginTop: 4 }}>
                      <thead>
                        <tr style={{ borderBottom: '1px solid #ddd' }}>
                          <th style={{ textAlign: 'left', padding: '4px 8px' }}>Feature</th>
                          <th style={{ textAlign: 'right', padding: '4px 8px' }}>Boundary</th>
                          <th style={{ textAlign: 'right', padding: '4px 8px' }}>SPE</th>
                          <th style={{ textAlign: 'right', padding: '4px 8px' }}>T²</th>
                          <th style={{ textAlign: 'right', padding: '4px 8px' }}>Final</th>
                        </tr>
                      </thead>
                      <tbody>
                        {Object.entries(extractionData.final_raw_score).map(([name, score]) => (
                          <tr key={name} style={{ borderBottom: '1px solid #eee' }}>
                            <td style={{ padding: '3px 8px' }}>{name}</td>
                            <td style={{ textAlign: 'right', padding: '3px 8px' }}>{extractionData.boundary_count[name] ?? 0}</td>
                            <td style={{ textAlign: 'right', padding: '3px 8px' }}>{round3(extractionData.spe_score[name] ?? 0)}</td>
                            <td style={{ textAlign: 'right', padding: '3px 8px' }}>{round3(extractionData.t2_score[name] ?? 0)}</td>
                            <td style={{ textAlign: 'right', padding: '3px 8px', fontWeight: 600 }}>{round3(score)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </details>
                ) : null}
              </div>
            ) : null}

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

            {ngFeaturePctEntries.length > 0 ? (
              <div className="analytics-ng-feature-chart" aria-label={t('analytics.featurePct.title')} style={{ marginTop: 16 }}>
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
          </section>
        </>
      ) : ran ? (
        <>
          <div className="analytics-section-header">{t('analytics.moldingAnalysis')}</div>

          {/* OK/NG 圓餅圖 */}
          {overall.total > 0 ? (
            <section className="analytics-card" style={{ marginBottom: 16 }}>
              <h4 style={{ margin: '0 0 8px', fontWeight: 600 }}>
                OK / NG ({overall.total} {t('analytics.totalRecords', 'pcs')})
              </h4>
              <div style={{ width: '100%', height: 260, display: 'flex', justifyContent: 'center' }}>
                <ResponsiveContainer width={360} height="100%">
                  <PieChart>
                    <Pie
                      data={pieData}
                      dataKey="value"
                      nameKey="name"
                      cx="50%"
                      cy="50%"
                      outerRadius={90}
                      label={({ name }) => `${name}`}
                    >
                      {pieData.map((_, i) => (
                        <Cell key={i} fill={colors[i % colors.length]} />
                      ))}
                    </Pie>
                    <Tooltip formatter={(value) => [value ?? 0, '']} />
                    <Legend />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            </section>
          ) : null}

          <section className="analytics-card">
            <div className="analytics-actions" style={{ justifyContent: 'flex-start', marginTop: 0, gap: 8 }}>
              {!productIdMode ? (
                <button
                  type="button"
                  className={analysisChartMode === 'heatmap' ? 'btn-primary' : 'btn-secondary'}
                  onClick={() => setAnalysisChartMode('heatmap')}
                >
                  {t('analytics.views.heatmap')}
                </button>
              ) : null}
              <button
                type="button"
                className={analysisChartMode === 'bar' ? 'btn-primary' : 'btn-secondary'}
                onClick={() => setAnalysisChartMode('bar')}
              >
                {t('analytics.views.bar')}
              </button>
            </div>

            {!productIdMode && analysisChartMode === 'heatmap' ? (
              analysisHeatmapRows.length > 0 ? (
                <div className="analytics-heatmap">
                  <div className="analytics-heatmap-head">
                    <div>{t('analytics.heatmap.category')}</div>
                    <div>{t('analytics.heatmap.value')}</div>
                    <div>{t('analytics.heatmap.ngRate')}</div>
                    <div>{t('analytics.heatmap.sample')}</div>
                  </div>
                  {analysisHeatmapRows.map((row) => (
                    <div
                      key={`${row.category}:${row.key}`}
                      className="analytics-heatmap-row"
                      style={{ background: heatColor(row.ngRate) }}
                    >
                      <div title={row.category}>{row.category}</div>
                      <div title={row.key}>{row.key}</div>
                      <div>{pct(row.ng, row.total)}%</div>
                      <div>{row.total}</div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="analytics-empty">{t('analytics.noData')}</div>
              )
            ) : null}

            {analysisChartMode === 'bar' ? (
            categoryCards.length > 0 ? (
              categoryCards.map((cat) => {
                const title = cat.category
                const isWinderCategory = /winder/i.test(String(title))
                if (productIdMode) {
                  const barData = cat.items
                    .map((item) => ({ name: item.label, count: item.total }))
                    .filter((item) => item.name)
                    .sort((a, b) => b.count - a.count)
                  const maxCount = barData.reduce((acc, item) => Math.max(acc, item.count), 0)
                  return (
                    <div key={cat.category} style={{ marginBottom: '1.5rem' }}>
                      <div className="analytics-card-title">{title}</div>
                      {barData.length > 0 ? (
                        <div className="analytics-chart-wrap" style={{ height: 260, minHeight: 260, marginTop: '0.75rem' }}>
                          <ResponsiveContainer width="100%" height={260}>
                            <BarChart data={barData} margin={{ top: 10, right: 20, left: 0, bottom: 60 }}>
                              <CartesianGrid strokeDasharray="3 3" />
                              <XAxis dataKey="name" interval={0} angle={-20} height={60} textAnchor="end" />
                              <YAxis allowDecimals={false} />
                              <Tooltip />
                              <Bar dataKey="count">
                                {barData.map((entry, idx) => (
                                  <Cell
                                    key={`cell-${idx}`}
                                    fill={entry.count === maxCount ? '#dc2626' : '#2563eb'}
                                  />
                                ))}
                              </Bar>
                            </BarChart>
                          </ResponsiveContainer>
                        </div>
                      ) : (
                        <div className="analytics-empty">{t('analytics.noData')}</div>
                      )}
                    </div>
                  )
                }
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
                            <div className="analytics-chart-wrap" style={{ height: 220, minHeight: 220 }}>
                              <ResponsiveContainer width="100%" height={220}>
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
                                    const winderNumber = parseWinderCategoryKey(item.key)
                                    if (winderNumber === null) return
                                    enterNgMode({ winderNumber })
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
            )
            ) : null}

            {winderChartData.length > 0 ? (
              <div style={{ marginTop: '1.5rem' }}>
                <div className="analytics-card-title">Winder Number 累積直方圖</div>
                <div className="analytics-chart-wrap" style={{ height: 280, minHeight: 280, marginTop: '0.75rem' }}>
                  <ResponsiveContainer width="100%" height={280}>
                    <ComposedChart data={winderChartData} margin={{ top: 10, right: 40, left: 0, bottom: 60 }}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="name" interval={0} angle={-20} height={60} textAnchor="end" />
                      <YAxis yAxisId="left" allowDecimals={false} />
                      <YAxis yAxisId="right" orientation="right" domain={[0, 100]} tickFormatter={(v: number) => `${v}%`} />
                      <Tooltip
                        formatter={(value: any, name: any) => {
                          if (name === '累積%') return [`${round3(Number(value)).toFixed(1)}%`, name]
                          return [value, name]
                        }}
                      />
                      <Legend />
                      <Bar yAxisId="left" dataKey="count" name="NG數量" fill="#2563eb" radius={[6, 6, 0, 0]} />
                      <Line yAxisId="right" dataKey="cumPct" name="累積%" type="monotone" stroke="#ef4444" strokeWidth={2} dot={{ r: 2 }} />
                    </ComposedChart>
                  </ResponsiveContainer>
                </div>
              </div>
            ) : null}
          </section>

        </>
      ) : null}
    </div>
  )
}
