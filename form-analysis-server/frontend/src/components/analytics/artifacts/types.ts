import type { ArtifactKey } from '../../../services/analyticsArtifacts'

export type ViewKey = 'events' | 'aggregated' | 'rag' | 'llm' | 'weighted'

export const VIEW_TO_ARTIFACT: Record<ViewKey, ArtifactKey> = {
  events: 'serialized_events',
  aggregated: 'aggregated_diagnostics',
  rag: 'rag_results',
  llm: 'llm_reports',
  weighted: 'weighted_contributions',
}

export function isPlainObject(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value)
}

export function toStr(value: unknown): string {
  if (value === null || value === undefined) return ''
  return String(value)
}

export function safeNumber(value: unknown): number {
  const n = typeof value === 'number' ? value : Number(value)
  return Number.isFinite(n) ? n : 0
}

export function isNumberLike(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value)
}

export function pickOutlierLabel(row: Record<string, unknown>): string {
  const keys = ['feature', 'column', 'name', 'dimension', 'id', 'key']
  for (const k of keys) {
    const v = row[k]
    if (typeof v === 'string' && v.trim()) return v.trim()
  }
  return ''
}

export function extractOutlierCounts(raw: unknown): Array<{ name: string; count: number }> {
  if (!raw) return []
  const candidates: Array<{ name: string; count: number }> = []

  const pushEntry = (name: string, count: number) => {
    const n = String(name || '').trim()
    if (!n) return
    const c = Number(count)
    candidates.push({ name: n, count: Number.isFinite(c) ? c : 0 })
  }

  if (Array.isArray(raw)) {
    for (const item of raw) {
      if (!isPlainObject(item)) continue
      const label = pickOutlierLabel(item)
      const count = isNumberLike(item.count) ? item.count : 1
      pushEntry(label, count)
    }
  } else if (isPlainObject(raw)) {
    const nestedKeys = ['outliers', 'result', 'data', 'records', 'rows']
    for (const k of nestedKeys) {
      if (raw[k]) {
        return extractOutlierCounts(raw[k])
      }
    }
    for (const [key, value] of Object.entries(raw)) {
      if (isNumberLike(value)) {
        pushEntry(key, value)
        continue
      }
      if (Array.isArray(value)) {
        pushEntry(key, value.length)
        continue
      }
      if (isPlainObject(value)) {
        const label = pickOutlierLabel(value)
        const count = isNumberLike(value.count) ? value.count : undefined
        if (label && count !== undefined) {
          pushEntry(label, count)
        } else if (count !== undefined) {
          pushEntry(key, count)
        }
      }
    }
  }

  const byName = new Map<string, number>()
  for (const row of candidates) {
    byName.set(row.name, (byName.get(row.name) ?? 0) + row.count)
  }
  return [...byName.entries()]
    .map(([name, count]) => ({ name, count }))
    .sort((a, b) => b.count - a.count)
}

export function extractBasicStatsTopN(
  raw: unknown,
  topN = 8,
  preferMetric: 'std' | 'mean' = 'std',
): Array<{ name: string; value: number; metric: string }> {
  if (!isPlainObject(raw)) return []
  const rows: Array<{ name: string; value: number; metric: string }> = []
  for (const [key, value] of Object.entries(raw)) {
    if (!isPlainObject(value)) continue
    const stats = value as Record<string, unknown>
    const std = stats.std ?? stats.stdev ?? stats.std_dev
    const mean = stats.mean ?? stats.avg ?? stats.average
    const max = stats.max
    const min = stats.min
    if (preferMetric === 'mean' && isNumberLike(mean)) {
      rows.push({ name: key, value: Number(mean), metric: 'mean' })
      continue
    }
    if (isNumberLike(std)) {
      rows.push({ name: key, value: Number(std), metric: 'std' })
      continue
    }
    if (isNumberLike(max) && isNumberLike(min)) {
      rows.push({ name: key, value: Math.abs(Number(max) - Number(min)), metric: 'range' })
      continue
    }
    if (isNumberLike(mean)) {
      rows.push({ name: key, value: Number(mean), metric: 'mean' })
    }
  }
  return rows.sort((a, b) => b.value - a.value).slice(0, topN)
}

export function tryParseIsoDate(value: unknown): Date | null {
  const s = String(value ?? '').trim()
  if (!s) return null
  const d = new Date(s)
  return Number.isFinite(d.getTime()) ? d : null
}

export function formatIsoPreview(value: unknown): string {
  const d = tryParseIsoDate(value)
  if (!d) return ''
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  const hh = String(d.getHours()).padStart(2, '0')
  const mm = String(d.getMinutes()).padStart(2, '0')
  return `${y}-${m}-${day} ${hh}:${mm}`
}

export function pickId(item: unknown): string {
  if (!isPlainObject(item)) return ''
  const candidates = ['event_id', 'summary_id', 'id', 'eventId', 'summaryId']
  for (const k of candidates) {
    const v = item[k]
    if (typeof v === 'string' && v.trim()) return v.trim()
  }
  return ''
}

// ===== Row types used by sub-views =====

export type EventRow = {
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

export type AggRow = {
  summary_id: string
  analysis_dimension: string
  sample_count: number
  context_preview: string
  core_feature_count: number
  event_count: number
}

export type CoreFeatureSummary = {
  feature: string
  iqr_freq: number
  t2_freq: number
  spe_freq: number
  total: number
}

export type WeightedItem = {
  id: string
  x_T2: number
  x_SPE: number
  t2_top: string
  spe_top: string
}

export type RagEvent = {
  event_id: string
  feature_count: number
  sop_count: number
}

export type LlmListItem = {
  event_id: string
  event_time_raw: unknown
  event_time: Date | null
  total_anomalies: number
}
