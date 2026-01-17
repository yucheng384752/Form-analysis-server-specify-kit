import { ensureTenantId, ensureTenantIdWithOptions, TENANT_STORAGE_KEY } from './tenant'
import { getApiKeyHeaderName, getApiKeyValue } from './auth'
import { getAdminApiKeyHeaderName, getAdminApiKeyValue } from './adminAuth'

// Global fetch wrapper: auto-inject X-Tenant-Id for all /api* requests except /api/tenants.
// This prevents accidental cross-tenant calls and removes per-call header boilerplate.
export function installGlobalFetchWrapper(): () => void {
  const originalFetch = window.fetch.bind(window)

  window.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
    try {
      let tenantId = window.localStorage.getItem(TENANT_STORAGE_KEY) || ''
      const apiKeyHeaderName = getApiKeyHeaderName()
      const apiKeyValue = getApiKeyValue()
      const adminKeyHeaderName = getAdminApiKeyHeaderName()
      const adminKeyValue = getAdminApiKeyValue()

      // Determine request URL
      const urlString =
        typeof input === 'string'
          ? input
          : input instanceof URL
            ? input.toString()
            : input.url

      const url = new URL(urlString, window.location.href)
      const isApiPath = url.pathname.startsWith('/api')
      const isTenantListPath = url.pathname.startsWith('/api/tenants')
      const isAuthPath = url.pathname.startsWith('/api/auth')

      // If tenant is missing but we are calling tenant-scoped APIs, try to auto-select
      // when exactly one tenant exists.
      if (!tenantId && isApiPath && !isTenantListPath && !isAuthPath) {
        tenantId = await ensureTenantId()
      }

      if (!isApiPath) {
        return originalFetch(input as any, init)
      }

      // Always attach auth headers when present, but do not force tenant header on /api/tenants or /api/auth.
      if (isTenantListPath || isAuthPath) {
        const mergedHeaders = new Headers(init?.headers || (input instanceof Request ? input.headers : undefined))

        // Allow admin bootstrap: /api/tenants and /api/auth/* may require admin key depending on operation.
        if (adminKeyValue) {
          mergedHeaders.set(adminKeyHeaderName, adminKeyValue)
        }
        if (apiKeyValue) {
          mergedHeaders.set(apiKeyHeaderName, apiKeyValue)
        }

        // If no auth headers exist, call as-is.
        if (!adminKeyValue && !apiKeyValue) {
          return originalFetch(input as any, init)
        }

        if (input instanceof Request) {
          // Clone to keep request body reusable.
          const wrappedRequest = new Request(input.clone(), { ...init, headers: mergedHeaders })
          return originalFetch(wrappedRequest)
        }

        return originalFetch(input as any, { ...init, headers: mergedHeaders })
      }

      const attemptFetch = async (forcedTenantId?: string) => {
        const effectiveTenantId = forcedTenantId ?? tenantId

        // If still no tenant id, call as-is (backend may auto-resolve when exactly one tenant exists)
        if (!effectiveTenantId) {
          return originalFetch(input as any, init)
        }

        const mergedHeaders = new Headers(init?.headers || (input instanceof Request ? input.headers : undefined))
        // Always set/override for tenant-scoped /api calls.
        mergedHeaders.set('X-Tenant-Id', effectiveTenantId)
        if (apiKeyValue) {
          mergedHeaders.set(apiKeyHeaderName, apiKeyValue)
        }

        if (input instanceof Request) {
          // Clone to keep request body reusable.
          const wrappedRequest = new Request(input.clone(), { ...init, headers: mergedHeaders })
          return originalFetch(wrappedRequest)
        }

        return originalFetch(input as any, { ...init, headers: mergedHeaders })
      }

      const res = await attemptFetch()
      if (res.status !== 404) return res

      // Auto-recover from stale tenant id after DB reset/reseed.
      try {
        const data = await res.clone().json().catch(() => null)
        const detail = typeof (data as any)?.detail === 'string' ? (data as any).detail : ''
        if (!detail || !detail.toLowerCase().includes('tenant not found')) {
          return res
        }

        const refreshed = await ensureTenantIdWithOptions({ notify: true, reason: 'recovery' })
        if (!refreshed) return res

        return await attemptFetch(refreshed)
      } catch {
        return res
      }
    } catch {
      // Fallback: never block fetch due to wrapper errors
      return originalFetch(input as any, init)
    }
  }

  return () => {
    window.fetch = originalFetch
  }
}
