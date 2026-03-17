import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
} from 'recharts'
import { type AggRow, type CoreFeatureSummary } from './types'

export interface AggregatedViewProps {
  filteredAggRows: AggRow[]
  selectedId: string
  setSelectedId: (id: string) => void
  selectedAgg: AggRow | null
  selectedAggCoreFeatures: CoreFeatureSummary[]
  aggCoreChartData: Array<{ feature: string; IQR: number; T2: number; SPE: number; total: number }>
}

export function AggregatedView({
  filteredAggRows,
  selectedId,
  setSelectedId,
  selectedAgg,
  selectedAggCoreFeatures,
  aggCoreChartData,
}: AggregatedViewProps) {
  return (
    <div className="analytics-report-grid">
      <div className="register-block">
        <div className="register-title" style={{ marginBottom: 8 }}>彙總清單（{filteredAggRows.length}）</div>
        <div className="analytics-report-list">
          {filteredAggRows.slice(0, 500).map((r) => {
            const active = r.summary_id === selectedId
            return (
              <button
                key={r.summary_id}
                type="button"
                className={active ? 'btn-primary' : 'btn-secondary'}
                style={{ textAlign: 'left' }}
                onClick={() => setSelectedId(r.summary_id)}
                title={r.summary_id}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', gap: 10 }}>
                  <div style={{ fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis' }}>{r.analysis_dimension || '(dimension)'}</div>
                  <div className="muted" style={{ whiteSpace: 'nowrap' }}>樣本 {r.sample_count}</div>
                </div>
                <div className="muted" style={{ marginTop: 4, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                  <span className="analytics-pill">core: {r.core_feature_count}</span>
                  <span className="analytics-pill">events: {r.event_count}</span>
                  {r.context_preview ? <span className="analytics-pill">{r.context_preview}</span> : null}
                </div>
              </button>
            )
          })}
          {filteredAggRows.length > 500 ? <div className="muted">僅顯示前 500 筆（避免卡頓）</div> : null}
        </div>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        {selectedAgg ? (
          <>
            <div className="register-block">
              <div className="register-title" style={{ marginBottom: 8 }}>彙總摘要</div>
              <div className="muted" style={{ marginBottom: 10 }}><code>{selectedAgg.summary_id}</code></div>
              <div className="analytics-report-kv">
                <div><span className="analytics-report-k">維度</span><span className="analytics-report-v">{selectedAgg.analysis_dimension || '-'}</span></div>
                <div><span className="analytics-report-k">樣本數</span><span className="analytics-report-v">{selectedAgg.sample_count}</span></div>
                <div><span className="analytics-report-k">events</span><span className="analytics-report-v">{selectedAgg.event_count}</span></div>
                <div><span className="analytics-report-k">core features</span><span className="analytics-report-v">{selectedAgg.core_feature_count}</span></div>
              </div>
            </div>

            <div className="register-block">
              <div className="register-title" style={{ marginBottom: 8 }}>Core Features 重點摘要</div>
              {aggCoreChartData.length > 0 ? (
                <div className="analytics-chart-wrap" style={{ height: 320, marginTop: 0, marginBottom: 10 }}>
                  <ResponsiveContainer>
                    <BarChart data={aggCoreChartData} layout="vertical" margin={{ left: 30, right: 12 }}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis type="number" allowDecimals={false} />
                      <YAxis type="category" dataKey="feature" width={180} tick={{ fontSize: 11 }} />
                      <Tooltip />
                      <Legend />
                      <Bar dataKey="IQR" stackId="a" fill="#ef4444" />
                      <Bar dataKey="T2" stackId="a" fill="#2563eb" />
                      <Bar dataKey="SPE" stackId="a" fill="#0ea5e9" />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              ) : null}
              {selectedAggCoreFeatures.length === 0 ? (
                <div className="muted">找不到 core_features 或 evidence 結構不符合預期</div>
              ) : (
                <>
                  <div className="muted" style={{ marginBottom: 10 }}>
                    依 evidence 頻率（IQR + T2 + SPE）排序，僅顯示前 12 個。
                  </div>
                  <div className="analytics-report-card-grid">
                    {selectedAggCoreFeatures.slice(0, 12).map((r) => (
                      <div key={r.feature} className="analytics-report-card">
                        <div style={{ display: 'flex', justifyContent: 'space-between', gap: 10, alignItems: 'baseline' }}>
                          <div style={{ fontWeight: 800, overflow: 'hidden', textOverflow: 'ellipsis' }}>{r.feature}</div>
                          <div className="muted" style={{ whiteSpace: 'nowrap' }}>Total {r.total}</div>
                        </div>
                        <div className="muted" style={{ marginTop: 8, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                          <span className="analytics-pill">IQR: {r.iqr_freq}</span>
                          <span className="analytics-pill">T2: {r.t2_freq}</span>
                          <span className="analytics-pill">SPE: {r.spe_freq}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </>
              )}
            </div>
          </>
        ) : (
          <>
            <div className="register-block"><div className="register-title" style={{ marginBottom: 8 }}>彙總摘要</div><div className="muted">請從左側選擇一筆彙總</div></div>
          </>
        )}
      </div>
    </div>
  )
}
