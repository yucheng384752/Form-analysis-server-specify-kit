import type { DateRange } from 'react-day-picker'

export const MIN_CUSTOM_RANGE_DAYS = 7
export const MAX_CUSTOM_RANGE_DAYS = 184 // approx half-year

export function addDays(date: Date, days: number): Date {
  const d = new Date(date)
  d.setDate(d.getDate() + days)
  return d
}

export function clampCustomRange(from: Date, to: Date): { start: Date; end: Date } {
  const start = new Date(from)
  const end = new Date(to)

  // Normalize order
  if (end.getTime() < start.getTime()) {
    return clampCustomRange(end, start)
  }

  const diffDays = Math.floor((end.getTime() - start.getTime()) / (24 * 60 * 60 * 1000)) + 1
  if (diffDays < MIN_CUSTOM_RANGE_DAYS) {
    return { start, end: addDays(start, MIN_CUSTOM_RANGE_DAYS - 1) }
  }
  if (diffDays > MAX_CUSTOM_RANGE_DAYS) {
    return { start, end: addDays(start, MAX_CUSTOM_RANGE_DAYS - 1) }
  }
  return { start, end }
}

export function normalizeDayPickerRange(range: DateRange | undefined): DateRange | undefined {
  if (!range?.from) return undefined
  if (!range.to) return { from: range.from, to: range.from }
  return range
}
