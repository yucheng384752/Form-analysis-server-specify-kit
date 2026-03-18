import { describe, expect, it } from 'vitest'

import { buildParetoSeries, pct, round3, toCumsumSeries } from './utils'
import type { ParetoItem } from './types'

// ==========================================================================
// pct — 百分比計算
// ==========================================================================
describe('pct', () => {
  it('計算正確的百分比（保留一位小數）', () => {
    expect(pct(3, 10)).toBe(30)
    expect(pct(1, 3)).toBe(33.3)
  })

  it('分母為 0 時回傳 0', () => {
    expect(pct(5, 0)).toBe(0)
  })

  it('分子為 0 時回傳 0', () => {
    expect(pct(0, 100)).toBe(0)
  })
})

// ==========================================================================
// round3 — 三位小數四捨五入
// ==========================================================================
describe('round3', () => {
  it('四捨五入至三位小數', () => {
    expect(round3(1.23456)).toBe(1.235)
    expect(round3(0.1)).toBe(0.1)
    expect(round3(100)).toBe(100)
  })
})

// ==========================================================================
// toCumsumSeries — 累積百分比序列
// ==========================================================================
describe('toCumsumSeries', () => {
  it('計算累積百分比', () => {
    const items = [
      { name: 'A', pct: 40 },
      { name: 'B', pct: 30 },
      { name: 'C', pct: 20 },
      { name: 'D', pct: 10 },
    ]
    const result = toCumsumSeries(items)
    expect(result).toHaveLength(4)
    expect(result[0].cumPct).toBe(40)
    expect(result[1].cumPct).toBe(70)
    expect(result[2].cumPct).toBe(90)
    expect(result[3].cumPct).toBe(100)
  })

  it('空陣列回傳空', () => {
    expect(toCumsumSeries([])).toEqual([])
  })

  it('累積值不超過 100', () => {
    const items = [
      { name: 'X', pct: 60 },
      { name: 'Y', pct: 60 },
    ]
    const result = toCumsumSeries(items)
    expect(result[1].cumPct).toBeLessThanOrEqual(100)
  })
})

// ==========================================================================
// buildParetoSeries — Pareto 資料轉換（核心函式）
// ==========================================================================
describe('buildParetoSeries', () => {
  const sampleItems: ParetoItem[] = [
    { name: 'short_circuit', value: 30 },
    { name: 'open_circuit', value: 20 },
    { name: 'impedance', value: 10 },
    { name: 'solder_bridge', value: 8 },
    { name: 'other', value: 2 },
  ]

  it('依照 value 降序排列', () => {
    const result = buildParetoSeries(sampleItems, {})
    expect(result[0].name).toBe('short_circuit')
    expect(result[1].name).toBe('open_circuit')
    expect(result[result.length - 1].name).toBe('other')
  })

  it('計算正確的累積百分比', () => {
    const result = buildParetoSeries(sampleItems, {})
    const total = 30 + 20 + 10 + 8 + 2
    expect(result[0].cumPct).toBeCloseTo((30 / total) * 100, 1)
    expect(result[1].cumPct).toBeCloseTo(((30 + 20) / total) * 100, 1)
    expect(result[result.length - 1].cumPct).toBeCloseTo(100, 0)
  })

  it('topN 限制回傳數量', () => {
    const result = buildParetoSeries(sampleItems, { topN: 3 })
    expect(result).toHaveLength(3)
    expect(result[0].name).toBe('short_circuit')
    expect(result[2].name).toBe('impedance')
  })

  it('cumThreshold 在達到門檻時截斷', () => {
    // short_circuit=30, open_circuit=20 → cum = 50/70 = 71.4%
    // + impedance=10 → cum = 60/70 = 85.7% > 80%
    const items: ParetoItem[] = [
      { name: 'A', value: 30 },
      { name: 'B', value: 20 },
      { name: 'C', value: 10 },
      { name: 'D', value: 5 },
      { name: 'E', value: 5 },
    ]
    const result = buildParetoSeries(items, { cumThreshold: 0.8 })
    // A=30/70=42.9%, A+B=50/70=71.4%, A+B+C=60/70=85.7% ≥ 80% → 截斷
    expect(result).toHaveLength(3)
  })

  it('空陣列回傳空', () => {
    expect(buildParetoSeries([], {})).toEqual([])
  })

  it('過濾掉空名稱的項目', () => {
    const items: ParetoItem[] = [
      { name: '', value: 10 },
      { name: 'valid', value: 5 },
    ]
    const result = buildParetoSeries(items, {})
    expect(result).toHaveLength(1)
    expect(result[0].name).toBe('valid')
  })

  it('value 為 0 時預設被過濾（showZero=false）', () => {
    const items: ParetoItem[] = [
      { name: 'A', value: 10 },
      { name: 'B', value: 0 },
    ]
    const result = buildParetoSeries(items, { minValue: 1 })
    expect(result).toHaveLength(1)
  })

  it('minValue 過濾小於門檻的項目', () => {
    const items: ParetoItem[] = [
      { name: 'A', value: 10 },
      { name: 'B', value: 3 },
      { name: 'C', value: 1 },
    ]
    const result = buildParetoSeries(items, { minValue: 3 })
    expect(result).toHaveLength(2)
  })

  it('name 有空白時應被 trim', () => {
    const items: ParetoItem[] = [
      { name: '  trimmed  ', value: 5 },
    ]
    const result = buildParetoSeries(items, {})
    expect(result[0].name).toBe('trimmed')
  })

  it('value 為 NaN 或 undefined 時被視為 0', () => {
    const items = [
      { name: 'A', value: NaN },
      { name: 'B', value: undefined as unknown as number },
      { name: 'C', value: 5 },
    ]
    const result = buildParetoSeries(items, { minValue: 1 })
    expect(result).toHaveLength(1)
    expect(result[0].name).toBe('C')
  })

  // 模擬前端實際使用場景：從 analysisResult 的 count_0 建立 NG Pareto
  it('模擬 NG Pareto 場景：count_0 資料轉換', () => {
    // 模擬 analysisResult['P2.NG_code'] 的 count_0 欄位
    const ngCodeData: Record<string, { count_0: number }> = {
      'short_circuit': { count_0: 30 },
      'open_circuit': { count_0: 20 },
      'impedance_out_of_spec': { count_0: 10 },
      'solder_bridge': { count_0: 5 },
    }

    // 前端 ngParetoData useMemo 的轉換邏輯
    const paretoItems: ParetoItem[] = Object.entries(ngCodeData).map(
      ([name, data]) => ({ name, value: data.count_0 }),
    )

    const result = buildParetoSeries(paretoItems, {
      topN: 12,
      cumThreshold: 0.8,
      minValue: 1,
    })

    expect(result.length).toBeGreaterThan(0)
    expect(result[0].name).toBe('short_circuit')
    expect(result[0].value).toBe(30)
    // cumPct 應遞增
    for (let i = 1; i < result.length; i++) {
      expect(result[i].cumPct).toBeGreaterThanOrEqual(result[i - 1].cumPct)
    }
  })

  // 模擬 Feature Pareto 場景：final_raw_score 資料轉換
  it('模擬 Feature Pareto 場景：final_raw_score 資料轉換', () => {
    const finalRawScore: Record<string, number> = {
      'Semi-finished impedance': 1.17,
      'Heat gun temperature': 0.83,
      'Slitting speed': 0.45,
    }

    const paretoItems: ParetoItem[] = Object.entries(finalRawScore).map(
      ([name, value]) => ({ name, value }),
    )

    const result = buildParetoSeries(paretoItems, { topN: 12 })

    expect(result).toHaveLength(3)
    expect(result[0].name).toBe('Semi-finished impedance')
    expect(result[0].value).toBe(1.17)
    expect(result[result.length - 1].cumPct).toBeCloseTo(100, 0)
  })
})
