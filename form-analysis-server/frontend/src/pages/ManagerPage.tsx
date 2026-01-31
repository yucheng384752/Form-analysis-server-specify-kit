import { useEffect, useMemo, useState } from 'react'
import { useToast } from '../components/common/ToastContext'
import './../styles/manager-page.css'

type WhoAmI = {
  is_admin: boolean
  tenant_id?: string | null
  actor_user_id?: string | null
  actor_role?: string | null
  api_key_label?: string | null
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

async function readErrorDetail(res: Response): Promise<string> {
  const body = await res.json().catch(() => ({}))
  const detail = (body as any)?.detail
  return typeof detail === 'string' ? detail : ''
}

export function ManagerPage() {
  const { showToast } = useToast()

  const [whoami, setWhoami] = useState<WhoAmI | null>(null)
  const [loadingWhoami, setLoadingWhoami] = useState(false)

  const [users, setUsers] = useState<TenantUserRow[] | null>(null)
  const [loadingUsers, setLoadingUsers] = useState(false)
  const [includeInactive, setIncludeInactive] = useState(false)

  const [createUsername, setCreateUsername] = useState('')
  const [createPassword, setCreatePassword] = useState('')
  const [createRole, setCreateRole] = useState<'user' | 'manager'>('user')
  const [creating, setCreating] = useState(false)

  const [pendingRoleById, setPendingRoleById] = useState<Record<string, string>>({})
  const [pendingActiveById, setPendingActiveById] = useState<Record<string, boolean>>({})
  const [savingUserId, setSavingUserId] = useState<string | null>(null)

  const canManage = useMemo(() => {
    const r = String(whoami?.actor_role || '').trim()
    return r === 'admin' || r === 'manager'
  }, [whoami?.actor_role])

  const refreshWhoami = async () => {
    setLoadingWhoami(true)
    try {
      const res = await fetch('/api/auth/whoami')
      if (!res.ok) {
        const detail = await readErrorDetail(res)
        showToast('error', detail || '讀取身分失敗（可能尚未登入）')
        setWhoami(null)
        return
      }
      const body = (await res.json().catch(() => ({}))) as WhoAmI
      setWhoami(body)
    } catch {
      showToast('error', '讀取身分失敗（網路或伺服器未啟動）')
      setWhoami(null)
    } finally {
      setLoadingWhoami(false)
    }
  }

  const refreshUsers = async () => {
    setLoadingUsers(true)
    try {
      const params = new URLSearchParams()
      if (includeInactive) params.set('include_inactive', 'true')
      const res = await fetch(`/api/auth/users?${params.toString()}`)
      if (!res.ok) {
        const detail = await readErrorDetail(res)
        showToast('error', detail || `讀取使用者失敗（HTTP ${res.status}）`)
        setUsers(null)
        return
      }
      const body = (await res.json().catch(() => ([]))) as TenantUserRow[]
      const list = Array.isArray(body) ? body : []
      setUsers(list)

      const nextRole: Record<string, string> = {}
      const nextActive: Record<string, boolean> = {}
      for (const u of list) {
        nextRole[u.id] = u.role
        nextActive[u.id] = Boolean(u.is_active)
      }
      setPendingRoleById(nextRole)
      setPendingActiveById(nextActive)
    } catch {
      showToast('error', '讀取使用者失敗（網路或伺服器未啟動）')
      setUsers(null)
    } finally {
      setLoadingUsers(false)
    }
  }

  useEffect(() => {
    void refreshWhoami()
  }, [])

  useEffect(() => {
    if (!canManage) return
    void refreshUsers()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [includeInactive, canManage])

  const handleCreateUser = async () => {
    const username = createUsername.trim()
    const password = createPassword

    if (!username) {
      showToast('error', '請輸入帳號')
      return
    }
    if (!password || password.length < 8) {
      showToast('error', '密碼至少 8 碼')
      return
    }

    setCreating(true)
    try {
      const res = await fetch('/api/auth/users', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password, role: createRole }),
      })
      if (!res.ok) {
        const detail = await readErrorDetail(res)
        showToast('error', detail || `建立使用者失敗（HTTP ${res.status}）`)
        return
      }
      showToast('success', '建立使用者成功')
      setCreateUsername('')
      setCreatePassword('')
      setCreateRole('user')
      await refreshUsers()
    } catch {
      showToast('error', '建立使用者失敗（網路或伺服器未啟動）')
    } finally {
      setCreating(false)
    }
  }

  const handleSaveUser = async (u: TenantUserRow) => {
    const nextRole = String(pendingRoleById[u.id] ?? u.role).trim() || 'user'
    const nextActive = Boolean(pendingActiveById[u.id] ?? u.is_active)

    const patch: Record<string, any> = {}
    if (nextRole !== u.role) patch.role = nextRole
    if (nextActive !== Boolean(u.is_active)) patch.is_active = nextActive

    if (Object.keys(patch).length === 0) return

    setSavingUserId(u.id)
    try {
      const res = await fetch(`/api/auth/users/${u.id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(patch),
      })
      if (!res.ok) {
        const detail = await readErrorDetail(res)
        showToast('error', detail || `更新失敗（HTTP ${res.status}）`)
        return
      }
      showToast('success', '更新成功')
      await refreshUsers()
    } catch {
      showToast('error', '更新失敗（網路或伺服器未啟動）')
    } finally {
      setSavingUserId(null)
    }
  }

  const handleDeactivateUser = async (u: TenantUserRow) => {
    if (!confirm(`確定要停用使用者「${u.username}」？`)) return

    setSavingUserId(u.id)
    try {
      const res = await fetch(`/api/auth/users/${u.id}`, { method: 'DELETE' })
      if (!res.ok) {
        const detail = await readErrorDetail(res)
        showToast('error', detail || `停用失敗（HTTP ${res.status}）`)
        return
      }
      showToast('success', '已停用')
      await refreshUsers()
    } catch {
      showToast('error', '停用失敗（網路或伺服器未啟動）')
    } finally {
      setSavingUserId(null)
    }
  }

  return (
    <div className="manager-page">
      <div className="manager-header">
        <div>
          <h2 className="manager-title">場域使用者管理</h2>
          <div className="manager-subtitle">使用一般 API key（不需要管理者金鑰）</div>
        </div>
        <div className="manager-actions">
          <button className="btn-secondary" disabled={loadingWhoami} onClick={() => void refreshWhoami()}>
            {loadingWhoami ? '讀取中…' : '刷新身分'}
          </button>
          <button className="btn-secondary" disabled={loadingUsers || !canManage} onClick={() => void refreshUsers()}>
            {loadingUsers ? '讀取中…' : '刷新使用者'}
          </button>
        </div>
      </div>

      <div className="manager-card">
        <div className="manager-kv">
          <div className="k">tenant_id</div>
          <div className="v"><code>{whoami?.tenant_id || '—'}</code></div>
        </div>
        <div className="manager-kv">
          <div className="k">actor_role</div>
          <div className="v"><code>{whoami?.actor_role || '—'}</code></div>
        </div>
        <div className="manager-kv">
          <div className="k">api_key_label</div>
          <div className="v"><code>{whoami?.api_key_label || '—'}</code></div>
        </div>
      </div>

      {!canManage ? (
        <div className="manager-empty">目前角色不是 admin/manager，無法管理使用者。</div>
      ) : (
        <>
          <div className="manager-card">
            <div className="manager-row">
              <label className="manager-label">
                帳號
                <input className="manager-input" value={createUsername} onChange={(e) => setCreateUsername(e.target.value)} />
              </label>
              <label className="manager-label">
                密碼
                <input className="manager-input" type="password" value={createPassword} onChange={(e) => setCreatePassword(e.target.value)} />
              </label>
              <label className="manager-label">
                角色
                <select className="manager-select" value={createRole} onChange={(e) => setCreateRole(e.target.value as any)}>
                  <option value="user">user</option>
                  <option value="manager">manager</option>
                </select>
              </label>
              <div className="manager-row-actions">
                <button className="btn-secondary" disabled={creating} onClick={() => void handleCreateUser()}>
                  {creating ? '建立中…' : '建立使用者'}
                </button>
              </div>
            </div>
            <div className="manager-hint muted">註：manager 無法建立/指派 admin；也無法停用 admin 使用者。</div>
          </div>

          <div className="manager-card">
            <label className="manager-checkbox">
              <input type="checkbox" checked={includeInactive} onChange={(e) => setIncludeInactive(e.target.checked)} />
              顯示停用使用者
            </label>
          </div>

          <div className="manager-card">
            {users === null ? (
              <div className="muted">尚未載入</div>
            ) : users.length === 0 ? (
              <div className="muted">無使用者</div>
            ) : (
              <div className="manager-table-wrap">
                <table className="manager-table">
                  <thead>
                    <tr>
                      <th>帳號</th>
                      <th>角色</th>
                      <th>啟用</th>
                      <th>建立時間</th>
                      <th>最後登入</th>
                      <th style={{ width: 220 }}>操作</th>
                    </tr>
                  </thead>
                  <tbody>
                    {users.map((u) => {
                      const isAdminUser = String(u.role).trim() === 'admin'
                      const pendingRole = pendingRoleById[u.id] ?? u.role
                      const pendingActive = pendingActiveById[u.id] ?? Boolean(u.is_active)
                      const dirty = pendingRole !== u.role || Boolean(pendingActive) !== Boolean(u.is_active)
                      const busy = savingUserId === u.id

                      return (
                        <tr key={u.id} className={!u.is_active ? 'is-inactive' : ''}>
                          <td>
                            <div className="username">{u.username}</div>
                            <div className="muted small"><code>{u.id}</code></div>
                          </td>
                          <td>
                            {isAdminUser ? (
                              <code>admin</code>
                            ) : (
                              <select
                                className="manager-select"
                                value={pendingRole}
                                onChange={(e) => setPendingRoleById((p) => ({ ...p, [u.id]: e.target.value }))}
                              >
                                <option value="user">user</option>
                                <option value="manager">manager</option>
                              </select>
                            )}
                          </td>
                          <td>
                            <input
                              type="checkbox"
                              checked={Boolean(pendingActive)}
                              disabled={isAdminUser}
                              onChange={(e) => setPendingActiveById((p) => ({ ...p, [u.id]: e.target.checked }))}
                            />
                          </td>
                          <td><span className="small">{u.created_at || '—'}</span></td>
                          <td><span className="small">{u.last_login_at || '—'}</span></td>
                          <td>
                            <div className="row-actions">
                              <button className="btn-secondary" disabled={!dirty || busy || isAdminUser} onClick={() => void handleSaveUser(u)}>
                                {busy ? '處理中…' : '更新'}
                              </button>
                              <button className="btn-danger" disabled={busy || isAdminUser || !u.is_active} onClick={() => void handleDeactivateUser(u)}>
                                {busy ? '處理中…' : '停用'}
                              </button>
                            </div>
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  )
}
