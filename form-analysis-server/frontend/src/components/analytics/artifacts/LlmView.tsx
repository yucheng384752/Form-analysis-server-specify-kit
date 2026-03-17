import { type LlmListItem, isPlainObject, toStr, safeNumber, formatIsoPreview } from './types'

export interface LlmViewProps {
  filteredLlmItems: LlmListItem[]
  selectedId: string
  setSelectedId: (id: string) => void
  selectedLlmDetail: any
}

export function LlmView({
  filteredLlmItems,
  selectedId,
  setSelectedId,
  selectedLlmDetail,
}: LlmViewProps) {
  return (
    <div className="analytics-report-grid">
      <div className="register-block">
        <div className="register-title" style={{ marginBottom: 8 }}>事件清單（{filteredLlmItems.length}）</div>
        <div className="analytics-report-list">
          {filteredLlmItems.slice(0, 500).map((r) => {
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
                  <div style={{ fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis' }}>{r.event_id}</div>
                  <div className="muted" style={{ whiteSpace: 'nowrap' }}>異常 {r.total_anomalies}</div>
                </div>
                <div className="muted" style={{ marginTop: 4 }}>{formatIsoPreview(r.event_time_raw) || '-'}</div>
              </button>
            )
          })}
          {filteredLlmItems.length > 500 ? <div className="muted">僅顯示前 500 筆（避免卡頓）</div> : null}
        </div>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        {selectedLlmDetail ? (
          <>
            <div className="register-block">
              <div className="register-title" style={{ marginBottom: 8 }}>LLM 主異常清單（表格）</div>
              <div className="analytics-report-kv">
                <div><span className="analytics-report-k">event_id</span><span className="analytics-report-v"><code>{toStr(selectedLlmDetail.event_id) || '-'}</code></span></div>
                <div><span className="analytics-report-k">event_time</span><span className="analytics-report-v">{formatIsoPreview(selectedLlmDetail.event_time) || '-'}</span></div>
                <div><span className="analytics-report-k">total_anomalies</span><span className="analytics-report-v">{safeNumber(selectedLlmDetail.total_anomalies)}</span></div>
              </div>
            </div>

            {Array.isArray(selectedLlmDetail.by_station) ? (
              <div className="register-block">
                <div className="register-title" style={{ marginBottom: 8 }}>按站點</div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                  {(selectedLlmDetail.by_station as unknown[]).filter(isPlainObject).map((stationRow: any) => {
                    const station = toStr(stationRow.station)
                    const anomalies = Array.isArray(stationRow.anomalies) ? (stationRow.anomalies as unknown[]) : []
                    if (anomalies.length === 0) return null
                    return (
                      <div key={station} className="analytics-report-subcard">
                        <div style={{ display: 'flex', gap: 8, alignItems: 'baseline', flexWrap: 'wrap' }}>
                          <div style={{ fontWeight: 800 }}>{station || '(station)'}</div>
                          <span className="analytics-pill">{anomalies.length} 條</span>
                        </div>
                        <div className="analytics-report-table" style={{ marginTop: 8 }}>
                          <div className="analytics-report-row analytics-report-head" style={{ gridTemplateColumns: '220px 150px 1.5fr' }}>
                            <div>feature</div>
                            <div>method</div>
                            <div>description</div>
                          </div>
                          {anomalies.slice(0, 50).filter(isPlainObject).map((it: any, idx: number) => (
                            <div key={idx} className="analytics-report-row" style={{ gridTemplateColumns: '220px 150px 1.5fr' }}>
                              <div>{toStr(it.feature_name) || '-'}</div>
                              <div>{toStr(it.detection_method) || '-'}</div>
                              <div style={{ whiteSpace: 'normal' }}>{toStr(it.problem_description) || '-'}</div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )
                  })}
                </div>
              </div>
            ) : null}
          </>
        ) : (
          <div className="register-block"><div className="register-title" style={{ marginBottom: 8 }}>LLM 主異常清單（表格）</div><div className="muted">請從左側選擇一筆事件</div></div>
        )}
      </div>
    </div>
  )
}
