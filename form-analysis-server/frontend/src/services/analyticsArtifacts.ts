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

export async function fetchArtifactList(opts?: { headers?: Record<string, string> }): Promise<ArtifactListItem[]> {
  const init: RequestInit = {}
  if (opts?.headers) init.headers = opts.headers
  const res = await fetch('/api/v2/analytics/artifacts', init)
  if (!res.ok) {
    const text = await res.text().catch(() => '')
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

  const res = await fetch(url.toString(), init)
  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new Error(text || `Failed to load artifact list ${key} (HTTP ${res.status})`)
  }
  return (await res.json()) as unknown
}

export async function fetchArtifactDetailView(
  key: ArtifactKey,
  itemId: string,
  opts?: { headers?: Record<string, string> },
): Promise<unknown> {
  const init: RequestInit = {}
  if (opts?.headers) init.headers = opts.headers
  const res = await fetch(
    `/api/v2/analytics/artifacts/${encodeURIComponent(key)}/detail/${encodeURIComponent(itemId)}`,
    init,
  )
  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new Error(text || `Failed to load artifact detail ${key}/${itemId} (HTTP ${res.status})`)
  }
  return (await res.json()) as unknown
}
