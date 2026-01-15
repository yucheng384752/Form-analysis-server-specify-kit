export const TENANT_STORAGE_KEY = 'form_analysis_tenant_id'

const API_BASE_URL = (import.meta.env?.VITE_API_URL as string) || ''

type TenantRow = {
  id: string
  name?: string
  code?: string
  is_active?: boolean
}

let inFlight: Promise<string> | null = null

/**
 * Ensure a tenant id exists in localStorage.
 * - If one is already stored, returns it.
 * - If none is stored and backend returns exactly one tenant, auto-select it.
 * - If multiple tenants exist, returns empty string (caller must rely on UI selection).
 */
export async function ensureTenantId(): Promise<string> {
  const existing = window.localStorage.getItem(TENANT_STORAGE_KEY) || ''
  if (existing) return existing

  if (!inFlight) {
    inFlight = (async () => {
      try {
        const tenantsUrl = API_BASE_URL ? `${API_BASE_URL}/api/tenants` : '/api/tenants'
        const res = await fetch(tenantsUrl)
        if (!res.ok) return ''
        const tenants = (await res.json()) as TenantRow[]
        if (Array.isArray(tenants) && tenants.length === 1 && tenants[0]?.id) {
          const id = String(tenants[0].id)
          window.localStorage.setItem(TENANT_STORAGE_KEY, id)
          return id
        }
        return ''
      } catch {
        return ''
      } finally {
        inFlight = null
      }
    })()
  }

  return inFlight
}
