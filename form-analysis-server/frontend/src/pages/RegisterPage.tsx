// src/pages/RegisterPage.tsx
import { useMemo, useState } from 'react'
import { useToast } from '../components/common/ToastContext'
import { clearApiKeyValue, getApiKeyHeaderName, getApiKeyValue, setApiKeyValue, API_KEY_STORAGE_KEY } from '../services/auth'
import { clearAdminApiKeyValue, getAdminApiKeyHeaderName, getAdminApiKeyValue, setAdminApiKeyValue, ADMIN_API_KEY_STORAGE_KEY } from '../services/adminAuth'
import { clearTenantId, ensureTenantIdWithOptions, getTenantId, setTenantId, TENANT_STORAGE_KEY } from '../services/tenant'
import './../styles/register-page.css'

type TenantRow = {
  id: string
  name?: string
  code?: string
  is_active?: boolean
  is_default?: boolean
}

export function RegisterPage() {
  const { showToast } = useToast()

  const maskKey = (raw: string) => {
    const v = String(raw || '').trim()
    if (!v) return ''
    if (v.length <= 8) return `${v.slice(0, 2)}…${v.slice(-2)}`
    return `${v.slice(0, 4)}…${v.slice(-4)}`
  }

  const [apiKeyDraft, setApiKeyDraft] = useState('')
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
  const [createRole, setCreateRole] = useState('user')
  const [createUserLoading, setCreateUserLoading] = useState(false)

  const [storedTenantId, setStoredTenantIdState] = useState(() => getTenantId())
  const [storedApiKeyMasked, setStoredApiKeyMasked] = useState(() => maskKey(getApiKeyValue()))
  const [storedAdminKeyMasked, setStoredAdminKeyMasked] = useState(() => maskKey(getAdminApiKeyValue()))
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [tenantsAuthRequired, setTenantsAuthRequired] = useState<boolean | null>(null)

  const hasTenant = useMemo(() => Boolean(storedTenantId), [storedTenantId])

  const apiKeyHeaderName = getApiKeyHeaderName()
  const adminKeyHeaderName = getAdminApiKeyHeaderName()

  const refreshTenants = async () => {
    setLoadingTenants(true)
    try {
      const res = await fetch('/api/tenants')
      if (!res.ok) {
        const body = await res.json().catch(() => ({}))
        const detail = (body as any)?.detail
        if (res.status === 401) {
          showToast('error', '後端已啟用 API key 驗證：請先設定 API key（或暫時關閉 AUTH_MODE 進行 bootstrap）')
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

  const handleSaveApiKey = () => {
    const trimmed = apiKeyDraft.trim()
    if (!trimmed) {
      showToast('error', '請輸入 API key')
      return
    }
    setApiKeyValue(trimmed)
    setApiKeyDraft('')
    setStoredApiKeyMasked(maskKey(trimmed))
    showToast('success', '已保存 API key（localStorage）')
  }

  const handleClearApiKey = () => {
    clearApiKeyValue()
    setStoredApiKeyMasked('')
    showToast('info', '已清除 API key（localStorage）')
  }

  const handleSaveAdminKey = () => {
    const trimmed = adminKeyDraft.trim()
    if (!trimmed) {
      showToast('error', '請輸入 Admin API key')
      return
    }
    setAdminApiKeyValue(trimmed)
    setAdminKeyDraft('')
    setStoredAdminKeyMasked(maskKey(trimmed))
    showToast('success', '已保存 Admin API key（localStorage）')
  }

  const handleClearAdminKey = () => {
    clearAdminApiKeyValue()
    setStoredAdminKeyMasked('')
    showToast('info', '已清除 Admin API key（localStorage）')
  }

  const handleAutoInitTenant = async () => {
    try {
      const id = await ensureTenantIdWithOptions({ notify: true, reason: 'bootstrap' })
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
      showToast('success', '登入成功：已自動保存場域與權限（API key）')
    } catch {
      showToast('error', '登入失敗（網路或伺服器未啟動）')
    } finally {
      setLoginLoading(false)
    }
  }

  const handleCreateUser = async () => {
    const tenantCode = createUserTenantCode.trim()
    const username = createUsername.trim()
    const password = createPassword
    const role = createRole.trim() || 'user'
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
      const res = await fetch('/api/auth/users', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
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
      showToast('success', `已建立帳號：${String((body as any)?.username || username)}`)
    } catch {
      showToast('error', '建立帳號失敗（網路或伺服器未啟動）')
    } finally {
      setCreateUserLoading(false)
    }
  }

  return (
    <div className="register-page">
      <section className="register-card">
        <h2 className="register-title">快速開始（建立/選擇場域）</h2>
        <p className="register-hint">你只需要先完成「場域（Tenant）」設定，就能開始使用系統。API key / 管理者 key 是可選的進階設定。</p>

        <ol className="register-list register-list-tight">
          <li>
            按「一鍵建立/選擇場域」
            <span className="muted">（空資料庫會自動建立 UT；只有一個場域會自動選；多個場域則請從列表挑一個）</span>
          </li>
          <li>
            若你在任何 API 操作看到 <code>401</code>，再回來設定 API key
            <span className="muted">（這代表後端啟用 AUTH_MODE=api_key）</span>
          </li>
        </ol>
      </section>

      <section className="register-card">
        <h3 className="register-subtitle">登入（帳號 / 密碼）</h3>
        <p className="register-hint muted">符合傳統使用者直覺：輸入帳號密碼 → 取得對應權限（系統會自動保存 API key）。</p>

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
                placeholder="例如：admin / user"
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
              {loginLoading ? '登入中…' : '登入並取得權限'}
            </button>
          </div>
          <p className="register-hint muted">
            備註：若同資料庫有多個場域，請填「場域代碼」。若只有一個場域可留空。
          </p>
        </div>
      </section>

      <section className="register-card">
        <h3 className="register-subtitle">場域（Tenant）初始化 / 選擇</h3>

        <div className="register-row">
          <div className="register-kv">
            <div className="register-k">目前已選擇的場域（Tenant ID）</div>
            <div className="register-v">{storedTenantId ? <code>{storedTenantId}</code> : <span className="muted">（無）</span>}</div>
          </div>
          <div className="register-actions">
            <button className="btn-primary" onClick={handleAutoInitTenant}>一鍵建立/選擇場域</button>
            <button className="btn-secondary" onClick={handleClearTenant}>清除 Tenant ID</button>
          </div>
        </div>

        <p className="register-hint muted" style={{ marginTop: '0.5rem' }}>
          說明：同一個資料庫內可以存在多個場域（tenants）。系統會用 <code>X-Tenant-Id</code> 把資料查詢/寫入限制在該場域。
        </p>

        <div className="register-actions">
          <button className="btn-secondary" disabled={loadingTenants} onClick={refreshTenants}>
            {loadingTenants ? '讀取中…' : '刷新 tenants 列表'}
          </button>
          {tenantsAuthRequired === true && (
            <span className="muted">（此環境需要 key 才能讀取 tenants）</span>
          )}
        </div>

        {tenants && (
          <div className="register-tenants">
            <div className="register-tenants-title">tenants</div>
            {tenants.length === 0 ? (
              <div className="muted">（目前為空，可按「自動初始化 Tenant」）</div>
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
      </section>

      <section className="register-card">
        <div className="register-row" style={{ alignItems: 'center' }}>
          <h3 className="register-subtitle" style={{ marginBottom: 0 }}>進階設定（可選）</h3>
          <button className="btn-secondary" onClick={() => setShowAdvanced((v) => !v)}>
            {showAdvanced ? '收合進階設定' : '展開進階設定'}
          </button>
        </div>

        {!showAdvanced ? (
          <p className="register-hint muted" style={{ marginTop: '0.5rem' }}>
            大多數情況只要設定場域就夠了。當你遇到 401、或要建立/管理 tenants，才需要在這裡貼 key。
          </p>
        ) : (
          <>
            <details className="register-details" open>
              <summary className="register-summary">建立帳號（管理者）</summary>
              <p className="register-hint muted" style={{ marginTop: '0.5rem' }}>
                需要先保存 Admin API key（用於建立使用者帳號）。建立完後，一般使用者就能用帳密登入。
              </p>

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
                <label className="register-label" style={{ minWidth: 220, flex: 1 }}>
                  角色
                  <input
                    className="register-input"
                    type="text"
                    placeholder="user"
                    value={createRole}
                    onChange={(e) => setCreateRole(e.target.value)}
                  />
                </label>
              </div>

              <div className="register-actions">
                <button className="btn-primary" disabled={createUserLoading} onClick={handleCreateUser}>
                  {createUserLoading ? '建立中…' : '建立帳號'}
                </button>
              </div>
            </details>

            <details className="register-details" open>
              <summary className="register-summary">API key（一般使用者）</summary>

              <div className="register-row">
                <div className="register-kv">
                  <div className="register-k">Header 名稱</div>
                  <div className="register-v"><code>{apiKeyHeaderName}</code></div>
                </div>
                <div className="register-kv">
                  <div className="register-k">目前已保存</div>
                  <div className="register-v">{storedApiKeyMasked ? <code>{storedApiKeyMasked}</code> : <span className="muted">（無）</span>}</div>
                </div>
              </div>

              <div className="register-form">
                <label className="register-label">
                  貼上 raw API key
                  <input
                    className="register-input"
                    type="password"
                    placeholder="例如：abc123..."
                    value={apiKeyDraft}
                    onChange={(e) => setApiKeyDraft(e.target.value)}
                  />
                </label>
                <div className="register-actions">
                  <button className="btn-primary" onClick={handleSaveApiKey}>保存 API key</button>
                  <button className="btn-secondary" onClick={handleClearApiKey}>清除 API key</button>
                </div>
                <p className="register-hint muted">
                  只有在後端啟用 <code>AUTH_MODE=api_key</code> 時才需要。你看到 401 時再來貼即可。
                </p>
              </div>
            </details>

            <details className="register-details">
              <summary className="register-summary">Admin API key（管理者：建立/管理 tenants）</summary>

              <div className="register-row">
                <div className="register-kv">
                  <div className="register-k">Header 名稱</div>
                  <div className="register-v"><code>{adminKeyHeaderName}</code></div>
                </div>
                <div className="register-kv">
                  <div className="register-k">目前已保存</div>
                  <div className="register-v">{storedAdminKeyMasked ? <code>{storedAdminKeyMasked}</code> : <span className="muted">（無）</span>}</div>
                </div>
              </div>

              <div className="register-form">
                <label className="register-label">
                  貼上 raw Admin API key
                  <input
                    className="register-input"
                    type="password"
                    placeholder="例如：admin-abc123..."
                    value={adminKeyDraft}
                    onChange={(e) => setAdminKeyDraft(e.target.value)}
                  />
                </label>
                <div className="register-actions">
                  <button className="btn-primary" onClick={handleSaveAdminKey}>保存 Admin key</button>
                  <button className="btn-secondary" onClick={handleClearAdminKey}>清除 Admin key</button>
                </div>
                <p className="register-hint muted">
                  備註：首次要建立 tenant（場域）且後端已啟用 <code>AUTH_MODE=api_key</code> 時，通常需要管理者先提供 admin key。
                </p>
              </div>
            </details>

            <details className="register-details">
              <summary className="register-summary">目前瀏覽器保存狀態（除錯用）</summary>
              <ul className="register-list register-list-tight">
                <li>
                  Tenant ID（{TENANT_STORAGE_KEY}）：{hasTenant ? <code>{storedTenantId}</code> : <span className="muted">（無）</span>}
                </li>
                <li>
                  API key（{API_KEY_STORAGE_KEY}）：{storedApiKeyMasked ? <code>{storedApiKeyMasked}</code> : <span className="muted">（無）</span>}
                </li>
                <li>
                  Admin key（{ADMIN_API_KEY_STORAGE_KEY}）：{storedAdminKeyMasked ? <code>{storedAdminKeyMasked}</code> : <span className="muted">（無）</span>}
                </li>
              </ul>
            </details>
          </>
        )}
      </section>

      <section className="register-card">
        <h3 className="register-subtitle">快速檢查（建議）</h3>
        <ol className="register-list">
          <li>後端文件：<a href="/docs" target="_blank" rel="noreferrer">/docs</a></li>
          <li>健康檢查：<a href="/healthz" target="_blank" rel="noreferrer">/healthz</a></li>
          <li>Tenant 列表：<a href="/api/tenants" target="_blank" rel="noreferrer">/api/tenants</a>（若啟用 auth 需要 key）</li>
        </ol>
      </section>
    </div>
  )
}
