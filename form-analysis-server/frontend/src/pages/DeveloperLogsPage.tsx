import { useCallback, useEffect, useMemo, useState } from 'react'
import { Download, RefreshCw, Search } from 'lucide-react'

import logService, { type LogEntry, type LogFile } from '../services/logService'
import '../styles/developer-logs-page.css'

const LEVELS = ['ALL', 'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'] as const
type LevelFilter = (typeof LEVELS)[number]

function normalizeLevel(level: string): string {
  const upper = String(level || '').toUpperCase()
  if (upper === 'WARN') return 'WARNING'
  return upper || 'INFO'
}

function levelClass(level: string): string {
  const normalized = normalizeLevel(level)
  if (normalized === 'ERROR' || normalized === 'CRITICAL') return 'is-error'
  if (normalized === 'WARNING') return 'is-warning'
  if (normalized === 'INFO') return 'is-info'
  if (normalized === 'DEBUG') return 'is-debug'
  return 'is-default'
}

function formatTimestamp(timestamp: string): string {
  if (!timestamp) return '-'
  const parsed = new Date(timestamp)
  if (Number.isNaN(parsed.getTime())) return timestamp
  return parsed.toLocaleString()
}

export function DeveloperLogsPage() {
  const [files, setFiles] = useState<Record<string, LogFile>>({})
  const [selectedLog, setSelectedLog] = useState('app')
  const [level, setLevel] = useState<LevelFilter>('ALL')
  const [hours, setHours] = useState('24')
  const [query, setQuery] = useState('')
  const [entries, setEntries] = useState<LogEntry[]>([])
  const [total, setTotal] = useState(0)
  const [hasMore, setHasMore] = useState(false)
  const [offset, setOffset] = useState(0)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fileOptions = useMemo(() => Object.keys(files).sort(), [files])

  const loadFiles = useCallback(async () => {
    const nextFiles = await logService.getLogFiles()
    setFiles(nextFiles)
    const nextNames = Object.keys(nextFiles).sort()
    if (nextNames.length > 0 && !nextFiles[selectedLog]) {
      setSelectedLog(nextNames.includes('app') ? 'app' : nextNames[0])
    }
  }, [selectedLog])

  const loadEntries = useCallback(
    async (nextOffset = 0, append = false) => {
      if (!selectedLog) return
      setLoading(true)
      setError(null)
      try {
        const parsedHours = Number.parseInt(hours, 10)
        const response = await logService.viewLogs(selectedLog, {
          limit: 100,
          offset: nextOffset,
          level: level === 'ALL' ? undefined : level,
          search: query.trim() || undefined,
          hours: Number.isFinite(parsedHours) && parsedHours > 0 ? parsedHours : undefined,
        })
        setEntries((prev) => (append ? [...prev, ...response.logs] : response.logs))
        setTotal(response.pagination.total)
        setHasMore(response.pagination.has_more)
        setOffset(nextOffset)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load logs')
      } finally {
        setLoading(false)
      }
    },
    [hours, level, query, selectedLog],
  )

  useEffect(() => {
    loadFiles().catch((err) => {
      setError(err instanceof Error ? err.message : 'Failed to load log files')
    })
  }, [loadFiles])

  useEffect(() => {
    setOffset(0)
    loadEntries(0, false)
  }, [loadEntries])

  const onRefresh = async () => {
    await loadFiles()
    await loadEntries(0, false)
  }

  const onLoadMore = async () => {
    if (!hasMore || loading) return
    await loadEntries(offset + 100, true)
  }

  const onDownload = async () => {
    if (!selectedLog) return
    setError(null)
    try {
      await logService.downloadLogFile(selectedLog)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to download log file')
    }
  }

  return (
    <section className="dev-logs-page" aria-label="Developer logs">
      <div className="dev-logs-header">
        <div>
          <h2>Developer Logs</h2>
          <p>Inspect backend log files with severity, time, and text filters.</p>
        </div>
        <div className="dev-logs-actions">
          <button className="btn-secondary" type="button" onClick={onDownload} disabled={!selectedLog}>
            <Download size={16} aria-hidden="true" />
            Download
          </button>
          <button className="btn-primary" type="button" onClick={onRefresh} disabled={loading}>
            <RefreshCw size={16} aria-hidden="true" className={loading ? 'is-spinning' : ''} />
            Refresh
          </button>
        </div>
      </div>

      <div className="dev-logs-toolbar">
        <label className="dev-logs-field">
          <span>Log file</span>
          <select value={selectedLog} onChange={(event) => setSelectedLog(event.target.value)}>
            {fileOptions.length === 0 ? <option value="">No log files</option> : null}
            {fileOptions.map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </select>
        </label>

        <label className="dev-logs-field is-small">
          <span>Hours</span>
          <input value={hours} onChange={(event) => setHours(event.target.value)} inputMode="numeric" />
        </label>

        <label className="dev-logs-field is-search">
          <span>Search</span>
          <div className="dev-logs-search">
            <Search size={16} aria-hidden="true" />
            <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="message contains..." />
          </div>
        </label>
      </div>

      <div className="dev-logs-levels" role="tablist" aria-label="Severity filter">
        {LEVELS.map((item) => (
          <button
            key={item}
            type="button"
            role="tab"
            aria-selected={level === item}
            className={`dev-logs-level ${level === item ? 'is-active' : ''}`}
            onClick={() => setLevel(item)}
          >
            {item}
          </button>
        ))}
      </div>

      {error ? <div className="dev-logs-error">{error}</div> : null}

      <div className="dev-logs-summary">
        <span>{entries.length} shown</span>
        <span>{total} matched</span>
        <span>{selectedLog || '-'}</span>
      </div>

      <div className="dev-logs-table-wrap">
        <table className="dev-logs-table">
          <thead>
            <tr>
              <th>Time</th>
              <th>Severity</th>
              <th>Line</th>
              <th>Message</th>
            </tr>
          </thead>
          <tbody>
            {entries.length === 0 ? (
              <tr>
                <td colSpan={4} className="dev-logs-empty">
                  {loading ? 'Loading logs...' : 'No log entries match the current filters.'}
                </td>
              </tr>
            ) : (
              entries.map((entry, index) => (
                <tr key={`${entry.line_number}-${index}`}>
                  <td className="dev-logs-time">{formatTimestamp(entry.timestamp)}</td>
                  <td>
                    <span className={`dev-logs-badge ${levelClass(entry.level)}`}>{normalizeLevel(entry.level)}</span>
                  </td>
                  <td className="dev-logs-line">{entry.line_number}</td>
                  <td className="dev-logs-message">{entry.message}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      <div className="dev-logs-footer">
        <button className="btn-secondary" type="button" onClick={onLoadMore} disabled={!hasMore || loading}>
          Load more
        </button>
      </div>
    </section>
  )
}

