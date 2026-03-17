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
import { type EventRow, isPlainObject, toStr, safeNumber, formatIsoPreview } from './types'

export interface EventsViewProps {
  filteredEventRows: EventRow[]
  eventTrendData: Array<{ day: string; events: number; iqr: number }>
  selectedId: string
  setSelectedId: (id: string) => void
  detailData: unknown
}

export function EventsView({
  filteredEventRows,
  eventTrendData,
  selectedId,
  setSelectedId,
  detailData,
}: EventsViewProps) {
  const selectedEvent = filteredEventRows.find((x) => x.event_id === selectedId) ?? null

  return (
    <div className="analytics-report-grid">
      <div className="register-block">
        <div className="register-title" style={{ marginBottom: 8 }}>事件清單（{filteredEventRows.length}）</div>
        {eventTrendData.length > 0 ? (
          <div className="analytics-chart-wrap" style={{ height: 220, marginTop: 0, marginBottom: 8 }}>
            <ResponsiveContainer>
              <BarChart data={eventTrendData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="day" tick={{ fontSize: 11 }} />
                <YAxis allowDecimals={false} />
                <Tooltip />
                <Legend />
                <Bar dataKey="events" name="Events" fill="#2563eb" />
                <Bar dataKey="iqr" name="IQR Events" fill="#ef4444" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        ) : null}
        <div className="analytics-report-list">
          {filteredEventRows.slice(0, 500).map((r) => {
            const active = r.event_id === selectedId
            return (
              <button
                key={r.event_id}
                type="button"
                className={active ? 'btn-primary' : 'btn-secondary'}
                style={{ textAlign: 'left' }}
                onClick={() => setSelectedId(r.event_id)}
                title={r.event_id}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', gap: 10 }}>
                  <div style={{ fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis' }}>{r.produce_no || r.event_id}</div>
                  <div className="muted" style={{ whiteSpace: 'nowrap' }}>{formatIsoPreview(r.event_date_raw) || '-'}</div>
                </div>
                <div className="muted" style={{ marginTop: 4, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                  <span className="analytics-pill">IQR: {r.iqr_count}</span>
                  <span className="analytics-pill">T2: {r.t2_count}</span>
                  <span className="analytics-pill">SPE: {r.spe_count}</span>
                  {r.slitting ? <span className="analytics-pill">Slit: {r.slitting}</span> : null}
                  {r.winder ? <span className="analytics-pill">Winder: {r.winder}</span> : null}
                </div>
              </button>
            )
          })}
          {filteredEventRows.length > 500 ? <div className="muted">僅顯示前 500 筆（避免卡頓）</div> : null}
        </div>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        {selectedEvent ? (
          <>
            <div className="register-block">
              <div className="register-title" style={{ marginBottom: 8 }}>事件摘要</div>
              <div className="muted" style={{ marginBottom: 10 }}><code>{selectedEvent.event_id}</code></div>
              <div className="analytics-report-kv">
                <div><span className="analytics-report-k">時間</span><span className="analytics-report-v">{formatIsoPreview(selectedEvent.event_date_raw) || '-'}</span></div>
                <div><span className="analytics-report-k">Produce_No.</span><span className="analytics-report-v">{selectedEvent.produce_no || '-'}</span></div>
                <div><span className="analytics-report-k">Slitting</span><span className="analytics-report-v">{selectedEvent.slitting || '-'}</span></div>
                <div><span className="analytics-report-k">Winder</span><span className="analytics-report-v">{selectedEvent.winder || '-'}</span></div>
                <div><span className="analytics-report-k">IQR anomalies</span><span className="analytics-report-v">{selectedEvent.iqr_count}</span></div>
              </div>
            </div>

            {selectedId && isPlainObject(detailData) ? (
              <>
                {Array.isArray((detailData as any)?.iqr_features) ? (
                  <div className="register-block">
                    <div className="register-title" style={{ marginBottom: 8 }}>IQR 異常特徵</div>
                    <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                      {((detailData as any).iqr_features as unknown[]).slice(0, 80).map((x, idx) => (
                        <span key={idx} className="analytics-pill">{toStr(x) || '-'}</span>
                      ))}
                    </div>
                  </div>
                ) : null}

                {Array.isArray((detailData as any)?.t2_features) ? (
                  <div className="register-block">
                    <div className="register-title" style={{ marginBottom: 8 }}>T2 Top Features</div>
                    <div className="analytics-report-table">
                      <div className="analytics-report-row analytics-report-head">
                        <div>feature</div>
                        <div>final_score</div>
                        <div>final_rank</div>
                      </div>
                      {((detailData as any).t2_features as unknown[]).slice(0, 20).filter(isPlainObject).map((x: any, idx: number) => (
                        <div key={idx} className="analytics-report-row">
                          <div>{toStr(x.feature) || '-'}</div>
                          <div>{safeNumber(x.final_score).toFixed(6)}</div>
                          <div>{safeNumber(x.final_rank)}</div>
                        </div>
                      ))}
                    </div>
                  </div>
                ) : null}

                {Array.isArray((detailData as any)?.spe_features) ? (
                  <div className="register-block">
                    <div className="register-title" style={{ marginBottom: 8 }}>SPE Top Features</div>
                    <div className="analytics-report-table">
                      <div className="analytics-report-row analytics-report-head">
                        <div>feature</div>
                        <div>final_score</div>
                        <div>final_rank</div>
                      </div>
                      {((detailData as any).spe_features as unknown[]).slice(0, 20).filter(isPlainObject).map((x: any, idx: number) => (
                        <div key={idx} className="analytics-report-row">
                          <div>{toStr(x.feature) || '-'}</div>
                          <div>{safeNumber(x.final_score).toFixed(6)}</div>
                          <div>{safeNumber(x.final_rank)}</div>
                        </div>
                      ))}
                    </div>
                  </div>
                ) : null}
              </>
            ) : null}
          </>
        ) : (
          <>
            <div className="register-block">
              <div className="register-title" style={{ marginBottom: 8 }}>事件摘要</div>
              <div className="muted">請從左側選擇一筆事件</div>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
