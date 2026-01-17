// src/pages/RegisterPage.tsx
import { useEffect, useMemo, useState } from 'react'
import { useToast } from '../components/common/ToastContext'
import { clearApiKeyValue, getApiKeyValue, setApiKeyValue, API_KEY_STORAGE_KEY } from '../services/auth'
import {
  clearAdminApiKeyValue,
  getAdminApiKeyHeaderName,
  getAdminApiKeyValue,
  setAdminApiKeyValue,
  ADMIN_API_KEY_STORAGE_KEY,
} from '../services/adminAuth'
import { clearTenantId, ensureTenantIdWithOptions, getTenantId, setTenantId, TENANT_STORAGE_KEY } from '../services/tenant'
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

type BootstrapStatus = {
  auth_mode: string
  auth_api_key_header: string
  auth_protect_prefixes: string[]
  auth_exempt_paths: string[]
  admin_api_key_header: string
  admin_keys_configured: boolean
}

export function RegisterPage() {
  const { showToast } = useToast()

  const maskKey = (raw: string) => {
    const v = String(raw || '').trim()
    if (!v) return ''
    if (v.length <= 8) return `${v.slice(0, 2)}…${v.slice(-2)}`
    return `${v.slice(0, 4)}…${v.slice(-4)}`
  }

  const [adminKeyDraft, setAdminKeyDraft] = useState('')
  const [tenants, setTenants] = useState<TenantRow[] | null>(null)
  const [loadingTenants, setLoadingTenants] = useState(false)

  const [loginTenantCode, setLoginTenantCode] = useState('')
  const [loginUsername, setLoginUsername] = useState('')
  const [loginPassword, setLoginPassword] = useState('')
  const [loginLoading, setLoginLoading] = useState(false)

  const [createUserTenantCode, setCreateUserTenantCode] = useState('')
  const [createUsername, setCreateUsername] = useState('')
  const [createPassword, setCreatePassword] = useState('')
  const [createUserLoading, setCreateUserLoading] = useState(false)

  const [createTenantName, setCreateTenantName] = useState('')
  const [createTenantCode, setCreateTenantCode] = useState('')
  const [createTenantLoading, setCreateTenantLoading] = useState(false)

  const [whoami, setWhoami] = useState<WhoAmI | null>(null)
  const [bootstrapStatus, setBootstrapStatus] = useState<BootstrapStatus | null>(null)
  const [diagLoading, setDiagLoading] = useState(false)

  const [storedTenantId, setStoredTenantIdState] = useState(() => getTenantId())
  const [storedApiKeyMasked, setStoredApiKeyMasked] = useState(() => maskKey(getApiKeyValue()))
  const [storedAdminKeyMasked, setStoredAdminKeyMasked] = useState(() => maskKey(getAdminApiKeyValue()))
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [tenantsAuthRequired, setTenantsAuthRequired] = useState<boolean | null>(null)

  const hasTenant = useMemo(() => Boolean(storedTenantId), [storedTenantId])
  const hasApiKey = useMemo(() => Boolean(storedApiKeyMasked), [storedApiKeyMasked])
  const hasAdminKey = useMemo(() => Boolean(storedAdminKeyMasked), [storedAdminKeyMasked])

  const getAdminHeadersIfEnabled = () => {
    if (!showAdvanced || !hasAdminKey) return {}
    const adminKey = getAdminApiKeyValue()
    if (!adminKey) return {}
    return { [getAdminApiKeyHeaderName()]: adminKey }
  }

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
      const adminHeaders = getAdminHeadersIfEnabled()
      const [whoRes, bootRes] = await Promise.all([
        fetch('/api/auth/whoami', { headers: adminHeaders }),
        fetch('/api/auth/bootstrap-status', { headers: adminHeaders }),
      ])

      const whoBody = await whoRes.json().catch(() => ({}))
      const bootBody = await bootRes.json().catch(() => ({}))

      if (whoRes.ok) setWhoami(whoBody as WhoAmI)
      if (bootRes.ok) setBootstrapStatus(bootBody as BootstrapStatus)

      if (!whoRes.ok && !bootRes.ok) {
        showToast('error', '自檢失敗：請確認後端可連線，並已登入或提供管理者金鑰')
        return
      }
      showToast('success', '已更新自檢資訊')
    } catch {
      showToast('error', '自檢失敗（網路或伺服器未啟動）')
    } finally {
      setDiagLoading(false)
    }
  }

  const handleCreateTenant = async () => {
    const name = createTenantName.trim()
    const code = createTenantCode.trim()
    if (!name) {
      showToast('error', '請輸入場域名稱')
      return
    }
    if (!code) {
      showToast('error', '請輸入場域代碼')
      return
    }

    setCreateTenantLoading(true)
    try {
      const adminHeaders = getAdminHeadersIfEnabled()
      const res = await fetch('/api/tenants', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...adminHeaders },
        body: JSON.stringify({ name, code, is_default: true, is_active: true }),
      })
      const body = await res.json().catch(() => ({}))
      const detail = (body as any)?.detail
      if (!res.ok) {
        showToast('error', typeof detail === 'string' ? detail : `建立場域失敗 (HTTP ${res.status})`)
        setShowAdvanced(true)
        return
      }

      const id = String((body as any)?.id || '')
      if (id) {
        setTenantId(id)
        setStoredTenantIdState(id)
      }
      showToast('success', `已建立場域：${code}`)
      await refreshTenants()
    } catch {
      showToast('error', '建立場域失敗（網路或伺服器未啟動）')
    } finally {
      setCreateTenantLoading(false)
    }
  }

  const refreshTenants = async () => {
    setLoadingTenants(true)
    try {
      const adminHeaders = getAdminHeadersIfEnabled()
      const res = await fetch('/api/tenants', { headers: adminHeaders })
      if (!res.ok) {
        const body = await res.json().catch(() => ({}))
        const detail = (body as any)?.detail
        if (res.status === 401) {
          showToast('error', '後端已啟用權限驗證：請先登入（或由管理者完成初始化）')
          setTenantsAuthRequired(true)
          setShowAdvanced(true)
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

  const handleSaveAdminKey = () => {
    const trimmed = adminKeyDraft.trim()
    if (!trimmed) {
      showToast('error', '請輸入管理者金鑰')
      return
    }
    setAdminApiKeyValue(trimmed)
    setAdminKeyDraft('')
    setStoredAdminKeyMasked(maskKey(trimmed))
    showToast('success', '已保存管理者金鑰（localStorage）')
  }

  const handleClearAdminKey = () => {
    clearAdminApiKeyValue()
    setStoredAdminKeyMasked('')
    showToast('info', '已清除管理者金鑰（localStorage）')
  }

  const handleAutoInitTenant = async () => {
    try {
      const id = await ensureTenantIdWithOptions({ notify: true, reason: 'bootstrap', allowAdminBootstrap: true })
      if (!id) {
        showToast('error', '無法自動決定 tenant（可能存在多個 tenant 且沒有 default）')
        return
      }
      setStoredTenantIdState(id)
      showToast('success', `tenant 已就緒：${id}`)
    } catch {
      showToast('error', '初始化 tenant 失敗')
    }
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

  const handleCreateUser = async (role: 'user' | 'admin') => {
    const tenantCode = createUserTenantCode.trim()
    const username = createUsername.trim()
    const password = createPassword
    if (!username) {
      showToast('error', '請輸入要建立的帳號')
      return
    }
    if (!password || password.length < 8) {
      showToast('error', '請輸入至少 8 碼密碼')
      return
    }

    setCreateUserLoading(true)
    try {
      const adminHeaders = getAdminHeadersIfEnabled()
      const res = await fetch('/api/auth/users', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...adminHeaders },
        body: JSON.stringify({ tenant_code: tenantCode || undefined, username, password, role }),
      })
      const body = await res.json().catch(() => ({}))
      const detail = (body as any)?.detail
      if (!res.ok) {
        showToast('error', typeof detail === 'string' ? detail : `建立帳號失敗 (HTTP ${res.status})`)
        if (res.status === 403) setShowAdvanced(true)
        return
      }
      setCreateUsername('')
      setCreatePassword('')
      showToast('success', `已建立帳號：${String((body as any)?.username || username)}（role=${role}）`)
    } catch {
      showToast('error', '建立帳號失敗（網路或伺服器未啟動）')
    } finally {
      setCreateUserLoading(false)
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
              open={showAdvanced}
              onToggle={(e) => setShowAdvanced((e.currentTarget as HTMLDetailsElement).open)}
            >
              <summary className="register-summary">管理者（初始化用）</summary>

              <div className="register-form">
                <label className="register-label">
                  輸入管理者金鑰
                  <input
                    className="register-input"
                    type="password"
                    placeholder="請貼上金鑰"
                    value={adminKeyDraft}
                    onChange={(e) => setAdminKeyDraft(e.target.value)}
                  />
                </label>
                <div className="register-actions">
                  <button className="btn-primary" onClick={handleSaveAdminKey}>啟用管理者模式</button>
                  <button className="btn-secondary" onClick={handleClearAdminKey}>清除管理者金鑰</button>
                </div>
                {!hasAdminKey && (
                  <p className="register-hint muted" style={{ marginTop: '0.5rem' }}>
                    只有在資料庫尚未初始化、需要建立第一個場域時才需要。
                  </p>
                )}
              </div>

              {!hasAdminKey ? null : (
                <>
                  <div className="register-form">
                    <div className="register-row">
                      <label className="register-label" style={{ minWidth: 220, flex: 1 }}>
                        場域名稱
                        <input
                          className="register-input"
                          type="text"
                          placeholder="例如：侑特"
                          value={createTenantName}
                          onChange={(e) => setCreateTenantName(e.target.value)}
                        />
                      </label>
                      <label className="register-label" style={{ minWidth: 220, flex: 1 }}>
                        場域代碼（tenant_code）
                        <input
                          className="register-input"
                          type="text"
                          placeholder="例如：ut"
                          value={createTenantCode}
                          onChange={(e) => setCreateTenantCode(e.target.value)}
                        />
                      </label>
                    </div>
                    <div className="register-actions">
                      <button className="btn-primary" disabled={createTenantLoading} onClick={handleCreateTenant}>
                        {createTenantLoading ? '建立中…' : '建立場域（Tenant）'}
                      </button>
                      <button className="btn-secondary" disabled={loadingTenants} onClick={refreshTenants}>
                        {loadingTenants ? '讀取中…' : '刷新 tenants'}
                      </button>
                    </div>
                  </div>

                  <div className="register-form">
                    <div className="register-row">
                      <div className="register-kv">
                        <div className="register-k">目前 Tenant ID</div>
                        <div className="register-v">{storedTenantId ? <code>{storedTenantId}</code> : <span className="muted">（無）</span>}</div>
                      </div>
                      <div className="register-actions">
                        <button className="btn-secondary" onClick={handleAutoInitTenant}>一鍵建立/選擇場域</button>
                        <button className="btn-secondary" onClick={handleClearTenant}>清除 Tenant ID</button>
                      </div>
                    </div>

                    <div className="register-actions">
                      <button className="btn-secondary" disabled={diagLoading} onClick={handleFetchDiagnostics}>
                        {diagLoading ? '讀取中…' : '後端自檢'}
                      </button>
                      {tenantsAuthRequired === true && <span className="muted">（此環境需要先登入才能讀取 tenants）</span>}
                    </div>

                {whoami && (
                  <div className="register-row" style={{ marginTop: '0.5rem' }}>
                    <div className="register-kv" style={{ minWidth: 260 }}>
                      <div className="register-k">whoami</div>
                      <div className="register-v">
                        <code>
                          is_admin={String(whoami.is_admin)} / role={String(whoami.actor_role || '') || '-'} / tenant_id={String(whoami.tenant_id || '') || '-'}
                        </code>
                      </div>
                    </div>
                    <div className="register-kv" style={{ minWidth: 260 }}>
                      <div className="register-k">bootstrap-status</div>
                      <div className="register-v">
                        {bootstrapStatus ? (
                          <code>
                            auth_mode={bootstrapStatus.auth_mode} / admin_keys_configured={String(bootstrapStatus.admin_keys_configured)}
                          </code>
                        ) : (
                          <span className="muted">（尚未讀取）</span>
                        )}
                      </div>
                    </div>
                  </div>
                )}

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
              </div>

              <div className="register-form">
                <div className="register-row">
                  <label className="register-label" style={{ minWidth: 220, flex: 1 }}>
                    場域代碼（可留空）
                    <input
                      className="register-input"
                      type="text"
                      placeholder="例如：ut"
                      value={createUserTenantCode}
                      onChange={(e) => setCreateUserTenantCode(e.target.value)}
                    />
                  </label>
                  <label className="register-label" style={{ minWidth: 220, flex: 1 }}>
                    帳號
                    <input
                      className="register-input"
                      type="text"
                      placeholder="例如：admin"
                      value={createUsername}
                      onChange={(e) => setCreateUsername(e.target.value)}
                    />
                  </label>
                  <label className="register-label" style={{ minWidth: 220, flex: 1 }}>
                    密碼（至少 8 碼）
                    <input
                      className="register-input"
                      type="password"
                      placeholder="至少 8 碼"
                      value={createPassword}
                      onChange={(e) => setCreatePassword(e.target.value)}
                    />
                  </label>
                </div>

                <div className="register-actions">
                  <button className="btn-primary" disabled={createUserLoading} onClick={() => handleCreateUser('admin')}>
                    {createUserLoading ? '建立中…' : '建立 Tenant 管理者（admin）'}
                  </button>
                  <button className="btn-secondary" disabled={createUserLoading} onClick={() => handleCreateUser('user')}>
                    {createUserLoading ? '建立中…' : '建立一般使用者（user）'}
                  </button>
                </div>
              </div>

              <details className="register-details">
                <summary className="register-summary">目前瀏覽器保存狀態（除錯用）</summary>
                <ul className="register-list register-list-tight">
                  <li>
                    Tenant ID（{TENANT_STORAGE_KEY}）：{hasTenant ? <code>{storedTenantId}</code> : <span className="muted">（無）</span>}
                  </li>
                  <li>
                    權限憑證（{API_KEY_STORAGE_KEY}）：{storedApiKeyMasked ? <code>{storedApiKeyMasked}</code> : <span className="muted">（無）</span>}
                  </li>
                  <li>
                    管理者金鑰（{ADMIN_API_KEY_STORAGE_KEY}）：{storedAdminKeyMasked ? <code>{storedAdminKeyMasked}</code> : <span className="muted">（無）</span>}
                  </li>
                </ul>
              </details>
                </>
              )}
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
                  <button className="btn-secondary" onClick={handleAutoInitTenant}>一鍵建立/選擇場域</button>
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

            {(whoami?.is_admin || whoami?.actor_role === 'admin') && (
              <details className="register-details" open>
                <summary className="register-summary">帳號管理</summary>
                <div className="register-row">
                  <label className="register-label" style={{ minWidth: 220, flex: 1 }}>
                    場域代碼（可留空）
                    <input
                      className="register-input"
                      type="text"
                      placeholder="例如：ut"
                      value={createUserTenantCode}
                      onChange={(e) => setCreateUserTenantCode(e.target.value)}
                    />
                  </label>
                  <label className="register-label" style={{ minWidth: 220, flex: 1 }}>
                    帳號
                    <input
                      className="register-input"
                      type="text"
                      placeholder="例如：user"
                      value={createUsername}
                      onChange={(e) => setCreateUsername(e.target.value)}
                    />
                  </label>
                  <label className="register-label" style={{ minWidth: 220, flex: 1 }}>
                    密碼（至少 8 碼）
                    <input
                      className="register-input"
                      type="password"
                      placeholder="至少 8 碼"
                      value={createPassword}
                      onChange={(e) => setCreatePassword(e.target.value)}
                    />
                  </label>
                </div>

                <div className="register-actions">
                  <button className="btn-primary" disabled={createUserLoading} onClick={() => handleCreateUser('user')}>
                    {createUserLoading ? '建立中…' : '建立一般使用者（user）'}
                  </button>
                  <button className="btn-secondary" disabled={createUserLoading} onClick={() => handleCreateUser('admin')}>
                    {createUserLoading ? '建立中…' : '建立 Tenant 管理者（admin）'}
                  </button>
                </div>
              </details>
            )}
          </>
        )}

      </section>
    </div>
  )
}
