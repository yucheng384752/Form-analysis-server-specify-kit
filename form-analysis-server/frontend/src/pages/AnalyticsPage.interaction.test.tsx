import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { AnalyticsPage } from './AnalyticsPage'

vi.mock('../components/common/ToastContext', () => ({
  useToast: () => ({
    showToast: vi.fn(),
  }),
}))

vi.mock('recharts', () => {
  const React = require('react')
  type Entry = { name?: string; value: unknown }
  return {
    __esModule: true,
    ResponsiveContainer: ({ children }: { children: React.ReactNode }) => React.createElement('div', null, children),
    PieChart: ({ children }: { children: React.ReactNode }) => React.createElement('div', null, children),
    Pie: ({ children, onClick }: { children: React.ReactNode; onClick?: (payload: any) => void }) =>
      React.createElement(
        'div',
        { 'data-testid': 'recharts-pie', onClick: () => onClick?.({ payload: { kind: 'NG' } }) },
        children,
      ),
    Cell: () => null,
    Tooltip: () => null,
    Legend: () => null,
    ComposedChart: ({ children }: { children: React.ReactNode }) => React.createElement('div', null, children),
    BarChart: ({ children }: { children: React.ReactNode }) => React.createElement('div', null, children),
    Bar: ({ data, onClick, className, children }: { data?: Entry[]; onClick?: (payload: any) => void; className?: string; children: React.ReactNode }) => {
      // Only render interactive buttons for Bars that have an onClick handler.
      // Bars without onClick (e.g. ParetoChart's display-only bars) must not render
      // duplicate button elements that would confuse role-based queries.
      if (!onClick) return React.createElement('div', { className }, children)

      const barData = Array.isArray(data) && data.length > 0 ? data : [{ name: 'OK', value: 0 }, { name: 'NG', value: 0 }]

      return React.createElement(
        'div',
        { className },
        barData.map((entry, index) =>
          React.createElement(
            'button',
            {
              key: `${entry.name}-${index}`,
              type: 'button',
              'data-testid': `recharts-bar-${index}-${entry.name}`,
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

type FetchCall = [RequestInfo | URL, RequestInit | undefined]

describe('AnalyticsPage interaction regression', () => {
  const toYmd = (date: Date): string => {
    const y = date.getFullYear()
    const m = String(date.getMonth() + 1).padStart(2, '0')
    const d = String(date.getDate()).padStart(2, '0')
    return `${y}-${m}-${d}`
  }

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

    const today = new Date()
    const thisMonthStart = new Date(today.getFullYear(), today.getMonth(), 1)
    // thisMonthEnd used for date range calculation reference
    void new Date(today.getFullYear(), today.getMonth() + 1, 0)

    const analysisResult = {
      'Winder Number': {
          W5: {
          total_count: 10,
          count_0: 3,
        },
      },
    }

    const ngRecordsResponse = {
      total_count: 1,
      page: 1,
      page_size: 10,
      records: [
        {
          id: 'r1',
          lot_no: 'LOT-001',
          data_type: 'P2',
          production_date: toYmd(thisMonthStart),
          created_at: `${toYmd(thisMonthStart)}T08:00:00Z`,
          product_id: 'P2-001',
          additional_data: {
            rows: [
              {
                'Striped Results': 0,
              },
            ],
          },
        },
      ],
    }

    vi.spyOn(window, 'fetch').mockImplementation(async (input: RequestInfo | URL, _init?: RequestInit) => {
      const url = String(input)
      if (url.includes('/api/v2/analytics/analyze')) {
        return new Response(JSON.stringify(analysisResult), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        })
      }

      if (url.includes('/api/v2/query/records/dynamic')) {
        return new Response(JSON.stringify(ngRecordsResponse), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        })
      }

      return new Response(JSON.stringify({}), { status: 200, headers: { 'Content-Type': 'application/json' } })
    })
  })

  it('click Winder NG bar to load corresponding date-scoped NG list', async () => {
    const user = userEvent.setup()
    render(<AnalyticsPage />)

    await user.click(screen.getByRole('button', { name: /Analyze/i }))
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Bar/i })).toBeInTheDocument()
    })

    await user.click(screen.getByRole('button', { name: /Bar/i }))
    await user.click(screen.getByRole('button', { name: /^NG$/i }))

    await waitFor(() => {
      expect(screen.getByText('LOT-001')).toBeInTheDocument()
    })

    const calls = (window.fetch as unknown as { mock: { calls: FetchCall[] } }).mock.calls
    const dynamicCalls = calls.filter(([input]) => String(input).includes('/api/v2/query/records/dynamic'))
    expect(dynamicCalls).toHaveLength(1)

    const payload = JSON.parse((dynamicCalls[0][1]?.body as string) || '{}') as {
      data_type: string
      filters: Array<{ field: string; op: string; value: unknown }>
    }
    const today = new Date()
    const expectedStart = toYmd(new Date(today.getFullYear(), today.getMonth(), 1))
    const expectedEnd = toYmd(new Date(today.getFullYear(), today.getMonth() + 1, 0))

    expect(payload.data_type).toBe('P2')
    expect(payload.filters).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ field: 'production_date', op: 'between', value: [expectedStart, expectedEnd] }),
        expect.objectContaining({ field: 'winder_number', op: 'eq', value: '5' }),
        expect.objectContaining({ field: 'slitting_result', op: 'eq', value: 0 }),
      ]),
    )
  })

  it('for 2025-08 + P2 + winder 1, compare NG query payload fields', async () => {
    const expectedStart = '2025-08-01'
    const expectedEnd = '2025-08-31'

    const user = userEvent.setup()
    const analysisResult = {
      'Winder Number': {
        W1: {
          total_count: 2,
          count_0: 1,
        },
      },
    }
    const ngRecordsResponse = {
      total_count: 1,
      page: 1,
      page_size: 200,
      records: [
        {
          id: 'r1',
          lot_no: 'LOT-2025-08-01',
          data_type: 'P2',
          production_date: expectedStart,
          created_at: `${expectedStart}T08:00:00Z`,
          product_id: 'P2-2025-0801',
          additional_data: {
            rows: [
              {
                'Striped Results': 0,
              },
            ],
          },
        },
      ],
    }

    vi.spyOn(window, 'fetch').mockImplementation(async (input: RequestInfo | URL, _init?: RequestInit) => {
      const url = String(input)
      if (url.includes('/api/v2/analytics/analyze')) {
        return new Response(JSON.stringify(analysisResult), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        })
      }

      if (url.includes('/api/v2/query/records/dynamic')) {
        return new Response(JSON.stringify(ngRecordsResponse), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        })
      }

      return new Response(JSON.stringify({}), { status: 200, headers: { 'Content-Type': 'application/json' } })
    })

    render(<AnalyticsPage />)

    const selects = screen.getAllByRole('combobox')
    expect(selects.length).toBeGreaterThanOrEqual(3)
    const yearSelect = selects[1]
    const monthSelect = selects[2]
    await user.selectOptions(yearSelect, '2025')
    await user.selectOptions(monthSelect, '8')

    await waitFor(() => {
      expect(screen.getByText(`Range: ${expectedStart} ~ ${expectedEnd}`)).toBeInTheDocument()
    })

    await user.click(screen.getByRole('button', { name: /Analyze/i }))

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Bar/i })).toBeInTheDocument()
    })

    await user.click(screen.getByRole('button', { name: /Bar/i }))
    await user.click(screen.getByRole('button', { name: /^NG$/i }))

    await waitFor(() => {
      expect(screen.getByText('LOT-2025-08-01')).toBeInTheDocument()
    })

    const calls = (window.fetch as unknown as { mock: { calls: FetchCall[] } }).mock.calls
    const dynamicCalls = calls.filter(([input]) => String(input).includes('/api/v2/query/records/dynamic'))
    expect(dynamicCalls).toHaveLength(1)

    const payload = JSON.parse((dynamicCalls[0][1]?.body as string) || '{}') as {
      data_type: string
      page: number
      page_size: number
      filters: Array<{ field: string; op: string; value: unknown }>
    }

    const requiredFilters = [
      { field: 'production_date', op: 'between', value: [expectedStart, expectedEnd] },
      { field: 'winder_number', op: 'eq', value: '1' },
      { field: 'slitting_result', op: 'eq', value: 0 },
    ]

    const missingFilters = requiredFilters.filter((required) =>
      !payload.filters.some((f) =>
        f.field === required.field &&
        f.op === required.op &&
        JSON.stringify(f.value) === JSON.stringify(required.value),
      ),
    )

    expect(missingFilters).toEqual([])
    expect(payload.data_type).toBe('P2')
    expect(payload.page).toBe(1)
    expect(payload.page_size).toBe(200)
  })

  it('fallback to row_data.Striped Results when slitting_result filter is unsupported', async () => {
    const user = userEvent.setup()
    const analysisResult = {
      'Winder Number': {
        W1: { total_count: 1, count_0: 1 },
      },
    }
    const ngRecordsResponse = {
      total_count: 1,
      page: 1,
      page_size: 200,
      records: [
        {
          id: 'r1',
          lot_no: 'LOT-FALLBACK-001',
          data_type: 'P2',
          production_date: '2025-08-15',
          created_at: '2025-08-15T08:00:00Z',
          additional_data: {
            rows: [{ 'Striped Results': 0 }],
          },
        },
      ],
    }
    let dynamicHit = 0
    vi.spyOn(window, 'fetch').mockImplementation(async (input: RequestInfo | URL, _init?: RequestInit) => {
      const url = String(input)
      if (url.includes('/api/v2/analytics/analyze')) {
        return new Response(JSON.stringify(analysisResult), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        })
      }
      if (url.includes('/api/v2/query/records/dynamic')) {
        dynamicHit += 1
        if (dynamicHit === 1) {
          return new Response(JSON.stringify({ detail: 'Unsupported field(s) for data_type P2: slitting_result' }), {
            status: 400,
            headers: { 'Content-Type': 'application/json' },
          })
        }
        return new Response(JSON.stringify(ngRecordsResponse), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        })
      }
      return new Response(JSON.stringify({}), { status: 200, headers: { 'Content-Type': 'application/json' } })
    })

    render(<AnalyticsPage />)
    await user.click(screen.getByRole('button', { name: /Analyze/i }))
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Bar/i })).toBeInTheDocument()
    })
    await user.click(screen.getByRole('button', { name: /Bar/i }))
    await user.click(screen.getByRole('button', { name: /^NG$/i }))
    await waitFor(() => {
      expect(screen.getByText('LOT-FALLBACK-001')).toBeInTheDocument()
    })

    const calls = (window.fetch as unknown as { mock: { calls: FetchCall[] } }).mock.calls
    const dynamicCalls = calls.filter(([input]) => String(input).includes('/api/v2/query/records/dynamic'))
    expect(dynamicCalls).toHaveLength(2)

    const payload1 = JSON.parse((dynamicCalls[0][1]?.body as string) || '{}') as {
      filters: Array<{ field: string; op: string; value: unknown }>
    }
    const payload2 = JSON.parse((dynamicCalls[1][1]?.body as string) || '{}') as {
      filters: Array<{ field: string; op: string; value: unknown }>
    }

    expect(payload1.filters).toEqual(
      expect.arrayContaining([expect.objectContaining({ field: 'slitting_result', op: 'eq', value: 0 })]),
    )
    expect(payload2.filters).toEqual(
      expect.arrayContaining([expect.objectContaining({ field: 'row_data.Striped Results', op: 'eq', value: 0 })]),
    )
  })
})
