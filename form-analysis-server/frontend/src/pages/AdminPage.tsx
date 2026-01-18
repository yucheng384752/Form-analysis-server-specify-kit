import { useEffect, useMemo, useState } from 'react'
import { useToast } from '../components/common/ToastContext'
import {
  clearAdminApiKeyValue,
  getAdminApiKeyHeaderName,
  getAdminApiKeyValue,
  setAdminApiKeyValue,
} from '../services/adminAuth'
import { clearTenantId, ensureTenantIdWithOptions, getTenantId, setTenantId, TENANT_STORAGE_KEY } from '../services/tenant'
import './../styles/admin-page.css'

type TenantRow = {
  id: string
  name: string
  code: string
  is_active: boolean
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

type TenantUserRow = {
  id: string
  tenant_id: string
  tenant_code?: string | null
  username: string
  role: string
  is_active: boolean
  created_at?: string | null
  last_login_at?: string | null
}

function maskKey(raw: string) {
  const v = String(raw || '').trim()
  if (!v) return ''
  if (v.length <= 8) return `${v.slice(0, 2)}…${v.slice(-2)}`
  return `${v.slice(0, 4)}…${v.slice(-4)}`
}

export function AdminPage() {
  const { showToast } = useToast()

  const [adminKeyDraft, setAdminKeyDraft] = useState('')
  const [storedAdminKeyMasked, setStoredAdminKeyMasked] = useState(() => maskKey(getAdminApiKeyValue()))

  const hasAdminKey = useMemo(() => Boolean(storedAdminKeyMasked), [storedAdminKeyMasked])

  const [whoami, setWhoami] = useState<WhoAmI | null>(null)
  const [bootstrapStatus, setBootstrapStatus] = useState<BootstrapStatus | null>(null)
  const [diagLoading, setDiagLoading] = useState(false)

  const [storedTenantId, setStoredTenantIdState] = useState(() => getTenantId())

  const [tenants, setTenants] = useState<TenantRow[] | null>(null)
  const [loadingTenants, setLoadingTenants] = useState(false)
  const [showInactiveTenants, setShowInactiveTenants] = useState(false)

  const [createTenantName, setCreateTenantName] = useState('')
  const [createTenantCode, setCreateTenantCode] = useState('')
  const [createTenantDefault, setCreateTenantDefault] = useState(false)
  const [createTenantLoading, setCreateTenantLoading] = useState(false)

  const [selectedTenantCode, setSelectedTenantCode] = useState<string>('')
  const [users, setUsers] = useState<TenantUserRow[] | null>(null)
  const [loadingUsers, setLoadingUsers] = useState(false)

  const [createUsername, setCreateUsername] = useState('')
  const [createPassword, setCreatePassword] = useState('')
  const [createRole, setCreateRole] = useState<'user' | 'admin'>('user')
  const [creatingUser, setCreatingUser] = useState(false)

  const getAdminHeaders = () => {
    if (!hasAdminKey) return {}
    const k = getAdminApiKeyValue()
    if (!k) return {}
    return { [getAdminApiKeyHeaderName()]: k }
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

  const refreshDiagnostics = async () => {
    setDiagLoading(true)
    try {
      const adminHeaders = getAdminHeaders()
      const [whoRes, bootRes] = await Promise.all([
        fetch('/api/auth/whoami', { headers: adminHeaders }),
        fetch('/api/auth/bootstrap-status', { headers: adminHeaders }),
      ])

      const whoBody = await whoRes.json().catch(() => ({}))
      const bootBody = await bootRes.json().catch(() => ({}))

      if (whoRes.ok) setWhoami(whoBody as WhoAmI)
      if (bootRes.ok) setBootstrapStatus(bootBody as BootstrapStatus)

      if (!whoRes.ok && !bootRes.ok) {
        showToast('error', '自檢失敗：請確認後端可連線，且管理者金鑰正確')
        return
      }
      showToast('success', '已更新自檢資訊')
    } catch {
      showToast('error', '自檢失敗（網路或伺服器未啟動）')
    } finally {
      setDiagLoading(false)
    }
  }

  const handleBootstrapFirstTenant = async () => {
    try {
      const res = await fetch('/api/tenants', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...getAdminHeaders() },
        body: JSON.stringify({}),
      })
      const body = await res.json().catch(() => ({}))
      const detail = (body as any)?.detail
      if (!res.ok) {
        showToast('error', typeof detail === 'string' ? detail : `建立 Tenant 失敗 (HTTP ${res.status})`)
        return
      }

      const id = String((body as any)?.id || '')
      if (id) {
        setTenantId(id)
        setStoredTenantIdState(id)
      }
      showToast('success', `已建立 Tenant：${String((body as any)?.code || '') || '（已建立）'}`)
      await refreshTenants()
    } catch {
      showToast('error', '建立 Tenant 失敗（網路或伺服器未啟動）')
    }
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

  const handleClearTenant = () => {
    clearTenantId()
    setStoredTenantIdState('')
    showToast('info', '已清除 Tenant ID（localStorage）')
  }

  const refreshTenants = async () => {
    setLoadingTenants(true)
    try {
      const params = new URLSearchParams()
      if (showInactiveTenants) params.set('include_inactive', 'true')
      const suffix = params.toString() ? `?${params.toString()}` : ''
      const res = await fetch(`/api/tenants${suffix}`, { headers: getAdminHeaders() })
      const body = await res.json().catch(() => ({}))
      if (!res.ok) {
        showToast('error', typeof (body as any)?.detail === 'string' ? (body as any).detail : `取得 tenants 失敗 (HTTP ${res.status})`)
        setTenants(null)
        return
      }
      const rows = Array.isArray(body) ? (body as TenantRow[]) : []
      setTenants(rows)
      if (!selectedTenantCode && rows.length === 1) {
        setSelectedTenantCode(rows[0].code)
      }
    } catch {
      showToast('error', '取得 tenants 失敗（網路或伺服器未啟動）')
      setTenants(null)
    } finally {
      setLoadingTenants(false)
    }
  }

  const patchTenant = async (tenantId: string, patch: Partial<Pick<TenantRow, 'name' | 'is_active' | 'is_default'>>) => {
    try {
      const res = await fetch(`/api/tenants/${tenantId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json', ...getAdminHeaders() },
        body: JSON.stringify(patch),
      })
      const body = await res.json().catch(() => ({}))
      if (!res.ok) {
        showToast('error', typeof (body as any)?.detail === 'string' ? (body as any).detail : `更新 tenant 失敗 (HTTP ${res.status})`)
        return
      }
      showToast('success', '已更新 tenant')
      await refreshTenants()
    } catch {
      showToast('error', '更新 tenant 失敗（網路或伺服器未啟動）')
    }
  }

  const createTenant = async () => {
    const name = createTenantName.trim()
    const code = createTenantCode.trim()
    if (!name) {
      showToast('error', '請輸入 tenant name')
      return
    }
    if (!code) {
      showToast('error', '請輸入 tenant code')
      return
    }

    setCreateTenantLoading(true)
    try {
      const res = await fetch('/api/tenants/admin', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...getAdminHeaders() },
        body: JSON.stringify({ name, code, is_active: true, is_default: createTenantDefault }),
      })
      const body = await res.json().catch(() => ({}))
      if (!res.ok) {
        showToast('error', typeof (body as any)?.detail === 'string' ? (body as any).detail : `建立 tenant 失敗 (HTTP ${res.status})`)
        return
      }
      showToast('success', `已建立 tenant：${code}`)
      setCreateTenantName('')
      setCreateTenantCode('')
      setCreateTenantDefault(false)
      await refreshTenants()
    } catch {
      showToast('error', '建立 tenant 失敗（網路或伺服器未啟動）')
    } finally {
      setCreateTenantLoading(false)
    }
  }

  const deleteTenant = async (tenant: TenantRow) => {
    if (!confirm(`確定要刪除 tenant ${tenant.code}？\n（此操作為安全停用：is_active=false）`)) return
    try {
      const res = await fetch(`/api/tenants/${tenant.id}`, {
        method: 'DELETE',
        headers: getAdminHeaders(),
      })
      const body = await res.json().catch(() => ({}))
      if (!res.ok) {
        showToast('error', typeof (body as any)?.detail === 'string' ? (body as any).detail : `刪除 tenant 失敗 (HTTP ${res.status})`)
        return
      }
      showToast('success', `已刪除（停用）tenant：${tenant.code}`)
      await refreshTenants()
    } catch {
      showToast('error', '刪除 tenant 失敗（網路或伺服器未啟動）')
    }
  }

  const toggleTenantActive = async (tenant: TenantRow, nextActive: boolean) => {
    await patchTenant(tenant.id, { is_active: nextActive })
  }

  const refreshUsers = async () => {
    const code = selectedTenantCode.trim()
    if (!code) {
      showToast('error', '請先選擇 tenant')
      return
    }

    setLoadingUsers(true)
    try {
      const params = new URLSearchParams({ tenant_code: code, include_inactive: 'true' })
      const res = await fetch(`/api/auth/users?${params.toString()}`, { headers: getAdminHeaders() })
      const body = await res.json().catch(() => ({}))
      if (!res.ok) {
        showToast('error', typeof (body as any)?.detail === 'string' ? (body as any).detail : `取得使用者失敗 (HTTP ${res.status})`)
        setUsers(null)
        return
      }
      setUsers(Array.isArray(body) ? (body as TenantUserRow[]) : [])
    } catch {
      showToast('error', '取得使用者失敗（網路或伺服器未啟動）')
      setUsers(null)
    } finally {
      setLoadingUsers(false)
    }
  }

  const patchUser = async (userId: string, patch: Partial<Pick<TenantUserRow, 'username' | 'role' | 'is_active'>>) => {
    try {
      const res = await fetch(`/api/auth/users/${userId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json', ...getAdminHeaders() },
        body: JSON.stringify(patch),
      })
      const body = await res.json().catch(() => ({}))
      if (!res.ok) {
        showToast('error', typeof (body as any)?.detail === 'string' ? (body as any).detail : `更新使用者失敗 (HTTP ${res.status})`)
        return
      }
      showToast('success', '已更新使用者')
      await refreshUsers()
    } catch {
      showToast('error', '更新使用者失敗（網路或伺服器未啟動）')
    }
  }

  const deleteUser = async (user: TenantUserRow) => {
    if (!confirm(`確定要刪除使用者 ${user.username}？\n（此操作為安全停用：is_active=false）`)) return
    try {
      const res = await fetch(`/api/auth/users/${user.id}`, {
        method: 'DELETE',
        headers: getAdminHeaders(),
      })
      const body = await res.json().catch(() => ({}))
      if (!res.ok) {
        showToast('error', typeof (body as any)?.detail === 'string' ? (body as any).detail : `刪除使用者失敗 (HTTP ${res.status})`)
        return
      }
      showToast('success', '已刪除（停用）使用者')
      await refreshUsers()
    } catch {
      showToast('error', '刪除使用者失敗（網路或伺服器未啟動）')
    }
  }

  const createUser = async () => {
    const code = selectedTenantCode.trim()
    const username = createUsername.trim()
    const password = createPassword

    if (!code) {
      showToast('error', '請先選擇 tenant')
      return
    }
    if (!username) {
      showToast('error', '請輸入 username')
      return
    }
    if (!password || password.length < 8) {
      showToast('error', '請輸入至少 8 碼密碼（建立使用者需要）')
      return
    }

    setCreatingUser(true)
    try {
      const res = await fetch('/api/auth/users', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...getAdminHeaders() },
        body: JSON.stringify({ tenant_code: code, username, password, role: createRole }),
      })
      const body = await res.json().catch(() => ({}))
      if (!res.ok) {
        showToast('error', typeof (body as any)?.detail === 'string' ? (body as any).detail : `建立使用者失敗 (HTTP ${res.status})`)
        return
      }
      showToast('success', `已建立使用者：${username}`)
      setCreateUsername('')
      setCreatePassword('')
      setCreateRole('user')
      await refreshUsers()
    } catch {
      showToast('error', '建立使用者失敗（網路或伺服器未啟動）')
    } finally {
      setCreatingUser(false)
    }
  }

  useEffect(() => {
    // Best-effort initial load.
    refreshTenants()
  }, [])

  return (
    <div className="admin-page">
      <section className="register-card">
        <h2 className="register-title">管理者模式</h2>
        <p className="register-hint">此頁面只在你明確提供管理者金鑰時，才會在呼叫端點時帶入 `X-Admin-API-Key`。</p>

        <div className="register-row">
          <div className="register-kv">
            <div className="register-k">目前管理者金鑰</div>
            <div className="register-v">{storedAdminKeyMasked || '（未設定）'}</div>
          </div>
        </div>

        <div className="register-form">
          <label className="register-label">
            管理者金鑰
            <input
              className="register-input"
              value={adminKeyDraft}
              onChange={(e) => setAdminKeyDraft(e.target.value)}
              placeholder="輸入 X-Admin-API-Key"
            />
          </label>

          <div className="register-actions">
            <button className="btn btn-primary" onClick={handleSaveAdminKey}>
              保存
            </button>
            <button className="btn" onClick={handleClearAdminKey}>
              清除
            </button>
            <button className="btn" onClick={refreshDiagnostics} disabled={diagLoading}>
              {diagLoading ? '檢查中…' : 'WhoAmI'}
            </button>
          </div>

          {whoami && (
            <div className="admin-kv-block">
              <div className="admin-kv">
                <span className="admin-k">is_admin</span>
                <span className="admin-v">{String(whoami.is_admin)}</span>
              </div>
              <div className="admin-kv">
                <span className="admin-k">actor_role</span>
                <span className="admin-v">{whoami.actor_role || '—'}</span>
              </div>
              <div className="admin-kv">
                <span className="admin-k">tenant_id</span>
                <span className="admin-v">{whoami.tenant_id || '—'}</span>
              </div>
            </div>
          )}

          {bootstrapStatus && (
            <div className="admin-kv-block">
              <div className="admin-kv">
                <span className="admin-k">auth_mode</span>
                <span className="admin-v">{bootstrapStatus.auth_mode}</span>
              </div>
              <div className="admin-kv">
                <span className="admin-k">admin_header</span>
                <span className="admin-v">{bootstrapStatus.admin_api_key_header}</span>
              </div>
              <div className="admin-kv">
                <span className="admin-k">admin_keys_configured</span>
                <span className="admin-v">{String(bootstrapStatus.admin_keys_configured)}</span>
              </div>
            </div>
          )}

          <details className="register-details" open>
            <summary className="register-summary">初始化（第一次／空資料庫）</summary>
            <p className="register-hint">
              這裡提供建立/選擇 Tenant 的工具（會寫入 localStorage：{TENANT_STORAGE_KEY}）。
            </p>

            <div className="register-row">
              <div className="register-kv">
                <div className="register-k">目前 Tenant ID</div>
                <div className="register-v">{storedTenantId ? <code>{storedTenantId}</code> : <span className="muted">（未設定）</span>}</div>
              </div>
              <div className="register-actions">
                <button className="btn" onClick={handleAutoInitTenant} disabled={!hasAdminKey} title={!hasAdminKey ? '請先設定管理者金鑰' : ''}>
                  一鍵建立/選擇場域
                </button>
                <button className="btn" onClick={handleClearTenant}>清除 Tenant ID</button>
              </div>
            </div>

            <div className="register-actions">
              <button className="btn btn-primary" onClick={handleBootstrapFirstTenant} disabled={!hasAdminKey} title={!hasAdminKey ? '請先設定管理者金鑰' : ''}>
                建立第一個 Tenant（bootstrap）
              </button>
            </div>
          </details>
        </div>
      </section>

      <section className="register-card">
        <div className="admin-header-row">
          <div>
            <h2 className="register-title">Tenant 管理</h2>
            <p className="register-hint">需要管理者金鑰才能完整 CRUD（新增/編輯/停用/設預設）。</p>
          </div>
          <div className="admin-header-actions">
            <label className="register-hint" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <input
                type="checkbox"
                checked={showInactiveTenants}
                onChange={(e) => setShowInactiveTenants(e.target.checked)}
              />
              顯示停用 tenants
            </label>
            <button className="btn" onClick={refreshTenants} disabled={loadingTenants}>
              {loadingTenants ? '更新中…' : '重新整理'}
            </button>
          </div>
        </div>

        <details className="register-details">
          <summary className="register-summary">新增 Tenant</summary>
          <div className="admin-form-grid">
            <label className="register-label">
              name
              <input className="register-input" value={createTenantName} onChange={(e) => setCreateTenantName(e.target.value)} />
            </label>
            <label className="register-label">
              code
              <input className="register-input" value={createTenantCode} onChange={(e) => setCreateTenantCode(e.target.value)} />
            </label>
            <label className="register-label">
              default
              <select
                className="register-input"
                value={createTenantDefault ? 'yes' : 'no'}
                onChange={(e) => setCreateTenantDefault(e.target.value === 'yes')}
              >
                <option value="no">no</option>
                <option value="yes">yes</option>
              </select>
            </label>
          </div>
          <div className="register-actions">
            <button className="btn btn-primary" onClick={createTenant} disabled={!hasAdminKey || createTenantLoading}>
              {createTenantLoading ? '建立中…' : '建立 Tenant'}
            </button>
          </div>
        </details>

        <div className="admin-table-wrap">
          <table className="admin-table">
            <thead>
              <tr>
                <th>id</th>
                <th>code</th>
                <th>name</th>
                <th>default</th>
                <th>active</th>
                <th>actions</th>
              </tr>
            </thead>
            <tbody>
              {(tenants || []).map((t) => (
                <tr key={t.id}>
                  <td className="admin-mono">{t.id}</td>
                  <td>{t.code}</td>
                  <td>
                    <input
                      className="admin-inline-input"
                      defaultValue={t.name}
                      onBlur={(e) => {
                        const v = e.target.value.trim()
                        if (v && v !== t.name) patchTenant(t.id, { name: v })
                      }}
                    />
                  </td>
                  <td>
                    <span className={t.is_default ? 'pill pill-ok' : 'pill pill-off'}>{t.is_default ? 'default' : '—'}</span>
                  </td>
                  <td>
                    <span className={t.is_active ? 'pill pill-ok' : 'pill pill-off'}>{t.is_active ? '啟用' : '停用'}</span>
                  </td>
                  <td>
                    <button
                      className="btn btn-small"
                      onClick={() => toggleTenantActive(t, !t.is_active)}
                      disabled={!hasAdminKey}
                      title={!hasAdminKey ? '請先設定管理者金鑰' : ''}
                    >
                      {t.is_active ? '停用' : '啟用'}
                    </button>
                    <button
                      className="btn btn-small"
                      onClick={() => patchTenant(t.id, { is_default: true })}
                      disabled={!hasAdminKey}
                      title={!hasAdminKey ? '請先設定管理者金鑰' : ''}
                      style={{ marginLeft: 8 }}
                    >
                      設為預設
                    </button>
                    <button
                      className="btn btn-small"
                      onClick={() => deleteTenant(t)}
                      disabled={!hasAdminKey}
                      title={!hasAdminKey ? '請先設定管理者金鑰' : ''}
                      style={{ marginLeft: 8 }}
                    >
                      刪除
                    </button>
                  </td>
                </tr>
              ))}
              {!tenants?.length && (
                <tr>
                  <td colSpan={6} className="admin-empty">
                    {tenants === null ? '尚未載入' : '沒有 tenants'}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>

      <section className="register-card">
        <div className="admin-header-row">
          <div>
            <h2 className="register-title">Tenant 使用者管理</h2>
            <p className="register-hint">可修改 username / role / 啟用停用；密碼修改先不做（TODO）。</p>
          </div>
          <div className="admin-header-actions">
            <select
              className="register-input admin-select"
              value={selectedTenantCode}
              onChange={(e) => setSelectedTenantCode(e.target.value)}
            >
              <option value="">選擇 tenant…</option>
              {(tenants || []).map((t) => (
                <option key={t.id} value={t.code}>
                  {t.code} ({t.name})
                </option>
              ))}
            </select>
            <button className="btn" onClick={refreshUsers} disabled={loadingUsers}>
              {loadingUsers ? '更新中…' : '載入使用者'}
            </button>
          </div>
        </div>

        <details className="register-details">
          <summary className="register-summary">新增使用者（需密碼；密碼修改仍為 TODO）</summary>
          <div className="admin-form-grid">
            <label className="register-label">
              username
              <input className="register-input" value={createUsername} onChange={(e) => setCreateUsername(e.target.value)} />
            </label>
            <label className="register-label">
              password
              <input
                className="register-input"
                type="password"
                value={createPassword}
                onChange={(e) => setCreatePassword(e.target.value)}
                placeholder="至少 8 碼"
              />
            </label>
            <label className="register-label">
              role
              <select className="register-input" value={createRole} onChange={(e) => setCreateRole(e.target.value as any)}>
                <option value="user">user</option>
                <option value="admin">admin</option>
              </select>
            </label>
          </div>
          <div className="register-actions">
            <button className="btn btn-primary" onClick={createUser} disabled={creatingUser}>
              {creatingUser ? '建立中…' : '建立使用者'}
            </button>
          </div>
        </details>

        <div className="admin-table-wrap">
          <table className="admin-table">
            <thead>
              <tr>
                <th>username</th>
                <th>role</th>
                <th>active</th>
                <th>last_login</th>
                <th>actions</th>
              </tr>
            </thead>
            <tbody>
              {(users || []).map((u) => (
                <tr key={u.id} className={!u.is_active ? 'is-inactive' : ''}>
                  <td>
                    <input
                      className="admin-inline-input"
                      defaultValue={u.username}
                      onBlur={(e) => {
                        const v = e.target.value.trim()
                        if (v && v !== u.username) patchUser(u.id, { username: v })
                      }}
                    />
                  </td>
                  <td>
                    <select
                      className="admin-inline-input"
                      defaultValue={u.role}
                      onChange={(e) => {
                        const v = e.target.value
                        if (v !== u.role) patchUser(u.id, { role: v })
                      }}
                    >
                      <option value="user">user</option>
                      <option value="admin">admin</option>
                    </select>
                  </td>
                  <td>
                    <input
                      type="checkbox"
                      defaultChecked={u.is_active}
                      onChange={(e) => patchUser(u.id, { is_active: e.target.checked })}
                    />
                  </td>
                  <td className="admin-mono">{u.last_login_at || '—'}</td>
                  <td>
                    <button className="btn btn-small" onClick={() => patchUser(u.id, { is_active: !u.is_active })}>
                      {u.is_active ? '停用' : '啟用'}
                    </button>
                    <button className="btn btn-small" onClick={() => deleteUser(u)} style={{ marginLeft: 8 }}>
                      刪除
                    </button>
                  </td>
                </tr>
              ))}
              {!users?.length && (
                <tr>
                  <td colSpan={5} className="admin-empty">
                    {users === null ? '尚未載入' : '沒有使用者'}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  )
}
