import { beforeEach, describe, expect, it, vi } from 'vitest'

import { clearTenantId, ensureTenantId, getTenantId, setTenantId, TENANT_STORAGE_KEY } from './tenant'

function mockFetchSequence(responses: Array<{ ok: boolean; json: any; status?: number }>) {
  const fetchMock = vi.fn()
  for (const r of responses) {
    fetchMock.mockResolvedValueOnce({
      ok: r.ok,
      status: r.status ?? (r.ok ? 200 : 500),
      json: vi.fn().mockResolvedValue(r.json),
    })
  }
  // @ts-expect-error test override
  global.fetch = fetchMock
  return fetchMock
}

describe('ensureTenantId (strict)', () => {
  beforeEach(() => {
    window.localStorage.clear()
    vi.restoreAllMocks()
  })

  it('setTenantId stores tenant id and getTenantId reads it', () => {
    setTenantId('t-set')
    expect(window.localStorage.getItem(TENANT_STORAGE_KEY)).toBe('t-set')
    expect(getTenantId()).toBe('t-set')
  })

  it('clearTenantId removes stored tenant id', () => {
    setTenantId('t-set')
    clearTenantId()
    expect(window.localStorage.getItem(TENANT_STORAGE_KEY)).toBeNull()
    expect(getTenantId()).toBe('')
  })

  it('ensureTenantId returns immediately when setTenantId has been called (no fetch)', async () => {
    const fetchMock = vi.fn()
    // @ts-expect-error test override
    global.fetch = fetchMock

    setTenantId('t-fast')
    const id = await ensureTenantId()
    expect(id).toBe('t-fast')
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('keeps existing localStorage tenant when it still exists in backend tenants list', async () => {
    window.localStorage.setItem(TENANT_STORAGE_KEY, 'tenant-123')
    const fetchMock = mockFetchSequence([
      { ok: true, json: [{ id: 'tenant-123' }] },
    ])

    const id = await ensureTenantId()
    expect(id).toBe('tenant-123')
    expect(window.localStorage.getItem(TENANT_STORAGE_KEY)).toBe('tenant-123')
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })

  it('repairs stale localStorage tenant by selecting the only backend tenant', async () => {
    window.localStorage.setItem(TENANT_STORAGE_KEY, 'stale-tenant')
    const fetchMock = mockFetchSequence([
      { ok: true, json: [{ id: 't1' }] },
    ])

    const id = await ensureTenantId()
    expect(id).toBe('t1')
    expect(window.localStorage.getItem(TENANT_STORAGE_KEY)).toBe('t1')
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })

  it('repairs stale localStorage tenant by creating a default tenant when backend has none', async () => {
    window.localStorage.setItem(TENANT_STORAGE_KEY, 'stale-tenant')
    const fetchMock = mockFetchSequence([
      { ok: true, json: [] },
      { ok: true, json: { id: 'created-1' }, status: 201 },
    ])

    const id = await ensureTenantId()
    expect(id).toBe('created-1')
    expect(window.localStorage.getItem(TENANT_STORAGE_KEY)).toBe('created-1')
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })

  it('when GET /api/tenants returns 1 tenant, stores and returns it', async () => {
    const fetchMock = mockFetchSequence([
      { ok: true, json: [{ id: 't1' }] },
    ])

    const id = await ensureTenantId()
    expect(id).toBe('t1')
    expect(window.localStorage.getItem(TENANT_STORAGE_KEY)).toBe('t1')
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })

  it('when GET /api/tenants returns 0, POST creates default and stores it', async () => {
    const fetchMock = mockFetchSequence([
      { ok: true, json: [] },
      { ok: true, json: { id: 'created-1' }, status: 201 },
    ])

    const id = await ensureTenantId()
    expect(id).toBe('created-1')
    expect(window.localStorage.getItem(TENANT_STORAGE_KEY)).toBe('created-1')
    expect(fetchMock).toHaveBeenCalledTimes(2)

    // Ensure the default bootstrap tenant payload is UT/ut
    const secondCall = fetchMock.mock.calls[1]
    expect(secondCall?.[0]).toContain('/api/tenants')
    const init = (secondCall?.[1] || {}) as RequestInit
    expect(init.method).toBe('POST')
    expect(String(init.body)).toBe(JSON.stringify({ name: 'UT', code: 'ut', is_default: true, is_active: true }))

    // second call should use localStorage and not call fetch again
    const id2 = await ensureTenantId()
    expect(id2).toBe('created-1')
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })

  it('when POST create returns non-ok (e.g. 409), retries GET once and stores single tenant if present', async () => {
    const fetchMock = mockFetchSequence([
      { ok: true, json: [] },
      { ok: false, json: { detail: 'Tenant already exists' }, status: 409 },
      { ok: true, json: [{ id: 't-after-race' }] },
    ])

    const id = await ensureTenantId()
    expect(id).toBe('t-after-race')
    expect(window.localStorage.getItem(TENANT_STORAGE_KEY)).toBe('t-after-race')
    expect(fetchMock).toHaveBeenCalledTimes(3)
  })

  it('when GET /api/tenants returns multiple tenants, returns empty string and does not set localStorage', async () => {
    const fetchMock = mockFetchSequence([
      { ok: true, json: [{ id: 't1' }, { id: 't2' }] },
    ])

    const id = await ensureTenantId()
    expect(id).toBe('')
    expect(window.localStorage.getItem(TENANT_STORAGE_KEY)).toBeNull()
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })

  it('when GET /api/tenants fails, returns empty string', async () => {
    const fetchMock = mockFetchSequence([
      { ok: false, json: { detail: 'boom' }, status: 500 },
    ])

    const id = await ensureTenantId()
    expect(id).toBe('')
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })
})
