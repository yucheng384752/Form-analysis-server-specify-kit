import { endOfMonth, endOfWeek, format, startOfMonth, startOfWeek } from 'date-fns'
import type { AnalysisResult, ParetoItem, ParetoPoint, RangeMode, RatioNode, TraceabilityData } from './types'

export function extractProduceNosFromTrace(data: TraceabilityData | null): string[] {
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

export function parseProductIds(input: string): string[] {
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

export function toYmd(date: Date): string {
  return format(date, 'yyyy-MM-dd')
}

export function getHalfYearBounds(date: Date): { start: Date; end: Date } {
  const year = date.getFullYear()
  const month = date.getMonth() // 0-11
  if (month < 6) {
    return { start: new Date(year, 0, 1), end: new Date(year, 6, 0) }
  }
  return { start: new Date(year, 6, 1), end: new Date(year + 1, 0, 0) }
}

export function getQuarterBounds(date: Date): { start: Date; end: Date } {
  const year = date.getFullYear()
  const month = date.getMonth() // 0-11
  const quarterStartMonth = Math.floor(month / 3) * 3
  return {
    start: new Date(year, quarterStartMonth, 1),
    end: new Date(year, quarterStartMonth + 3, 0),
  }
}

export function getModeBounds(mode: Exclude<RangeMode, 'custom'>, anchor: Date): { start: Date; end: Date } {
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

export function getIsoWeekYear(date: Date): number {
  const d = new Date(Date.UTC(date.getFullYear(), date.getMonth(), date.getDate()))
  const day = d.getUTCDay() || 7
  d.setUTCDate(d.getUTCDate() + 4 - day)
  return d.getUTCFullYear()
}

export function getIsoWeekNumber(date: Date): number {
  const d = new Date(Date.UTC(date.getFullYear(), date.getMonth(), date.getDate()))
  const day = d.getUTCDay() || 7
  d.setUTCDate(d.getUTCDate() + 4 - day)
  const yearStart = new Date(Date.UTC(d.getUTCFullYear(), 0, 1))
  const diffDays = Math.floor((d.getTime() - yearStart.getTime()) / (24 * 60 * 60 * 1000)) + 1
  return Math.ceil(diffDays / 7)
}

export function isoWeekStartDate(weekYear: number, weekNumber: number): Date {
  const safeWeek = Math.max(1, Math.min(53, Math.floor(weekNumber || 1)))
  const simple = new Date(Date.UTC(weekYear, 0, 1 + (safeWeek - 1) * 7))
  const dow = simple.getUTCDay() || 7
  const mondayUtc = new Date(simple)
  mondayUtc.setUTCDate(simple.getUTCDate() - dow + 1)
  return new Date(mondayUtc.getUTCFullYear(), mondayUtc.getUTCMonth(), mondayUtc.getUTCDate())
}

export function parseCounts(node: RatioNode | undefined): { ok: number; ng: number; total: number } {
  const total = Math.max(0, Number(node?.total_count ?? 0) || 0)
  const ng = Math.max(0, Number(node?.count_0 ?? 0) || 0)
  const ok = Math.max(0, total - ng)
  return { ok, ng, total }
}

export function isPlainObject(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value)
}

export function normalizeAnalysisResult(input: unknown): AnalysisResult | null {
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

export function pickOverallNode(result: AnalysisResult): { category: string; key: string; node: RatioNode } | null {
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

export function pct(n: number, d: number): number {
  if (!d) return 0
  return Math.round((n / d) * 1000) / 10
}

export function round3(n: number): number {
  return Math.round(n * 1000) / 1000
}

export function toCumsumSeries(items: ReadonlyArray<{ name: string; pct: number }>): Array<{ name: string; pct: number; cumPct: number }> {
  let cum = 0
  return items.map((x) => {
    const pct3 = round3(x.pct)
    cum = Math.min(100, round3(cum + pct3))
    return { name: x.name, pct: pct3, cumPct: cum }
  })
}

export function buildParetoSeries(
  items: ReadonlyArray<ParetoItem>,
  options: {
    topN?: number
    cumThreshold?: number
  }
): ParetoPoint[] {
  const topN = options.topN
  const cumThreshold = options.cumThreshold

  const filtered = items
    .map((item) => ({
      name: String(item.name || '').trim(),
      value: Number(item.value) || 0,
    }))
    .filter((item) => item.name)
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
