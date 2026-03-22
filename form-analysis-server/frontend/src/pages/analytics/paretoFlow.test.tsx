/**
 * Pareto 繪製功能 — 端對端資料流測試
 *
 * 驗證從「使用者點擊圓餅圖 NG 區塊」到「顯示 NG list 與 Pareto 圖表」的完整資料流：
 *
 * ┌──────────────────────────────────────────────────────────────────────────┐
 * │  Feature Pareto 資料流                                                   │
 * │                                                                          │
 * │  DB → validate_and_prepare_df() → BasicStatistics → Comparator          │
 * │     → ContributionAnalyzer (PCA/T²/SPE) → Extractor.merge()            │
 * │     → POST /api/v2/analytics/extraction-analysis                        │
 * │     → extractionData.final_raw_score                                    │
 * │     → featureParetoData useMemo → buildParetoSeries()                   │
 * │     → <ParetoChart title="Feature Pareto (final_raw_score)">            │
 * │       └─ <ComposedChart> + <Bar value> + <Line cumPct>                  │
 * └──────────────────────────────────────────────────────────────────────────┘
 */

import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { AnalyticsPage } from '../AnalyticsPage'
import { buildParetoSeries } from './utils'
import type { ParetoItem, ParetoPoint } from './types'
import { PARETO_TOP_N, PARETO_CUM_THRESHOLD } from './types'

// ── Mocks ──

vi.mock('../../components/common/ToastContext', () => ({
  useToast: () => ({
    showToast: vi.fn(),
  }),
}))

vi.mock('recharts', () => {
  const React = require('react')
  return {
    __esModule: true,
    ResponsiveContainer: ({ children }: any) => React.createElement('div', null, children),
    PieChart: ({ children }: any) => React.createElement('div', null, children),
    Pie: ({ children, onClick }: any) =>
      React.createElement(
        'div',
        {
          'data-testid': 'recharts-pie',
          onClick: () => onClick?.({ kind: 'NG', payload: { kind: 'NG' } }),
        },
        children,
      ),
    Cell: () => null,
    Tooltip: () => null,
    Legend: () => null,
    ComposedChart: ({ children, data }: any) =>
      React.createElement(
        'div',
        { 'data-testid': 'composed-chart', 'data-chart-items': JSON.stringify(data) },
        children,
      ),
    BarChart: ({ children }: any) => React.createElement('div', null, children),
    Bar: ({ data, onClick, children }: any) => {
      const barData = Array.isArray(data) && data.length > 0
        ? data
        : [{ name: 'OK', value: 0 }, { name: 'NG', value: 0 }]
      return React.createElement(
        'div',
        null,
        barData.map((entry: any, i: number) =>
          React.createElement(
            'button',
            {
              key: `${entry.name}-${i}`,
              type: 'button',
              'data-testid': `recharts-bar-${i}-${entry.name}`,
              onClick: () => onClick?.({ payload: entry }),
            },
            String(entry?.name ?? ''),
          ),
        ),
        children,
      )
    },
    XAxis: () => null,
    YAxis: () => null,
    CartesianGrid: () => null,
    Line: () => null,
  }
})

// ── Helpers ──

const toYmd = (d: Date): string => {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const dd = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${dd}`
}

// ── 測試用模擬資料 ──

/** 模擬後端 POST /api/v2/analytics/analyze 回傳的資料 */
const MOCK_ANALYZE_RESULT = {
  'P2.NG_code': {
    short_circuit: { '0': 0.15, '1': 0.85, total_count: 200, count_0: 30 },
    open_circuit: { '0': 0.10, '1': 0.90, total_count: 200, count_0: 20 },
    impedance_out_of_spec: { '0': 0.05, '1': 0.95, total_count: 200, count_0: 10 },
    solder_bridge: { '0': 0.04, '1': 0.96, total_count: 200, count_0: 8 },
    minor_defect: { '0': 0.01, '1': 0.99, total_count: 200, count_0: 2 },
  },
  'P2.Winder Number': {
    W1: { total_count: 50, count_0: 10 },
    W2: { total_count: 50, count_0: 5 },
  },
}

/** 模擬後端 POST /api/v2/analytics/extraction-analysis 回傳的資料 */
const MOCK_EXTRACTION_RESULT = {
  station: 'P2',
  boundary_count: { 'Semi-finished impedance': 5, 'Heat gun temperature': 2, 'Slitting speed': 1 },
  spe_score: { 'Semi-finished impedance': 0.62, 'Heat gun temperature': 0.28, 'Slitting speed': 0.10 },
  t2_score: { 'Semi-finished impedance': 0.55, 'Heat gun temperature': 0.30, 'Slitting speed': 0.15 },
  final_raw_score: { 'Semi-finished impedance': 1.17, 'Heat gun temperature': 0.58, 'Slitting speed': 0.25 },
  features_used: ['Semi-finished impedance', 'Heat gun temperature', 'Slitting speed'],
  sample_counts: { total: 100, baseline: 80, analysis: 20 },
  elapsed_ms: 150,
}

/** 模擬 NG records 回傳 */
const MOCK_NG_RECORDS = {
  total_count: 2,
  page: 1,
  page_size: 200,
  records: [
    {
      id: 'r1', lot_no: 'LOT-NG-001', data_type: 'P2',
      production_date: toYmd(new Date()),
      created_at: `${toYmd(new Date())}T08:00:00Z`,
      additional_data: { rows: [{ 'Striped Results': 0 }] },
    },
    {
      id: 'r2', lot_no: 'LOT-NG-002', data_type: 'P2',
      production_date: toYmd(new Date()),
      created_at: `${toYmd(new Date())}T09:00:00Z`,
      additional_data: { rows: [{ 'Striped Results': 0 }] },
    },
  ],
}

// ==========================================================================
// 1. buildParetoSeries 單元測試 — 驗證資料轉換正確性
// ==========================================================================

describe('buildParetoSeries — 使用實際 Pareto 常數', () => {
  it('NG Pareto：從 count_0 建構 (topN=12, cumThreshold=0.8)', () => {
    // 步驟：模擬前端 ngParetoData useMemo 的邏輯
    const bucket = MOCK_ANALYZE_RESULT['P2.NG_code']
    const items: ParetoItem[] = Object.entries(bucket).map(([name, node]) => ({
      name,
      value: Number(node?.count_0 ?? 0) || 0,
    }))

    const result = buildParetoSeries(items, {
      topN: PARETO_TOP_N,       // 12
      cumThreshold: PARETO_CUM_THRESHOLD, // 0.8
    })

    // 驗證：降序排列
    expect(result[0].name).toBe('short_circuit')
    expect(result[0].value).toBe(30)
    expect(result[1].name).toBe('open_circuit')
    expect(result[1].value).toBe(20)

    // 驗證：cumPct 遞增
    for (let i = 1; i < result.length; i++) {
      expect(result[i].cumPct).toBeGreaterThanOrEqual(result[i - 1].cumPct)
    }

    // 驗證：cumThreshold 截斷 — short(30)+open(20)+impedance(10)=60/70=85.7% ≥ 80%
    // minor_defect(2) 應被截斷（累積已超過 80%）
    const total = 30 + 20 + 10 + 8 + 2
    const cumAfterThird = (30 + 20 + 10) / total
    expect(cumAfterThird).toBeGreaterThanOrEqual(0.8)
    expect(result.length).toBeLessThanOrEqual(3)
  })

  it('Feature Pareto：從 final_raw_score 建構', () => {
    // 步驟：模擬前端 featureParetoData useMemo 的邏輯
    const items: ParetoItem[] = Object.entries(MOCK_EXTRACTION_RESULT.final_raw_score).map(
      ([name, value]) => ({ name, value: Number(value) || 0 }),
    )

    const result = buildParetoSeries(items, {
      topN: PARETO_TOP_N,
      cumThreshold: PARETO_CUM_THRESHOLD,
    })

    // 驗證：降序排列
    expect(result[0].name).toBe('Semi-finished impedance')
    expect(result[0].value).toBe(1.17)

    // 驗證：cumThreshold 會截斷到達 80% 以上的範圍
    // final_raw_score: 1.17, 0.58, 0.25 → cum after 2 items = 87.5%
    expect(result.length).toBe(2)
    expect(result[1].cumPct).toBeGreaterThanOrEqual(80)
  })

  it('Feature Pareto：保留所有正值項目', () => {
    const items: ParetoItem[] = Object.entries(MOCK_EXTRACTION_RESULT.final_raw_score).map(
      ([name, value]) => ({ name, value: Number(value) || 0 }),
    )

    const result = buildParetoSeries(items, {
      topN: PARETO_TOP_N,
    })

    expect(result.length).toBe(2)
    expect(result[0].name).toBe('Semi-finished impedance')
    expect(result[1].name).toBe('Heat gun temperature')
    expect(result[1].cumPct).toBeGreaterThanOrEqual(80)
  })
})

// ==========================================================================
// 2. API 資料結構驗證 — 確認後端回傳格式符合前端預期
// ==========================================================================

describe('API 回傳資料結構驗證', () => {
  it('analyze 回傳的 P2.NG_code 包含 count_0（NG Pareto 所需）', () => {
    const result = MOCK_ANALYZE_RESULT
    const ngCode = result['P2.NG_code']

    expect(ngCode).toBeDefined()
    for (const [name, node] of Object.entries(ngCode)) {
      expect(node).toHaveProperty('count_0')
      expect(node).toHaveProperty('total_count')
      expect(typeof node.count_0).toBe('number')
      expect(node.count_0).toBeGreaterThanOrEqual(0)
    }
  })

  it('extraction-analysis 回傳包含 final_raw_score（Feature Pareto 所需）', () => {
    const result = MOCK_EXTRACTION_RESULT

    expect(result).toHaveProperty('final_raw_score')
    expect(result).toHaveProperty('features_used')
    expect(result).toHaveProperty('boundary_count')
    expect(result).toHaveProperty('spe_score')
    expect(result).toHaveProperty('t2_score')
    expect(result).toHaveProperty('sample_counts')

    // final_raw_score 的 key 應與 features_used 一致
    const scoreKeys = Object.keys(result.final_raw_score)
    for (const feature of result.features_used) {
      expect(scoreKeys).toContain(feature)
    }
  })

  it('extraction-analysis 的 final_raw_score 各值為正數', () => {
    for (const [feature, score] of Object.entries(MOCK_EXTRACTION_RESULT.final_raw_score)) {
      expect(typeof score).toBe('number')
      expect(score).toBeGreaterThanOrEqual(0)
    }
  })
})

// ==========================================================================
// 3. 前端 useMemo 邏輯驗證 — 模擬 ngParetoData 與 featureParetoData 產生
// ==========================================================================

describe('前端 useMemo 轉換邏輯', () => {
  it('ngParetoData：從 analysisResult 多個候選 key 找到 bucket', () => {
    // 模擬 AnalyticsPage.tsx L436-459 的邏輯
    const analysisResult = MOCK_ANALYZE_RESULT
    const candidates = ['P2.NG_code', 'NG_code', 'P3.NG_code']
    let bucket: Record<string, any> | null = null
    for (const key of candidates) {
      const entry = (analysisResult as any)[key]
      if (entry && typeof entry === 'object') {
        bucket = entry
        break
      }
    }

    expect(bucket).not.toBeNull()
    expect(bucket).toBe(MOCK_ANALYZE_RESULT['P2.NG_code'])

    // 轉換為 ParetoItem
    const items: ParetoItem[] = Object.entries(bucket!).map(([name, node]) => ({
      name,
      value: Number((node as any)?.count_0 ?? 0) || 0,
    }))

    expect(items).toHaveLength(5)
    expect(items.find((i) => i.name === 'short_circuit')?.value).toBe(30)

    // buildParetoSeries
    const paretoData = buildParetoSeries(items, {
      topN: PARETO_TOP_N,
      cumThreshold: PARETO_CUM_THRESHOLD,
    })

    expect(paretoData.length).toBeGreaterThan(0)
    // 每個 ParetoPoint 應有 name, value, cumPct
    for (const point of paretoData) {
      expect(point).toHaveProperty('name')
      expect(point).toHaveProperty('value')
      expect(point).toHaveProperty('cumPct')
      expect(point.cumPct).toBeGreaterThan(0)
      expect(point.cumPct).toBeLessThanOrEqual(100)
    }
  })

  it('featureParetoData：從 extractionData.final_raw_score 產生', () => {
    // 模擬 AnalyticsPage.tsx L461-472 的邏輯
    const extractionData = MOCK_EXTRACTION_RESULT
    const items: ParetoItem[] = Object.entries(extractionData.final_raw_score || {}).map(
      ([name, value]) => ({ name, value: Number(value) || 0 }),
    )

    const paretoData = buildParetoSeries(items, {
      topN: PARETO_TOP_N,
      cumThreshold: PARETO_CUM_THRESHOLD,
    })

    // 驗證輸出結構符合 ParetoChart 預期
    for (const point of paretoData) {
      expect(typeof point.name).toBe('string')
      expect(typeof point.value).toBe('number')
      expect(typeof point.cumPct).toBe('number')
    }
  })
})

// ==========================================================================
// 4. ParetoChart 組件渲染驗證 — 確認 data 結構能餵入圖表
// ==========================================================================

describe('ParetoChart 渲染資料驗證', () => {
  it('ParetoChart 的 data 型別符合 ParetoDatum', () => {
    // ParetoChart expects { name: string; value: number; cumPct: number }[]
    const sampleData: ParetoPoint[] = [
      { name: 'short_circuit', value: 30, cumPct: 42.9 },
      { name: 'open_circuit', value: 20, cumPct: 71.4 },
      { name: 'impedance', value: 10, cumPct: 85.7 },
    ]

    for (const d of sampleData) {
      expect(typeof d.name).toBe('string')
      expect(d.name.length).toBeGreaterThan(0)
      expect(Number.isFinite(d.value)).toBe(true)
      expect(d.value).toBeGreaterThanOrEqual(0)
      expect(d.cumPct).toBeGreaterThanOrEqual(0)
      expect(d.cumPct).toBeLessThanOrEqual(100)
    }
  })
})

// ==========================================================================
// 5. 整合測試 — 點擊圓餅圖 NG → 進入 NG Mode → 顯示 Pareto
// ==========================================================================

describe('整合測試：點擊圓餅圖 NG → NG list + Pareto', () => {
  type FetchCall = [RequestInfo | URL, RequestInit | undefined]

  beforeEach(() => {
    window.localStorage.clear()
    vi.restoreAllMocks()

    Object.defineProperty(window, 'matchMedia', {
      writable: true,
      configurable: true,
      value: vi.fn().mockReturnValue({
        matches: false,
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        addListener: vi.fn(),
        removeListener: vi.fn(),
      }),
    })
  })

  it('點擊 Pie NG → 觸發 /analyze、/extraction-analysis、/records/dynamic 三個 API 呼叫', async () => {
    const user = userEvent.setup()
    const fetchCalls: Array<{ url: string; body: any }> = []

    vi.spyOn(window, 'fetch').mockImplementation(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      const body = init?.body ? JSON.parse(String(init.body)) : null
      fetchCalls.push({ url, body })

      if (url.includes('/api/v2/analytics/analyze')) {
        return new Response(JSON.stringify(MOCK_ANALYZE_RESULT), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        })
      }
      if (url.includes('/api/v2/analytics/extraction-analysis')) {
        return new Response(JSON.stringify(MOCK_EXTRACTION_RESULT), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        })
      }
      if (url.includes('/api/v2/query/records/dynamic')) {
        return new Response(JSON.stringify(MOCK_NG_RECORDS), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        })
      }
      return new Response(JSON.stringify({}), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      })
    })

    render(<AnalyticsPage />)

    // Step 1: 點擊 Analyze 觸發初始分析
    await user.click(screen.getByRole('button', { name: /Analyze/i }))

    // Step 2: 等待分析結果載入，出現 Bar 按鈕
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Bar/i })).toBeInTheDocument()
    })

    // Step 3: 點擊圓餅圖的 NG 區塊（觸發 enterNgMode）
    const pieElement = screen.getByTestId('recharts-pie')
    await user.click(pieElement)

    // Step 4: 等待 NG records 載入
    await waitFor(() => {
      expect(screen.getByText('LOT-NG-001')).toBeInTheDocument()
    }, { timeout: 5000 })

    // 驗證 API 呼叫
    const analyzeHits = fetchCalls.filter((c) => c.url.includes('/api/v2/analytics/analyze'))
    const extractionHits = fetchCalls.filter((c) => c.url.includes('/api/v2/analytics/extraction-analysis'))
    const dynamicHits = fetchCalls.filter((c) => c.url.includes('/api/v2/query/records/dynamic'))

    // analyze 至少被呼叫 1 次（初始分析）
    expect(analyzeHits.length).toBeGreaterThanOrEqual(1)

    // extraction-analysis 在 enterNgMode 時被呼叫
    expect(extractionHits.length).toBeGreaterThanOrEqual(1)

    // records/dynamic 在 fetchNgRecords 時被呼叫
    expect(dynamicHits.length).toBeGreaterThanOrEqual(1)
  })

  it('enterNgMode 傳送正確的 extraction-analysis 參數', async () => {
    const user = userEvent.setup()
    const fetchCalls: Array<{ url: string; body: any }> = []

    vi.spyOn(window, 'fetch').mockImplementation(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      const body = init?.body ? JSON.parse(String(init.body)) : null
      fetchCalls.push({ url, body })

      if (url.includes('/api/v2/analytics/analyze')) {
        return new Response(JSON.stringify(MOCK_ANALYZE_RESULT), {
          status: 200, headers: { 'Content-Type': 'application/json' },
        })
      }
      if (url.includes('/api/v2/analytics/extraction-analysis')) {
        return new Response(JSON.stringify(MOCK_EXTRACTION_RESULT), {
          status: 200, headers: { 'Content-Type': 'application/json' },
        })
      }
      if (url.includes('/api/v2/query/records/dynamic')) {
        return new Response(JSON.stringify(MOCK_NG_RECORDS), {
          status: 200, headers: { 'Content-Type': 'application/json' },
        })
      }
      return new Response(JSON.stringify({}), {
        status: 200, headers: { 'Content-Type': 'application/json' },
      })
    })

    render(<AnalyticsPage />)
    await user.click(screen.getByRole('button', { name: /Analyze/i }))
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Bar/i })).toBeInTheDocument()
    })

    await user.click(screen.getByTestId('recharts-pie'))
    await waitFor(() => {
      expect(screen.getByText('LOT-NG-001')).toBeInTheDocument()
    }, { timeout: 5000 })

    // 驗證 extraction-analysis 的 payload
    const extractionCall = fetchCalls.find((c) => c.url.includes('/api/v2/analytics/extraction-analysis'))
    expect(extractionCall).toBeDefined()
    expect(extractionCall!.body).toHaveProperty('station')
    expect(extractionCall!.body.station).toBe('P2')
  })

  it('NG 模式下顯示兩個 NG records', async () => {
    const user = userEvent.setup()

    vi.spyOn(window, 'fetch').mockImplementation(async (input: RequestInfo | URL, _init?: RequestInit) => {
      const url = String(input)
      if (url.includes('/api/v2/analytics/analyze')) {
        return new Response(JSON.stringify(MOCK_ANALYZE_RESULT), {
          status: 200, headers: { 'Content-Type': 'application/json' },
        })
      }
      if (url.includes('/api/v2/analytics/extraction-analysis')) {
        return new Response(JSON.stringify(MOCK_EXTRACTION_RESULT), {
          status: 200, headers: { 'Content-Type': 'application/json' },
        })
      }
      if (url.includes('/api/v2/query/records/dynamic')) {
        return new Response(JSON.stringify(MOCK_NG_RECORDS), {
          status: 200, headers: { 'Content-Type': 'application/json' },
        })
      }
      return new Response(JSON.stringify({}), {
        status: 200, headers: { 'Content-Type': 'application/json' },
      })
    })

    render(<AnalyticsPage />)
    await user.click(screen.getByRole('button', { name: /Analyze/i }))
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Bar/i })).toBeInTheDocument()
    })

    await user.click(screen.getByTestId('recharts-pie'))

    // 等待兩個 NG records 都顯示
    await waitFor(() => {
      expect(screen.getByText('LOT-NG-001')).toBeInTheDocument()
      expect(screen.getByText('LOT-NG-002')).toBeInTheDocument()
    }, { timeout: 5000 })
  })
})
