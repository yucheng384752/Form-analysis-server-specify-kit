import { useMemo, useState } from 'react'

function isPlainObject(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value)
}

function tryStringify(value: unknown): string {
  try {
    return JSON.stringify(value, null, 2)
  } catch {
    return String(value)
  }
}

export function JsonViewer(props: {
  title?: string
  data: unknown
  defaultExpanded?: boolean
  maxPreviewChars?: number
}) {
  const { title, data } = props
  const [expanded, setExpanded] = useState(Boolean(props.defaultExpanded))

  const meta = useMemo(() => {
    if (Array.isArray(data)) return { kind: 'array' as const, count: data.length }
    if (isPlainObject(data)) return { kind: 'object' as const, count: Object.keys(data).length }
    if (data === null) return { kind: 'null' as const, count: 0 }
    return { kind: typeof data as 'string' | 'number' | 'boolean' | 'undefined' | 'function' | 'symbol' | 'bigint', count: 0 }
  }, [data])

  const raw = useMemo(() => tryStringify(data), [data])
  const maxChars = Math.max(2000, Math.floor(props.maxPreviewChars ?? 12000))
  const preview = raw.length > maxChars ? raw.slice(0, maxChars) + `\n... (truncated, ${raw.length} chars total)` : raw

  return (
    <div className="register-block" style={{ width: '100%' }}>
      <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: 12 }}>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, flexWrap: 'wrap' }}>
          <div className="register-title" style={{ marginBottom: 0 }}>{title || 'JSON'}</div>
          <div className="muted">{meta.kind}{meta.kind === 'array' || meta.kind === 'object' ? ` (${meta.count})` : ''}</div>
        </div>
        <button type="button" className="btn-secondary" onClick={() => setExpanded((v) => !v)}>
          {expanded ? '收起' : '展開'}
        </button>
      </div>

      {expanded ? (
        <pre style={{ marginTop: 12, whiteSpace: 'pre-wrap', wordBreak: 'break-word', overflowX: 'auto' }}>{preview}</pre>
      ) : (
        <pre style={{ marginTop: 12, maxHeight: 120, overflow: 'hidden', whiteSpace: 'pre-wrap', wordBreak: 'break-word', opacity: 0.85 }}>{preview}</pre>
      )}
    </div>
  )
}
