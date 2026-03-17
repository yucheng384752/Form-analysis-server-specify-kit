import {
  ResponsiveContainer,
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  ZAxis,
  CartesianGrid,
  Tooltip,
} from 'recharts'
import { type WeightedItem, isPlainObject, toStr, safeNumber } from './types'

export interface WeightedViewProps {
  filteredWeightedItems: WeightedItem[]
  weightedScatterData: Array<{ id: string; x: number; y: number; z: number }>
  selectedId: string
  setSelectedId: (id: string) => void
  selectedWeighted: WeightedItem | null
  detailData: unknown
}

export function WeightedView({
  filteredWeightedItems,
  weightedScatterData,
  selectedId,
  setSelectedId,
  selectedWeighted,
  detailData,
}: WeightedViewProps) {
  return (
    <div className="analytics-report-grid">
      <div className="register-block">
        <div className="register-title" style={{ marginBottom: 8 }}>案件清單（{filteredWeightedItems.length}）</div>
        <div className="analytics-report-list">
          {filteredWeightedItems.slice(0, 500).map((r) => {
            const active = r.id === selectedId
            return (
              <button
                key={r.id}
                type="button"
                className={active ? 'btn-primary' : 'btn-secondary'}
                style={{ textAlign: 'left' }}
                onClick={() => setSelectedId(r.id)}
                title={r.id}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', gap: 10 }}>
                  <div style={{ fontWeight: 600 }}>{r.id}</div>
                  <div className="muted" style={{ whiteSpace: 'nowrap' }}>x_T2 {r.x_T2.toFixed(3)} / x_SPE {r.x_SPE.toFixed(3)}</div>
                </div>
                <div className="muted" style={{ marginTop: 4, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                  {r.t2_top ? <span className="analytics-pill">T2 top: {r.t2_top}</span> : null}
                  {r.spe_top ? <span className="analytics-pill">SPE top: {r.spe_top}</span> : null}
                </div>
              </button>
            )
          })}
          {filteredWeightedItems.length > 500 ? <div className="muted">僅顯示前 500 筆（避免卡頓）</div> : null}
        </div>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        {weightedScatterData.length > 0 ? (
          <div className="register-block">
            <div className="register-title" style={{ marginBottom: 8 }}>Risk Map（x_T2 vs x_SPE）</div>
            <div className="analytics-chart-wrap" style={{ height: 320, marginTop: 0 }}>
              <ResponsiveContainer>
                <ScatterChart margin={{ top: 8, right: 16, left: 8, bottom: 8 }}>
                  <CartesianGrid />
                  <XAxis type="number" dataKey="x" name="x_T2" />
                  <YAxis type="number" dataKey="y" name="x_SPE" />
                  <ZAxis type="number" dataKey="z" range={[40, 220]} />
                  <Tooltip
                    cursor={{ strokeDasharray: '3 3' }}
                    formatter={(value: any, name: any) => [value, name === 'x' ? 'x_T2' : name === 'y' ? 'x_SPE' : name]}
                    labelFormatter={(_, payload) => {
                      const row = payload?.[0]?.payload as any
                      return row?.id ? `ID: ${row.id}` : ''
                    }}
                  />
                  <Scatter data={weightedScatterData} fill="#2563eb" />
                </ScatterChart>
              </ResponsiveContainer>
            </div>
          </div>
        ) : null}
        {selectedWeighted && isPlainObject(detailData) ? (
          <>
            <div className="register-block">
              <div className="register-title" style={{ marginBottom: 8 }}>加權貢獻摘要</div>
              <div className="muted" style={{ marginBottom: 10 }}><code>{selectedWeighted.id}</code></div>
              <div className="analytics-report-kv">
                <div><span className="analytics-report-k">x_T2</span><span className="analytics-report-v">{selectedWeighted.x_T2.toFixed(3)}</span></div>
                <div><span className="analytics-report-k">x_SPE</span><span className="analytics-report-v">{selectedWeighted.x_SPE.toFixed(3)}</span></div>
              </div>
            </div>

            {(() => {
              const t2 = Array.isArray((detailData as any)?.t2_features) ? ((detailData as any).t2_features as unknown[]) : []
              const spe = Array.isArray((detailData as any)?.spe_features) ? ((detailData as any).spe_features as unknown[]) : []
              const top10 = (items: unknown[]) => items.filter(isPlainObject).map((x) => x as Record<string, unknown>).slice(0, 10)
              return (
                <>
                  <div className="register-block">
                    <div className="register-title" style={{ marginBottom: 8 }}>T2 Top Features</div>
                    <div className="analytics-report-table">
                      <div className="analytics-report-row analytics-report-head">
                        <div>feature</div>
                        <div>final_score</div>
                        <div>final_rank</div>
                      </div>
                      {top10(t2).map((x, idx) => (
                        <div key={idx} className="analytics-report-row">
                          <div>{toStr(x['feature'])}</div>
                          <div>{safeNumber(x['final_score']).toFixed(6)}</div>
                          <div>{safeNumber(x['final_rank'])}</div>
                        </div>
                      ))}
                    </div>
                  </div>

                  <div className="register-block">
                    <div className="register-title" style={{ marginBottom: 8 }}>SPE Top Features</div>
                    <div className="analytics-report-table">
                      <div className="analytics-report-row analytics-report-head">
                        <div>feature</div>
                        <div>final_score</div>
                        <div>final_rank</div>
                      </div>
                      {top10(spe).map((x, idx) => (
                        <div key={idx} className="analytics-report-row">
                          <div>{toStr(x['feature'])}</div>
                          <div>{safeNumber(x['final_score']).toFixed(6)}</div>
                          <div>{safeNumber(x['final_rank'])}</div>
                        </div>
                      ))}
                    </div>
                  </div>
                </>
              )
            })()}
          </>
        ) : (
          <>
            <div className="register-block"><div className="register-title" style={{ marginBottom: 8 }}>加權貢獻摘要</div><div className="muted">請從左側選擇一筆案件</div></div>
          </>
        )}
      </div>
    </div>
  )
}
