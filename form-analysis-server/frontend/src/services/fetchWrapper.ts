import { ensureTenantIdWithOptions, TENANT_STORAGE_KEY } from './tenant'
import { getApiKeyHeaderName, getApiKeyValue } from './auth'

// Global fetch wrapper: auto-inject X-Tenant-Id for all /api* requests except /api/tenants.
// This prevents accidental cross-tenant calls and removes per-call header boilerplate.
export function installGlobalFetchWrapper(): () => void {
  const originalFetch = window.fetch.bind(window)

  window.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
    try {
      let tenantId = window.localStorage.getItem(TENANT_STORAGE_KEY) || ''
      const apiKeyHeaderName = getApiKeyHeaderName()
      const apiKeyValue = getApiKeyValue()

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

      if (!isApiPath) {
        return originalFetch(input as any, init)
      }

      // Do not auto-inject admin headers globally.
      // Admin-only requests must explicitly set X-Admin-API-Key at call sites after the user
      // deliberately enables admin mode. This avoids surprising "admin parameter" usage on load.
      //
      // We still allow attaching the regular API key when present.
      if (isTenantListPath || isAuthPath) {
        const mergedHeaders = new Headers(init?.headers || (input instanceof Request ? input.headers : undefined))
        if (apiKeyValue) {
          mergedHeaders.set(apiKeyHeaderName, apiKeyValue)
        }

        // If no auth headers exist, call as-is.
        if (!apiKeyValue) {
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

        // Hard block tenant-scoped API calls when tenant is not explicitly selected.
        // This prevents silently using a default/guessed tenant.
        if (!effectiveTenantId) {
          return new Response(
            JSON.stringify({
              detail: '尚未選擇 Tenant（X-Tenant-Id）。請到「註冊/初始化」頁籤建立/選擇 Tenant 後再操作。',
            }),
            { status: 400, headers: { 'Content-Type': 'application/json' } },
          )
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
