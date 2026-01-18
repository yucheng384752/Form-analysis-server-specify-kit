// src/pages/RegisterPage.tsx
import { useEffect, useMemo, useState } from 'react'
import { useToast } from '../components/common/ToastContext'
import { clearApiKeyValue, getApiKeyValue, setApiKeyValue } from '../services/auth'
import { clearTenantId, getTenantId, setTenantId } from '../services/tenant'
import { clearAdminApiKeyValue, getAdminApiKeyHeaderName, setAdminApiKeyValue } from '../services/adminAuth'
import './../styles/register-page.css'

type TenantRow = {
  id: string
  name?: string
  code?: string
  is_active?: boolean
  is_default?: boolean
}

type WhoAmI = {
  is_admin: boolean
  tenant_id?: string | null
  actor_user_id?: string | null
  actor_role?: string | null
  api_key_label?: string | null
}

export function RegisterPage(props: { onAdminUnlocked?: (ok: boolean) => void }) {
  const { showToast } = useToast()

  const maskKey = (raw: string) => {
    const v = String(raw || '').trim()
    if (!v) return ''
    if (v.length <= 8) return `${v.slice(0, 2)}…${v.slice(-2)}`
    return `${v.slice(0, 4)}…${v.slice(-4)}`
  }

  const [tenants, setTenants] = useState<TenantRow[] | null>(null)
  const [loadingTenants, setLoadingTenants] = useState(false)

  const [loginTenantCode, setLoginTenantCode] = useState('')
  const [loginUsername, setLoginUsername] = useState('')
  const [loginPassword, setLoginPassword] = useState('')
  const [loginLoading, setLoginLoading] = useState(false)

  const [adminKeyDraft, setAdminKeyDraft] = useState('')
  const [adminKeyLoading, setAdminKeyLoading] = useState(false)

  const [whoami, setWhoami] = useState<WhoAmI | null>(null)
  const [diagLoading, setDiagLoading] = useState(false)

  const [storedTenantId, setStoredTenantIdState] = useState(() => getTenantId())
  const [storedApiKeyMasked, setStoredApiKeyMasked] = useState(() => maskKey(getApiKeyValue()))
  const [tenantsAuthRequired, setTenantsAuthRequired] = useState<boolean | null>(null)

  const hasApiKey = useMemo(() => Boolean(storedApiKeyMasked), [storedApiKeyMasked])

  // Auto refresh whoami when API key exists (for role-based UI)
  useEffect(() => {
    if (!hasApiKey) {
      setWhoami(null)
      return
    }
    if (whoami) return

    let cancelled = false
    ;(async () => {
      try {
        const res = await fetch('/api/auth/whoami')
        if (!res.ok) return
        const body = (await res.json().catch(() => ({}))) as WhoAmI
        if (!cancelled) setWhoami(body)
      } catch {
        // ignore
      }
    })()

    return () => {
      cancelled = true
    }
  }, [hasApiKey, whoami])

  const handleFetchDiagnostics = async () => {
    setDiagLoading(true)
    try {
      const res = await fetch('/api/auth/whoami')
      const body = await res.json().catch(() => ({}))
      if (!res.ok) {
        showToast('error', '自檢失敗：請確認後端可連線，並已登入')
        return
      }
      setWhoami(body as WhoAmI)
      showToast('success', '已更新自檢資訊')
    } catch {
      showToast('error', '自檢失敗（網路或伺服器未啟動）')
    } finally {
      setDiagLoading(false)
    }
  }

  const refreshTenants = async () => {
    setLoadingTenants(true)
    try {
      const res = await fetch('/api/tenants')
      if (!res.ok) {
        const body = await res.json().catch(() => ({}))
        const detail = (body as any)?.detail
        if (res.status === 401) {
          showToast('error', '後端已啟用權限驗證：請先登入（或由管理者完成初始化）')
          setTenantsAuthRequired(true)
          setTenants(null)
          return
        }
        showToast('error', typeof detail === 'string' ? detail : `取得 tenants 失敗 (HTTP ${res.status})`)
        setTenants(null)
        return
      }
      const data = (await res.json()) as TenantRow[]
      setTenants(Array.isArray(data) ? data : [])
      setTenantsAuthRequired(false)
      showToast('success', `已取得 tenants：${Array.isArray(data) ? data.length : 0} 筆`)
    } catch {
      showToast('error', '取得 tenants 失敗（網路或伺服器未啟動）')
      setTenants(null)
    } finally {
      setLoadingTenants(false)
    }
  }

  const handleClearApiKey = () => {
    clearApiKeyValue()
    setStoredApiKeyMasked('')
    showToast('info', '已清除權限憑證（localStorage）')
  }

  const handleSetTenant = (id: string) => {
    const trimmed = String(id || '').trim()
    if (!trimmed) {
      showToast('error', 'tenant id 不可為空')
      return
    }
    setTenantId(trimmed)
    setStoredTenantIdState(trimmed)
    showToast('success', `已設定 Tenant ID：${trimmed}`)
  }

  const handleClearTenant = () => {
    clearTenantId()
    setStoredTenantIdState('')
    showToast('info', '已清除 Tenant ID（localStorage）')
  }

  const handlePasswordLogin = async () => {
    const username = loginUsername.trim()
    const password = loginPassword
    const tenantCode = loginTenantCode.trim()
    if (!username) {
      showToast('error', '請輸入帳號')
      return
    }
    if (!password) {
      showToast('error', '請輸入密碼')
      return
    }

    setLoginLoading(true)
    try {
      const res = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tenant_code: tenantCode || undefined, username, password }),
      })
      const body = await res.json().catch(() => ({}))
      const detail = (body as any)?.detail
      if (!res.ok) {
        showToast('error', typeof detail === 'string' ? detail : `登入失敗 (HTTP ${res.status})`)
        return
      }

      const tenantId = String((body as any)?.tenant_id || '')
      const apiKey = String((body as any)?.api_key || '')
      if (!tenantId || !apiKey) {
        showToast('error', '登入成功但回傳格式不完整')
        return
      }

      setTenantId(tenantId)
      setStoredTenantIdState(tenantId)

      setApiKeyValue(apiKey)
      setStoredApiKeyMasked(maskKey(apiKey))

      setLoginPassword('')
      showToast('success', '登入成功：已自動保存場域與權限')
    } catch {
      showToast('error', '登入失敗（網路或伺服器未啟動）')
    } finally {
      setLoginLoading(false)
    }
  }

  const handleVerifyAdminKey = async () => {
    const key = adminKeyDraft.trim()
    if (!key) {
      showToast('error', '請輸入管理者金鑰')
      return
    }

    setAdminKeyLoading(true)
    try {
      // Verify by calling bootstrap-status (admin-only).
      const res = await fetch('/api/auth/bootstrap-status', {
        headers: {
          [getAdminApiKeyHeaderName()]: key,
        },
      })

      if (!res.ok) {
        const body = await res.json().catch(() => ({}))
        const detail = (body as any)?.detail
        showToast('error', typeof detail === 'string' ? detail : '管理者金鑰無效')
        clearAdminApiKeyValue()
        props.onAdminUnlocked?.(false)
        return
      }

      setAdminApiKeyValue(key)
      setAdminKeyDraft('')
      props.onAdminUnlocked?.(true)
      showToast('success', '管理者金鑰驗證成功：已解鎖「管理者」頁籤')
    } catch {
      showToast('error', '管理者金鑰驗證失敗（網路或伺服器未啟動）')
    } finally {
      setAdminKeyLoading(false)
    }
  }

  return (
    <div className="register-page">
      <section className="register-card">
        <h2 className="register-title">登入</h2>

        {!hasApiKey ? (
          <>
            <div className="register-form">
              <div className="register-row">
                <label className="register-label" style={{ minWidth: 220, flex: 1 }}>
                  場域代碼（可留空）
                  <input
                    className="register-input"
                    type="text"
                    placeholder="例如：ut"
                    value={loginTenantCode}
                    onChange={(e) => setLoginTenantCode(e.target.value)}
                  />
                </label>
                <label className="register-label" style={{ minWidth: 220, flex: 1 }}>
                  帳號
                  <input
                    className="register-input"
                    type="text"
                    placeholder="請輸入帳號"
                    value={loginUsername}
                    onChange={(e) => setLoginUsername(e.target.value)}
                  />
                </label>
                <label className="register-label" style={{ minWidth: 220, flex: 1 }}>
                  密碼
                  <input
                    className="register-input"
                    type="password"
                    placeholder="請輸入密碼"
                    value={loginPassword}
                    onChange={(e) => setLoginPassword(e.target.value)}
                  />
                </label>
              </div>

              <div className="register-actions">
                <button className="btn-primary" disabled={loginLoading} onClick={handlePasswordLogin}>
                  {loginLoading ? '登入中…' : '登入'}
                </button>
              </div>
            </div>

            <details
              className="register-details"
              open={false}
            >
              <summary className="register-summary">提示</summary>
              <div className="register-hint">
                需要建立第一個 Tenant / Tenant 管理者時，可在此驗證管理者金鑰，驗證成功後會顯示「管理者」頁籤。
              </div>
              <div className="register-form" style={{ marginTop: '0.75rem' }}>
                <label className="register-label">
                  管理者金鑰
                  <input
                    className="register-input"
                    type="password"
                    placeholder="請貼上金鑰"
                    value={adminKeyDraft}
                    onChange={(e) => setAdminKeyDraft(e.target.value)}
                  />
                </label>
                <div className="register-actions">
                  <button className="btn-secondary" disabled={adminKeyLoading} onClick={handleVerifyAdminKey}>
                    {adminKeyLoading ? '驗證中…' : '驗證並解鎖管理者'}
                  </button>
                </div>
              </div>
            </details>
          </>
        ) : (
          <>
            <div className="register-row" style={{ marginTop: '0.75rem' }}>
              <div className="register-kv">
                <div className="register-k">Tenant ID</div>
                <div className="register-v">{storedTenantId ? <code>{storedTenantId}</code> : <span className="muted">（未保存）</span>}</div>
              </div>
              <div className="register-kv">
                <div className="register-k">角色</div>
                <div className="register-v">
                  {whoami ? (
                    <code>{whoami.is_admin ? 'admin' : (whoami.actor_role || 'user')}</code>
                  ) : (
                    <span className="muted">（讀取中…）</span>
                  )}
                </div>
              </div>
              <div className="register-actions">
                <button className="btn-secondary" disabled={diagLoading} onClick={handleFetchDiagnostics}>
                  {diagLoading ? '讀取中…' : '更新身分'}
                </button>
                <button className="btn-secondary" onClick={handleClearApiKey}>登出（清除登入資訊）</button>
              </div>
            </div>

            <details className="register-details" open>
              <summary className="register-summary">場域（Tenant）設定</summary>
              <div className="register-row">
                <div className="register-kv">
                  <div className="register-k">目前已選擇的場域（Tenant ID）</div>
                  <div className="register-v">{storedTenantId ? <code>{storedTenantId}</code> : <span className="muted">（無）</span>}</div>
                </div>
                <div className="register-actions">
                  <button className="btn-secondary" onClick={handleClearTenant}>清除 Tenant ID</button>
                </div>
              </div>

              <div className="register-actions">
                <button className="btn-secondary" disabled={loadingTenants} onClick={refreshTenants}>
                  {loadingTenants ? '讀取中…' : '刷新 tenants 列表'}
                </button>
                {tenantsAuthRequired === true && <span className="muted">（此環境需要 key 才能讀取 tenants）</span>}
              </div>

              {tenants && (
                <div className="register-tenants">
                  <div className="register-tenants-title">tenants</div>
                  {tenants.length === 0 ? (
                    <div className="muted">（目前為空）</div>
                  ) : (
                    <div className="register-tenants-grid">
                      {tenants.map((t) => (
                        <div key={t.id} className="register-tenant-item">
                          <div className="register-tenant-id"><code>{t.id}</code></div>
                          <div className="register-tenant-meta muted">
                            name={t.name ?? '-'} / code={t.code ?? '-'}
                          </div>
                          <div className="register-actions">
                            <button className="btn-secondary" onClick={() => handleSetTenant(t.id)}>使用此 Tenant</button>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </details>

            <details className="register-details">
              <summary className="register-summary">提示（管理者）</summary>
              <div className="register-hint">如需初始化/管理 tenant 與使用者，請在此驗證管理者金鑰以解鎖「管理者」頁籤。</div>
              <div className="register-form" style={{ marginTop: '0.75rem' }}>
                <label className="register-label">
                  管理者金鑰
                  <input
                    className="register-input"
                    type="password"
                    placeholder="請貼上金鑰"
                    value={adminKeyDraft}
                    onChange={(e) => setAdminKeyDraft(e.target.value)}
                  />
                </label>
                <div className="register-actions">
                  <button className="btn-secondary" disabled={adminKeyLoading} onClick={handleVerifyAdminKey}>
                    {adminKeyLoading ? '驗證中…' : '驗證並解鎖管理者'}
                  </button>
                </div>
              </div>
            </details>
          </>
        )}

      </section>
    </div>
  )
}
