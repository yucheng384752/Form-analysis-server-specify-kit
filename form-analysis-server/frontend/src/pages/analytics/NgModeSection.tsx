import { useTranslation } from 'react-i18next'
import { ResponsiveContainer, ComposedChart, CartesianGrid, XAxis, YAxis, Tooltip, Legend, Bar, Line } from 'recharts'
import { ParetoChart } from '../../components/analytics/ParetoChart'
import type { QueryRecordLite, ParetoPoint } from './types'
import { PARETO_ENABLED_DAILY, PARETO_SOURCE_FEATURE } from './types'
import { isPlainObject, round3 } from './utils'

interface NgModeSectionProps {
  ngWinderNumber: number | null
  ngLoading: boolean
  ngError: string
  ngRecords: QueryRecordLite[]
  featureParetoData: ParetoPoint[]
  extractionLoading: boolean
  extractionData: {
    final_raw_score: Record<string, number>
    boundary_count: Record<string, number>
    spe_score: Record<string, number>
    t2_score: Record<string, number>
  } | null
  ngFeaturePctEntries: Array<{ name: string; pct: number }>
  ngFeaturePctChartData: Array<{ name: string; pct: number; cumPct: number }>
  ngFeaturePctChartHeight: number
  onExitNgMode: () => void
  onClearWinder: () => void
  onRefresh: () => void
  getNgKeyCandidates: (record: QueryRecordLite) => string[]
  sortRowsNgFirst: (rows: unknown[], keys: string[]) => unknown[]
  rowHasNg: (row: unknown, keys: string[]) => boolean
  formatCellValue: (value: unknown) => string
}

export function NgModeSection({
  ngWinderNumber,
  ngLoading,
  ngError,
  ngRecords,
  featureParetoData,
  extractionLoading,
  extractionData,
  ngFeaturePctEntries,
  ngFeaturePctChartData,
  ngFeaturePctChartHeight,
  onExitNgMode,
  onClearWinder,
  onRefresh,
  getNgKeyCandidates,
  sortRowsNgFirst,
  rowHasNg,
  formatCellValue,
}: NgModeSectionProps) {
  const { t } = useTranslation()

  return (
    <>
      <div className="analytics-section-header">{t('analytics.ngOnlyTitle')}{ngWinderNumber ? ` · W${ngWinderNumber}` : ''}</div>

      <section className="analytics-card">
        <div className="analytics-actions" style={{ justifyContent: 'space-between', marginTop: 0 }}>
          <button type="button" className="btn-secondary" onClick={onExitNgMode}>
            {t('analytics.backToAnalysis')}
          </button>

          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            {ngWinderNumber !== null ? (
              <button
                type="button"
                className="btn-secondary"
                onClick={onClearWinder}
                disabled={ngLoading}
              >
                {t('common.clear')}
              </button>
            ) : null}

            <button type="button" className="btn-primary" onClick={onRefresh} disabled={ngLoading}>
              {ngLoading ? t('analytics.loading') : t('analytics.refresh')}
            </button>
          </div>
        </div>

        {ngError ? <div className="analytics-error">{ngError}</div> : null}

        {PARETO_ENABLED_DAILY ? (
          <div style={{ marginTop: 16, marginBottom: 16 }}>
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
                gap: 12,
              }}
            >
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
  )
}
