import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ensureTenantId, TENANT_STORAGE_KEY } from './tenant'
import { installGlobalFetchWrapper } from './fetchWrapper'
import { ADMIN_API_KEY_STORAGE_KEY } from './adminAuth'

type MockResponse = {
  ok: boolean
  status: number
  json: () => Promise<any>
  clone: () => MockResponse
}

function makeJsonResponse(status: number, body: any): MockResponse {
  const res: MockResponse = {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
    clone: () => res,
  }
  return res
}

function getUrlString(input: any): string {
  if (typeof input === 'string') return input
  if (input instanceof URL) return input.toString()
  if (input && typeof input.url === 'string') return input.url
  return String(input)
}

describe('installGlobalFetchWrapper (registration -> tenant header)', () => {
  beforeEach(() => {
    window.localStorage.clear()
    vi.restoreAllMocks()
  })

  it('after bootstrap (UT/ut) stores tenant id and auto-injects X-Tenant-Id for /api calls', async () => {
    // Simulate admin bootstrap key exists in browser.
    window.localStorage.setItem(ADMIN_API_KEY_STORAGE_KEY, 'adminkey-1')

    const calls: Array<{ url: string; headers: Record<string, string>; init?: RequestInit }> = []

    const originalFetch = vi.fn(async (input: any, init?: RequestInit) => {
      const url = new URL(getUrlString(input), window.location.href)

      const headers = new Headers(
        init?.headers || (input instanceof Request ? (input as Request).headers : undefined),
      )

      const headerSnapshot: Record<string, string> = {}
      headers.forEach((value, key) => {
        headerSnapshot[key] = value
      })

      calls.push({ url: url.pathname, headers: headerSnapshot, init })

      if (url.pathname === '/api/tenants' && (!init?.method || init.method === 'GET')) {
        expect(headers.get('X-Admin-API-Key')).toBe('adminkey-1')
        return makeJsonResponse(200, [])
      }

      if (url.pathname === '/api/tenants' && init?.method === 'POST') {
        expect(headers.get('X-Admin-API-Key')).toBe('adminkey-1')
        // UT bootstrap payload
        expect(String(init.body)).toBe(
          JSON.stringify({ name: 'UT', code: 'ut', is_default: true, is_active: true }),
        )
        return makeJsonResponse(201, { id: 'tenant-ut' })
      }

      if (url.pathname === '/api/upload' && (!init?.method || init.method === 'GET')) {
        // This call should carry the tenant header after registration/bootstrap.
        const effectiveHeaders = input instanceof Request ? (input as Request).headers : headers
        expect(effectiveHeaders.get('X-Tenant-Id')).toBe('tenant-ut')
        return makeJsonResponse(200, { ok: true })
      }

      return makeJsonResponse(200, { ok: true })
    })

    // Install wrapper on top of our mock fetch.
    // @ts-expect-error test override
    global.fetch = originalFetch
    // @ts-expect-error test override
    window.fetch = originalFetch

    const restore = installGlobalFetchWrapper()

    // Simulate registration/bootstrap: no tenants -> create default UT/ut -> store tenant id.
    const tenantId = await ensureTenantId()
    expect(tenantId).toBe('tenant-ut')
    expect(window.localStorage.getItem(TENANT_STORAGE_KEY)).toBe('tenant-ut')

    // Subsequent API calls should automatically include tenant header.
    await window.fetch('/api/upload')

    restore()

    // sanity: originalFetch was used for /api/tenants twice + /api/upload once.
    const paths = calls.map((c) => c.url)
    expect(paths).toContain('/api/tenants')
    expect(paths).toContain('/api/upload')
  })
})
