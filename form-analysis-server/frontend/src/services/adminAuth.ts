export const ADMIN_API_KEY_STORAGE_KEY = 'form_analysis_admin_api_key'

export function getAdminApiKeyHeaderName(): string {
  return 'X-Admin-API-Key'
}

export function getAdminApiKeyValue(): string {
  try {
    const stored = window.localStorage.getItem(ADMIN_API_KEY_STORAGE_KEY) || ''
    return stored.trim()
  } catch {
    return ''
  }
}

export function setAdminApiKeyValue(rawKey: string): void {
  const value = String(rawKey || '').trim()
  try {
    if (!value) {
      window.localStorage.removeItem(ADMIN_API_KEY_STORAGE_KEY)
      return
    }
    window.localStorage.setItem(ADMIN_API_KEY_STORAGE_KEY, value)
  } catch {
    // ignore
  }
}

export function clearAdminApiKeyValue(): void {
  try {
    window.localStorage.removeItem(ADMIN_API_KEY_STORAGE_KEY)
  } catch {
    // ignore
  }
}
