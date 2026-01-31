import { useEffect, useMemo, useState, type KeyboardEventHandler } from 'react'
import { useToast } from '../components/common/ToastContext'
import {
  clearAdminApiKeyValue,
  clearAdminUnlockedInSession,
  getAdminApiKeyHeaderName,
  getAdminApiKeyValue,
  isAdminUnlockedInSession,
  setAdminUnlockedInSession,
  setAdminApiKeyValue,
} from '../services/adminAuth'
import { setApiKeyValue } from '../services/auth'
import { clearTenantId, ensureTenantIdWithOptions, getTenantId, setTenantId, TENANT_STORAGE_KEY } from '../services/tenant'
import { getTenantLabelById, writeTenantMap } from '../services/tenantMap'
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

export function AdminPage(props: { onAdminUnlocked?: () => void; onAdminLocked?: () => void } = {}) {
  const { showToast } = useToast()

  const [adminKeyDraft, setAdminKeyDraft] = useState('')
  const [storedAdminKeyMasked, setStoredAdminKeyMasked] = useState(() => maskKey(getAdminApiKeyValue()))
  const [adminKeySaving, setAdminKeySaving] = useState(false)

  const [adminUnlocked, setAdminUnlocked] = useState(() => isAdminUnlockedInSession())

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

  const hasAnyActiveTenant = useMemo(() => {
    return (tenants || []).some((t) => Boolean(t?.is_active))
  }, [tenants])

  const storedTenantLabel = useMemo(() => {
    if (!storedTenantId) return ''
    const fromList = tenants?.find((t) => t?.id === storedTenantId)
    if (fromList?.code) return fromList.code
    return getTenantLabelById(storedTenantId)
  }, [storedTenantId, tenants])

  const whoamiTenantLabel = useMemo(() => {
    const id = String(whoami?.tenant_id || '').trim()
    if (!id) return ''
    const fromList = tenants?.find((t) => t?.id === id)
    if (fromList?.code) return fromList.code
    return getTenantLabelById(id)
  }, [whoami?.tenant_id, tenants])

  const handleAdminKeyDraftKeyDown: KeyboardEventHandler<HTMLInputElement> = (e) => {
    if (e.key !== 'Enter') return
    e.preventDefault()
    if (adminKeySaving) return
    void handleSaveAdminKey()
  }

  const [selectedTenantCode, setSelectedTenantCode] = useState<string>('')
  const [users, setUsers] = useState<TenantUserRow[] | null>(null)
  const [loadingUsers, setLoadingUsers] = useState(false)

  const [moveUserTargets, setMoveUserTargets] = useState<Record<string, string>>({})
  const [movingUserId, setMovingUserId] = useState<string | null>(null)

  const [createUsername, setCreateUsername] = useState('')
  const [createPassword, setCreatePassword] = useState('')
  const [createRole, setCreateRole] = useState<'user' | 'manager' | 'admin'>('user')
  const [creatingUser, setCreatingUser] = useState(false)

  const getAdminHeaders = () => {
    if (!hasAdminKey || !adminUnlocked) return {}
    const k = getAdminApiKeyValue()
    if (!k) return {}
    return { [getAdminApiKeyHeaderName()]: k }
  }

  const handleSaveAdminKey = async () => {
    const trimmed = adminKeyDraft.trim()
    if (!trimmed) {
      showToast('error', '請輸入管理者金鑰')
      return
    }

    setAdminKeySaving(true)
    try {
      // Verify by calling bootstrap-status (admin-only).
      const res = await fetch('/api/auth/bootstrap-status', {
        headers: {
          [getAdminApiKeyHeaderName()]: trimmed,
        },
      })

      if (!res.ok) {
        const body = await res.json().catch(() => ({}))
        const detail = (body as any)?.detail
        showToast('error', typeof detail === 'string' ? detail : '管理者金鑰無效')
        clearAdminApiKeyValue()
        clearAdminUnlockedInSession()
        props?.onAdminLocked?.()
        setStoredAdminKeyMasked('')
        return
      }

      setAdminApiKeyValue(trimmed)
      setAdminUnlockedInSession(true)
      setAdminUnlocked(true)
      props?.onAdminUnlocked?.()
      setAdminKeyDraft('')
      setStoredAdminKeyMasked(maskKey(trimmed))
      showToast('success', '管理者金鑰驗證成功：已解鎖管理者模式')
      void refreshDiagnostics()
    } catch {
      showToast('error', '管理者金鑰驗證失敗（網路或伺服器未啟動）')
    } finally {
      setAdminKeySaving(false)
    }
  }

  const handleClearAdminKey = () => {
    clearAdminApiKeyValue()
    clearAdminUnlockedInSession()
    setAdminUnlocked(false)
    setStoredAdminKeyMasked('')
    props?.onAdminLocked?.()
    showToast('info', '已清除管理者金鑰（localStorage）')
  }

  const handleDisableAdminMode = () => {
    // Disable only for this browser tab session. Keep the stored key.
    clearAdminUnlockedInSession()
    setAdminUnlocked(false)
    props?.onAdminLocked?.()
    showToast('info', '已停用管理者模式（本次 session）')
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
      showToast('success', `已建立區域：${String((body as any)?.code || '') || '（已建立）'}`)
      await refreshTenants()
    } catch {
      showToast('error', '建立區域失敗（網路或伺服器未啟動）')
    }
  }

  const handleAutoInitTenant = async () => {
    try {
      const id = await ensureTenantIdWithOptions({ notify: true, reason: 'bootstrap', allowAdminBootstrap: true })
      if (!id) {
        showToast('error', '無法自動決定區域（可能存在多個區域且沒有預設）')
        return
      }
      setStoredTenantIdState(id)
      showToast('success', `區域已就緒：${getTenantLabelById(id) || '（未知）'}`)
    } catch {
      showToast('error', '初始化 tenant 失敗')
    }
  }

  const handleClearTenant = () => {
    clearTenantId()
    setStoredTenantIdState('')
    showToast('info', '已清除區域（localStorage）')
  }

  const handleSetCurrentTenant = async (tenant: TenantRow) => {
    setTenantId(tenant.id)
    setStoredTenantIdState(tenant.id)

    if (!hasAdminKey) {
      showToast('success', `已切換目前區域：${tenant.code} (${tenant.name})`)
      return
    }

    try {
      const res = await fetch('/api/auth/admin/tenant-api-keys', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...getAdminHeaders() },
        body: JSON.stringify({ tenant_id: tenant.id }),
      })
      const body = await res.json().catch(() => ({}))
      if (!res.ok) {
        showToast(
          'error',
          typeof (body as any)?.detail === 'string' ? (body as any).detail : `取得 API key 失敗 (HTTP ${res.status})`,
        )
        return
      }

      const apiKey = String((body as any)?.api_key || '').trim()
      if (apiKey) setApiKeyValue(apiKey)

      showToast('success', `已切換區域：${tenant.code} (${tenant.name})，並取得可用 API key`)
    } catch {
      showToast('error', '切換區域失敗（網路或伺服器未啟動）')
    }
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
      writeTenantMap(rows)
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
      showToast('error', '請輸入區域名稱')
      return
    }
    if (!code) {
      showToast('error', '請輸入區域代碼')
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
        showToast('error', typeof (body as any)?.detail === 'string' ? (body as any).detail : `建立區域失敗 (HTTP ${res.status})`)
        return
      }
      showToast('success', `已建立區域：${code}`)
      setCreateTenantName('')
      setCreateTenantCode('')
      setCreateTenantDefault(false)
      await refreshTenants()
    } catch {
      showToast('error', '建立區域失敗（網路或伺服器未啟動）')
    } finally {
      setCreateTenantLoading(false)
    }
  }

  const deleteTenant = async (tenant: TenantRow) => {
    if (!confirm(`確定要刪除區域 ${tenant.code}？\n（此操作為安全停用：is_active=false）`)) return
    try {
      const res = await fetch(`/api/tenants/${tenant.id}`, {
        method: 'DELETE',
        headers: getAdminHeaders(),
      })
      const body = await res.json().catch(() => ({}))
      if (!res.ok) {
        showToast('error', typeof (body as any)?.detail === 'string' ? (body as any).detail : `刪除區域失敗 (HTTP ${res.status})`)
        return
      }
      showToast('success', `已刪除（停用）區域：${tenant.code}`)
      await refreshTenants()
    } catch {
      showToast('error', '刪除區域失敗（網路或伺服器未啟動）')
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

  const moveUserToTenant = async (user: TenantUserRow) => {
    const targetCode = (moveUserTargets[user.id] || '').trim()
    if (!targetCode) {
      showToast('error', '請先選擇要綁定的 tenant')
      return
    }
    if (targetCode === (user.tenant_code || '')) {
      showToast('info', '使用者已在此 tenant，不需修改')
      return
    }

    if (!confirm(`確定要將使用者 ${user.username} 改綁定到 tenant ${targetCode}？\n\n注意：會撤銷此使用者現有的登入 API key，需要重新登入。`)) return

    setMovingUserId(user.id)
    try {
      const res = await fetch(`/api/auth/users/${user.id}/tenant`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json', ...getAdminHeaders() },
        body: JSON.stringify({ tenant_code: targetCode, revoke_api_keys: true }),
      })
      const body = await res.json().catch(() => ({}))
      if (!res.ok) {
        showToast('error', typeof (body as any)?.detail === 'string' ? (body as any).detail : `改綁定失敗 (HTTP ${res.status})`)
        return
      }
      showToast('success', `已改綁定：${user.username} → ${targetCode}`)
      setMoveUserTargets((prev) => {
        const next = { ...prev }
        delete next[user.id]
        return next
      })
      await refreshUsers()
    } catch {
      showToast('error', '改綁定失敗（網路或伺服器未啟動）')
    } finally {
      setMovingUserId(null)
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
          <div className="register-kv">
            <div className="register-k">管理者模式狀態</div>
            <div className="register-v">{adminUnlocked ? <span className="pill pill-ok">已啟用</span> : <span className="pill pill-off">已停用</span>}</div>
          </div>
        </div>

        <div className="register-form">
          <label className="register-label">
            管理者金鑰
            <input
              className="register-input"
              value={adminKeyDraft}
              onChange={(e) => setAdminKeyDraft(e.target.value)}
              onKeyDown={handleAdminKeyDraftKeyDown}
              placeholder="輸入 X-Admin-API-Key"
            />
          </label>

          <div className="register-actions">
            <button className="btn btn-primary" onClick={handleSaveAdminKey} disabled={adminKeySaving}>
              {adminKeySaving ? '驗證中…' : '保存'}
            </button>
            <button className="btn" onClick={handleClearAdminKey} disabled={adminKeySaving}>
              清除
            </button>
            <button className="btn" onClick={handleDisableAdminMode} disabled={adminKeySaving || !adminUnlocked}>
              停用
            </button>
          </div>

          <details className="register-details" open>
            <summary className="register-summary">自檢（WhoAmI / Bootstrap Status）</summary>
            <div className="register-actions">
              <button className="btn" onClick={refreshDiagnostics} disabled={diagLoading}>
                {diagLoading ? '更新中…' : '更新自檢資訊'}
              </button>
            </div>

            {whoami && storedTenantId && String(whoami.tenant_id || '') && String(whoami.tenant_id || '') !== storedTenantId ? (
              <p className="register-hint" style={{ color: '#b45309' }}>
                提醒：目前 localStorage 的區域為 <code>{storedTenantLabel || '（未知）'}</code>，但 whoami 回報的 tenant 為 <code>{whoamiTenantLabel || '—'}</code>。
                若要同步，請到下方「區域管理」點「套用為目前區域」。
              </p>
            ) : null}

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
                  <span className="admin-v" title={whoami.tenant_id || ''}>{whoamiTenantLabel || '—'}</span>
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
          </details>

          <details className="register-details" open>
            <summary className="register-summary">初始化（第一次／空資料庫）</summary>
            <p className="register-hint">
              這裡提供建立/選擇區域的工具（會寫入 localStorage：{TENANT_STORAGE_KEY}）。
            </p>

            <div className="register-row">
              <div className="register-kv">
                <div className="register-k">目前區域</div>
                <div className="register-v">{storedTenantId ? <code title={storedTenantId}>{storedTenantLabel || '（未知）'}</code> : <span className="muted">（未設定）</span>}</div>
              </div>
              <div className="register-actions">
                <button className="btn" onClick={handleAutoInitTenant} disabled={!hasAdminKey} title={!hasAdminKey ? '請先設定管理者金鑰' : ''}>
                  一鍵建立/選擇區域
                </button>
                <button className="btn" onClick={handleClearTenant}>清除區域</button>
              </div>
            </div>

            {!hasAnyActiveTenant ? (
              <div className="register-actions">
                <button className="btn btn-primary" onClick={handleBootstrapFirstTenant} disabled={!hasAdminKey} title={!hasAdminKey ? '請先設定管理者金鑰' : ''}>
                  建立第一個區域（bootstrap）
                </button>
              </div>
            ) : (
              <p className="register-hint">已偵測到有效區域，此 bootstrap 按鈕已隱藏（避免誤建）。</p>
            )}
          </details>
        </div>
      </section>

      <section className="register-card">
        <div className="admin-header-row">
          <div>
            <h2 className="register-title">區域管理</h2>
            <p className="register-hint">需要管理者金鑰才能完整 CRUD（新增/編輯/停用/設預設）。</p>
          </div>
          <div className="admin-header-actions">
            <label className="register-hint" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <input
                type="checkbox"
                checked={showInactiveTenants}
                onChange={(e) => setShowInactiveTenants(e.target.checked)}
              />
              顯示停用區域
            </label>
            <button className="btn" onClick={refreshTenants} disabled={loadingTenants}>
              {loadingTenants ? '更新中…' : '重新整理'}
            </button>
          </div>
        </div>

        <details className="register-details">
          <summary className="register-summary">新增區域</summary>
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
              {createTenantLoading ? '建立中…' : '建立區域'}
            </button>
          </div>
        </details>

        <div className="admin-table-wrap">
          <table className="admin-table">
            <thead>
              <tr>
                <th>area</th>
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
                  <td className="admin-mono"><span title={t.id}>{getTenantLabelById(t.id) || '（未知）'}</span></td>
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
                    <button className="btn btn-small" onClick={() => handleSetCurrentTenant(t)}>
                      套用為目前區域
                    </button>
                    <button
                      className="btn btn-small"
                      onClick={() => toggleTenantActive(t, !t.is_active)}
                      disabled={!hasAdminKey}
                      title={!hasAdminKey ? '請先設定管理者金鑰' : ''}
                      style={{ marginLeft: 8 }}
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
                <option value="manager">manager</option>
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
                <th>tenant</th>
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
                    <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                      <span className="admin-mono">{u.tenant_code || '—'}</span>
                      <select
                        className="admin-inline-input"
                        value={moveUserTargets[u.id] || ''}
                        onChange={(e) =>
                          setMoveUserTargets((prev) => ({
                            ...prev,
                            [u.id]: e.target.value,
                          }))
                        }
                      >
                        <option value="">改綁定到…</option>
                        {(tenants || []).map((t) => (
                          <option key={t.id} value={t.code}>
                            {t.code} ({t.name})
                          </option>
                        ))}
                      </select>
                      <button className="btn btn-small" onClick={() => moveUserToTenant(u)} disabled={movingUserId === u.id}>
                        {movingUserId === u.id ? '處理中…' : '改綁定'}
                      </button>
                    </div>
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
                      <option value="manager">manager</option>
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
                      停用
                    </button>
                  </td>
                </tr>
              ))}
              {!users?.length && (
                <tr>
                  <td colSpan={6} className="admin-empty">
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
