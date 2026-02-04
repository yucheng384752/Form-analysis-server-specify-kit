import { describe, expect, it } from 'vitest'

import { clampCustomRange, normalizeDayPickerRange } from '../utils/analyticsDateRange'

function ymd(d: Date): string {
  const yyyy = d.getFullYear()
  const mm = String(d.getMonth() + 1).padStart(2, '0')
  const dd = String(d.getDate()).padStart(2, '0')
  return `${yyyy}-${mm}-${dd}`
}

describe('analyticsDateRange', () => {
  it('normalizeDayPickerRange turns single click into single-day range', () => {
    const from = new Date(2025, 8, 1) // 2025-09-01
    const normalized = normalizeDayPickerRange({ from })
    expect(normalized?.from).toBe(from)
    expect(normalized?.to).toBe(from)
  })

  it('clampCustomRange expands too-short ranges to one week', () => {
    const from = new Date(2025, 8, 1) // 2025-09-01
    const to = new Date(2025, 8, 2) // 2025-09-02

    const out = clampCustomRange(from, to)
    expect(ymd(out.start)).toBe('2025-09-01')
    expect(ymd(out.end)).toBe('2025-09-07')
  })
})
