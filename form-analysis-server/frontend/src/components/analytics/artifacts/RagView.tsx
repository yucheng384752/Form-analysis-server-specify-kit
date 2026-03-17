import { type RagEvent, isPlainObject, toStr } from './types'

export interface RagViewProps {
  filteredRagEvents: RagEvent[]
  selectedId: string
  setSelectedId: (id: string) => void
  selectedRag: RagEvent | null
  detailData: unknown
}

export function RagView({
  filteredRagEvents,
  selectedId,
  setSelectedId,
  selectedRag,
  detailData,
}: RagViewProps) {
  return (
    <div className="analytics-report-grid">
      <div className="register-block">
        <div className="register-title" style={{ marginBottom: 8 }}>事件清單（{filteredRagEvents.length}）</div>
        <div className="analytics-report-list">
          {filteredRagEvents.slice(0, 500).map((r) => {
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
                  <div className="muted" style={{ whiteSpace: 'nowrap' }}>SOP {r.sop_count}</div>
                </div>
                <div className="muted" style={{ marginTop: 4, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                  <span className="analytics-pill">features: {r.feature_count}</span>
                </div>
              </button>
            )
          })}
          {filteredRagEvents.length > 500 ? <div className="muted">僅顯示前 500 筆（避免卡頓）</div> : null}
        </div>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        {selectedRag && isPlainObject(detailData) ? (
          <>
            <div className="register-block">
              <div className="register-title" style={{ marginBottom: 8 }}>SOP 建議（RAG）</div>
              <div className="analytics-artifacts-hint" style={{ marginBottom: 10 }}><code>{selectedRag.event_id}</code></div>
              {Object.entries(((detailData as any)?.features ?? {}) as Record<string, unknown>).map(([feature, rows]) => {
                const arr = Array.isArray(rows) ? (rows as unknown[]) : []
                if (arr.length === 0) return null
                return (
                  <div key={feature} style={{ marginBottom: 12 }}>
                    <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'baseline' }}>
                      <div style={{ fontWeight: 700 }}>{feature}</div>
                      <span className="analytics-pill">{arr.length} 條</span>
                    </div>
                    <div className="analytics-report-table" style={{ marginTop: 6 }}>
                      <div
                        className="analytics-report-row analytics-report-head"
                        style={{ gridTemplateColumns: '90px 130px 120px 1.2fr 1.2fr 120px' }}
                      >
                        <div>code</div>
                        <div>station</div>
                        <div>kind</div>
                        <div>problem</div>
                        <div>action</div>
                        <div>section</div>
                      </div>
                      {arr.slice(0, 20).filter(isPlainObject).map((row: any, idx) => {
                        const code = toStr(row.code)
                        const station = toStr(row.station)
                        const kind = toStr(row.kind)
                        const problem = toStr(row.problem)
                        const action = toStr(row.action)
                        const section = toStr(row.section)
                        return (
                          <div
                            key={idx}
                            className="analytics-report-row"
                            style={{ gridTemplateColumns: '90px 130px 120px 1.2fr 1.2fr 120px' }}
                            title={[code, station, kind, problem, action, section].filter(Boolean).join(' / ')}
                          >
                            <div>{code || '-'}</div>
                            <div>{station || '-'}</div>
                            <div>{kind || '-'}</div>
                            <div style={{ whiteSpace: 'normal' }}>{problem || '-'}</div>
                            <div style={{ whiteSpace: 'normal' }}>{action || '-'}</div>
                            <div>{section || '-'}</div>
                          </div>
                        )
                      })}
                      {arr.length > 20 ? (
                        <div className="analytics-artifacts-hint" style={{ padding: '8px 10px' }}>
                          僅顯示前 20 條（避免卡頓）
                        </div>
                      ) : null}
                    </div>
                  </div>
                )
              })}
            </div>
          </>
        ) : (
          <>
            <div className="register-block"><div className="register-title" style={{ marginBottom: 8 }}>SOP 建議（RAG）</div><div className="analytics-artifacts-hint">請從左側選擇一筆事件</div></div>
          </>
        )}
      </div>
    </div>
  )
}
