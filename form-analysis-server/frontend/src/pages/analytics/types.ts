import type { DataType } from '../../types/common'

export type RatioNode = {
  '0'?: number
  '1'?: number
  total_count?: number
  count_0?: number
  label?: string
}

export type AnalysisResult = Record<string, Record<string, RatioNode>>

export type StationSelection = {
  p2: boolean
  p3: boolean
  all: boolean
}

export type QueryRecordLite = {
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

export type QueryResponseLite = {
  total_count: number
  page: number
  page_size: number
  records: QueryRecordLite[]
}

export type TraceabilityData = {
  product_id: string
  p3: any
  p2: any
  p1: any
  trace_complete: boolean
  missing_links: string[]
}

// Preset modes are week/month/quarter/half-year; custom supports day-level.
export type RangeMode = 'week' | 'month' | 'quarter' | 'halfYear' | 'custom'

export type ParetoItem = { name: string; value: number }
export type ParetoPoint = { name: string; value: number; cumPct: number }

export const PARETO_ENABLED_DAILY = true
export const PARETO_TOP_N = 12
export const PARETO_CUM_THRESHOLD = 0.8
export const PARETO_MIN_COUNT = 1
export const PARETO_SHOW_ZERO = false
export const PARETO_SOURCE_NG = true
export const PARETO_SOURCE_FEATURE = true

export const OK_COLOR = '#2563eb'
export const NG_COLOR = '#dc2626'
