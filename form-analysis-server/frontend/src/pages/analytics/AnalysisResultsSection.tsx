import { useTranslation } from 'react-i18next'
import { ResponsiveContainer, PieChart, Pie, Cell, Tooltip, Legend, BarChart, Bar, ComposedChart, CartesianGrid, XAxis, YAxis, Line } from 'recharts'
import { OK_COLOR, NG_COLOR } from './types'
import { pct, round3 } from './utils'

interface AnalysisResultsSectionProps {
  overall: { ok: number; ng: number; total: number }
  pieData: Array<{ name: string; value: number; kind: 'OK' | 'NG' }>
  categoryCards: Array<{
    category: string
    items: Array<{ key: string; label: string; ok: number; ng: number; total: number }>
  }>
  analysisHeatmapRows: Array<{
    category: string
    key: string
    ok: number
    ng: number
    total: number
    ngRate: number
  }>
  winderChartData: Array<{ name: string; count: number; total: number; cumPct: number }>
  analysisChartMode: 'heatmap' | 'bar'
  productIdMode: boolean
  heatColor: (rate: number) => string
  onSetChartMode: (mode: 'heatmap' | 'bar') => void
  onEnterNgMode: (opts?: { winderNumber?: number | null }) => void
  parseWinderCategoryKey: (key: unknown) => number | null
}

const colors = [OK_COLOR, NG_COLOR]

export function AnalysisResultsSection({
  overall,
  pieData,
  categoryCards,
  analysisHeatmapRows,
  winderChartData,
  analysisChartMode,
  productIdMode,
  heatColor,
  onSetChartMode,
  onEnterNgMode,
  parseWinderCategoryKey,
}: AnalysisResultsSectionProps) {
  const { t } = useTranslation()

  return (
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
              onClick={() => onSetChartMode('heatmap')}
            >
              {t('analytics.views.heatmap')}
            </button>
          ) : null}
          <button
            type="button"
            className={analysisChartMode === 'bar' ? 'btn-primary' : 'btn-secondary'}
            onClick={() => onSetChartMode('bar')}
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
                                onEnterNgMode({ winderNumber })
                                return
                              }
                              onEnterNgMode()
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
  )
}
