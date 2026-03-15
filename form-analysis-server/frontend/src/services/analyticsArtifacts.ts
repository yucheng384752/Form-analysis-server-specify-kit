export type ArtifactKey =
  | 'serialized_events'
  | 'aggregated_diagnostics'
  | 'rag_results'
  | 'llm_reports'
  | 'weighted_contributions'

export type ArtifactListItem = {
  key: ArtifactKey | string
  filename: string
  exists: boolean
  size_bytes?: number | null
  mtime_epoch?: number | null
}

export type ArtifactInputResolveResult = {
  requested: string[]
  requested_count: number
  normalized_inputs: Record<string, string[]>
  resolved: string[]
  resolved_count: number
  unmatched: string[]
  unmatched_count: number
  matches: Record<string, string[]>
  match_diagnostics: Record<
    string,
    {
      candidate_count: number
      matched_by: string[]
      reason_code: string
      reason_message: string
    }
  >
  trace_tokens: Record<string, string[]>
  trace_attempted_count: number
  trace_resolved_count: number
  unmatched_reason_counts: Record<string, number>
}

export type ArtifactSnapshotBucket = {
  name: string
  count: number
}

export type ArtifactUnifiedSnapshot = {
  artifact_key: string
  sample_count: number
  station_distribution: ArtifactSnapshotBucket[]
  machine_distribution: ArtifactSnapshotBucket[]
  top_features: ArtifactSnapshotBucket[]
  metrics: Record<string, number>
}

export type MachineDistributionBucket = {
  name: string
  count: number
}

export type ComplaintAnalysisResult = {
  requested_ids: string[]
  mapping: Record<
    string,
    {
      matched_stage: string
      missing_stages?: string[]
      trace_status?: {
        p1: boolean
        p2: boolean
        p3: boolean
      }
    }
  >
  source_scope: {
    requested_count: number
    resolved_count: number
    merged_rows: number
  }
  analysis: Record<string, unknown>
  machine_distribution?: MachineDistributionBucket[]
  winder_distribution?: MachineDistributionBucket[]
  timing: {
    trace_ms: number
    scope_ms: number
    analysis_ms: number
    total_ms: number
  }
  elapsed_ms?: number
}

function parseRetryAfterMs(res: Response): number {
  const raw = (res.headers.get('Retry-After') || '').trim()
  if (!raw) return 1200
  const asNum = Number(raw)
  if (Number.isFinite(asNum) && asNum >= 0) return Math.round(asNum * 1000)
  const asDate = Date.parse(raw)
  if (!Number.isNaN(asDate)) return Math.max(0, asDate - Date.now())
  return 1200
}

async function fetchWith429Retry(
  url: string,
  init?: RequestInit,
  opts?: { maxRetries?: number; label?: string },
): Promise<Response> {
  const maxRetries = Math.max(0, opts?.maxRetries ?? 1)
  let attempt = 0
  let lastRes: Response | null = null

  while (attempt <= maxRetries) {
    const res = await fetch(url, init)
    lastRes = res
    if (res.status !== 429) return res
    if (attempt >= maxRetries) break
    const waitMs = parseRetryAfterMs(res)
    await new Promise((r) => window.setTimeout(r, waitMs))
    attempt += 1
  }

  if (lastRes) return lastRes
  throw new Error(opts?.label ? `${opts.label}: request failed` : 'request failed')
}

export async function fetchArtifactList(opts?: { headers?: Record<string, string> }): Promise<ArtifactListItem[]> {
  const init: RequestInit = {}
  if (opts?.headers) init.headers = opts.headers
  const res = await fetchWith429Retry('/api/v2/analytics/artifacts', init, { label: 'fetch artifacts list' })
  if (!res.ok) {
    const text = await res.text().catch(() => '')
    if (res.status === 429) {
      throw new Error('Rate limit exceeded while loading artifacts list. Please retry in a moment.')
    }
    throw new Error(text || `Failed to load artifacts list (HTTP ${res.status})`)
  }
  const json = (await res.json()) as unknown
  if (!Array.isArray(json)) return []
  return json as ArtifactListItem[]
}

export async function fetchArtifactJson(key: ArtifactKey, opts?: { headers?: Record<string, string> }): Promise<unknown> {
  // Backwards-compat: callers should migrate to list/detail endpoints.
  return fetchArtifactListView(key, opts)
}

export async function fetchArtifactListView(
  key: ArtifactKey,
  opts?: { headers?: Record<string, string> },
  params?: { productIds?: string[] },
): Promise<unknown> {
  const init: RequestInit = {}
  if (opts?.headers) init.headers = opts.headers

  const url = new URL(`/api/v2/analytics/artifacts/${encodeURIComponent(key)}/list`, window.location.origin)
  const pids = (params?.productIds ?? []).map((s) => s.trim()).filter(Boolean)
  if (pids.length > 0) {
    url.searchParams.set('product_ids', pids.join(','))
  }

  const res = await fetchWith429Retry(url.toString(), init, { label: `fetch artifact list ${key}` })
  if (!res.ok) {
    const text = await res.text().catch(() => '')
    if (res.status === 429) {
      throw new Error(`Rate limit exceeded for ${key} list query. Please retry in a moment.`)
    }
    throw new Error(text || `Failed to load artifact list ${key} (HTTP ${res.status})`)
  }
  return (await res.json()) as unknown
}

export async function resolveArtifactProductInputs(
  key: ArtifactKey,
  opts?: { headers?: Record<string, string> },
  params?: { productIds?: string[] },
): Promise<ArtifactInputResolveResult> {
  const init: RequestInit = {}
  if (opts?.headers) init.headers = opts.headers

  const url = new URL(
    `/api/v2/analytics/artifacts/${encodeURIComponent(key)}/resolve-input`,
    window.location.origin,
  )
  const pids = (params?.productIds ?? []).map((s) => s.trim()).filter(Boolean)
  if (pids.length > 0) {
    url.searchParams.set('product_ids', pids.join(','))
  }

  const res = await fetchWith429Retry(url.toString(), init, { label: `resolve artifact inputs ${key}` })
  if (!res.ok) {
    const text = await res.text().catch(() => '')
    if (res.status === 429) {
      throw new Error(`Rate limit exceeded while resolving product_id inputs for ${key}. Please retry in a moment.`)
    }
    throw new Error(text || `Failed to resolve artifact inputs ${key} (HTTP ${res.status})`)
  }
  const json = (await res.json()) as Partial<ArtifactInputResolveResult>
  const normalizedInputs =
    json.normalized_inputs && typeof json.normalized_inputs === 'object'
      ? (json.normalized_inputs as Record<string, string[]>)
      : {}
  const matchDiagnosticsRaw =
    json.match_diagnostics && typeof json.match_diagnostics === 'object'
      ? (json.match_diagnostics as Record<string, any>)
      : {}
  const traceTokens =
    json.trace_tokens && typeof json.trace_tokens === 'object'
      ? (json.trace_tokens as Record<string, string[]>)
      : {}

  const matchDiagnostics: ArtifactInputResolveResult['match_diagnostics'] = {}
  for (const [k, v] of Object.entries(matchDiagnosticsRaw)) {
    const obj = v && typeof v === 'object' ? (v as Record<string, unknown>) : {}
    matchDiagnostics[k] = {
      candidate_count: Number(obj.candidate_count) || 0,
      matched_by: Array.isArray(obj.matched_by) ? obj.matched_by.map((x) => String(x).trim()).filter(Boolean) : [],
      reason_code: typeof obj.reason_code === 'string' ? obj.reason_code : '',
      reason_message: typeof obj.reason_message === 'string' ? obj.reason_message : '',
    }
  }

  return {
    requested: Array.isArray(json.requested) ? (json.requested as string[]) : [],
    requested_count: Number((json as any).requested_count) || (Array.isArray(json.requested) ? json.requested.length : 0),
    normalized_inputs: normalizedInputs,
    resolved: Array.isArray(json.resolved) ? (json.resolved as string[]) : [],
    resolved_count: Number((json as any).resolved_count) || (Array.isArray(json.resolved) ? json.resolved.length : 0),
    unmatched: Array.isArray(json.unmatched) ? (json.unmatched as string[]) : [],
    unmatched_count: Number((json as any).unmatched_count) || (Array.isArray(json.unmatched) ? json.unmatched.length : 0),
    matches: json.matches && typeof json.matches === 'object' ? (json.matches as Record<string, string[]>) : {},
    match_diagnostics: matchDiagnostics,
    trace_tokens: traceTokens,
    trace_attempted_count: Number((json as any).trace_attempted_count) || 0,
    trace_resolved_count: Number((json as any).trace_resolved_count) || 0,
    unmatched_reason_counts:
      (json as any).unmatched_reason_counts && typeof (json as any).unmatched_reason_counts === 'object'
        ? ((json as any).unmatched_reason_counts as Record<string, number>)
        : {},
  }
}

export async function fetchArtifactDetailView(
  key: ArtifactKey,
  itemId: string,
  opts?: { headers?: Record<string, string> },
): Promise<unknown> {
  const init: RequestInit = {}
  if (opts?.headers) init.headers = opts.headers
  const res = await fetchWith429Retry(
    `/api/v2/analytics/artifacts/${encodeURIComponent(key)}/detail/${encodeURIComponent(itemId)}`,
    init,
    { label: `fetch artifact detail ${key}/${itemId}` },
  )
  if (!res.ok) {
    const text = await res.text().catch(() => '')
    if (res.status === 429) {
      throw new Error(`Rate limit exceeded while loading detail ${key}/${itemId}. Please retry in a moment.`)
    }
    throw new Error(text || `Failed to load artifact detail ${key}/${itemId} (HTTP ${res.status})`)
  }
  return (await res.json()) as unknown
}

export async function fetchArtifactSnapshotView(
  key: ArtifactKey,
  opts?: { headers?: Record<string, string> },
  params?: { productIds?: string[] },
): Promise<ArtifactUnifiedSnapshot> {
  const init: RequestInit = {}
  if (opts?.headers) init.headers = opts.headers

  const url = new URL(
    `/api/v2/analytics/artifacts/${encodeURIComponent(key)}/snapshot`,
    window.location.origin,
  )
  const pids = (params?.productIds ?? []).map((s) => s.trim()).filter(Boolean)
  if (pids.length > 0) {
    url.searchParams.set('product_ids', pids.join(','))
  }

  const res = await fetchWith429Retry(url.toString(), init, { label: `fetch artifact snapshot ${key}` })
  if (!res.ok) {
    const text = await res.text().catch(() => '')
    if (res.status === 429) {
      throw new Error(`Rate limit exceeded for ${key} snapshot query. Please retry in a moment.`)
    }
    throw new Error(text || `Failed to load artifact snapshot ${key} (HTTP ${res.status})`)
  }

  const json = (await res.json()) as Partial<ArtifactUnifiedSnapshot>
  const buckets = (value: unknown): ArtifactSnapshotBucket[] =>
    Array.isArray(value)
      ? value
          .filter((x) => x && typeof x === 'object')
          .map((x: any) => ({
            name: String(x.name ?? '').trim(),
            count: Number(x.count) || 0,
          }))
          .filter((x) => x.name)
      : []

  return {
    artifact_key: typeof json.artifact_key === 'string' ? json.artifact_key : String(key),
    sample_count: Number(json.sample_count) || 0,
    station_distribution: buckets(json.station_distribution),
    machine_distribution: buckets(json.machine_distribution),
    top_features: buckets(json.top_features),
    metrics: json.metrics && typeof json.metrics === 'object' ? (json.metrics as Record<string, number>) : {},
  }
}

export async function fetchComplaintAnalysis(
  opts?: { headers?: Record<string, string> },
  payload?: { productIds?: string[]; includeBasicStats?: boolean; includeOutliers?: boolean; includeContribution?: boolean },
): Promise<ComplaintAnalysisResult> {
  const init: RequestInit = {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(opts?.headers || {}),
    },
    body: JSON.stringify({
      product_ids: (payload?.productIds ?? []).map((s) => s.trim()).filter(Boolean),
      include_basic_stats: payload?.includeBasicStats ?? true,
      include_outliers: payload?.includeOutliers ?? true,
      include_contribution: payload?.includeContribution ?? false,
    }),
  }

  const res = await fetchWith429Retry('/api/v2/analytics/complaint-analysis', init, {
    label: 'complaint analysis',
  })
  if (!res.ok) {
    const text = await res.text().catch(() => '')
    if (res.status === 429) {
      throw new Error('Rate limit exceeded while running complaint analysis. Please retry in a moment.')
    }
    throw new Error(text || `Failed to run complaint analysis (HTTP ${res.status})`)
  }

  const json = (await res.json()) as Partial<ComplaintAnalysisResult> & Record<string, any>
  return {
    requested_ids: Array.isArray(json.requested_ids) ? (json.requested_ids as string[]) : [],
    mapping: json.mapping && typeof json.mapping === 'object' ? (json.mapping as ComplaintAnalysisResult['mapping']) : {},
    source_scope:
      json.source_scope && typeof json.source_scope === 'object'
        ? (json.source_scope as ComplaintAnalysisResult['source_scope'])
        : {
            requested_count: 0,
            resolved_count: 0,
            merged_rows: 0,
          },
    analysis: json.analysis && typeof json.analysis === 'object' ? (json.analysis as Record<string, unknown>) : {},
    machine_distribution: Array.isArray(json.machine_distribution)
      ? (json.machine_distribution as ComplaintAnalysisResult['machine_distribution'])
      : [],
    winder_distribution: Array.isArray(json.winder_distribution)
      ? (json.winder_distribution as ComplaintAnalysisResult['winder_distribution'])
      : [],
    timing:
      json.timing && typeof json.timing === 'object'
        ? (json.timing as ComplaintAnalysisResult['timing'])
        : {
            trace_ms: 0,
            scope_ms: 0,
            analysis_ms: 0,
            total_ms: 0,
          },
    elapsed_ms: Number(json.elapsed_ms) || 0,
  }
}
