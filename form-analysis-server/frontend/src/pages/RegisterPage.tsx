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

  const [apiKeyDraft, setApiKeyDraft] = useState('')
  const [adminKeyDraft, setAdminKeyDraft] = useState('')
  const [tenants, setTenants] = useState<TenantRow[] | null>(null)
  const [loadingTenants, setLoadingTenants] = useState(false)

  const storedApiKey = useMemo(() => {
    const v = getApiKeyValue()
    return v ? `${v.slice(0, 4)}…${v.slice(-4)}` : ''
  }, [])

  const storedTenantId = useMemo(() => getTenantId(), [])

  const apiKeyHeaderName = getApiKeyHeaderName()
  const adminKeyHeaderName = getAdminApiKeyHeaderName()

  const storedAdminKey = useMemo(() => {
    const v = getAdminApiKeyValue()
    return v ? `${v.slice(0, 4)}…${v.slice(-4)}` : ''
  }, [])

  const refreshTenants = async () => {
    setLoadingTenants(true)
    try {
      const res = await fetch('/api/tenants')
      if (!res.ok) {
        const body = await res.json().catch(() => ({}))
        const detail = (body as any)?.detail
        if (res.status === 401) {
          showToast('error', '後端已啟用 API key 驗證：請先設定 API key（或暫時關閉 AUTH_MODE 進行 bootstrap）')
          setTenants(null)
          return
        }
        showToast('error', typeof detail === 'string' ? detail : `取得 tenants 失敗 (HTTP ${res.status})`)
        setTenants(null)
        return
      }
      const data = (await res.json()) as TenantRow[]
      setTenants(Array.isArray(data) ? data : [])
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
    showToast('success', '已保存 API key（localStorage）')
  }

  const handleClearApiKey = () => {
    clearApiKeyValue()
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
    showToast('success', '已保存 Admin API key（localStorage）')
  }

  const handleClearAdminKey = () => {
    clearAdminApiKeyValue()
    showToast('info', '已清除 Admin API key（localStorage）')
  }

  const handleAutoInitTenant = async () => {
    try {
      const id = await ensureTenantIdWithOptions({ notify: true, reason: 'bootstrap' })
      if (!id) {
        showToast('error', '無法自動決定 tenant（可能存在多個 tenant 且沒有 default）')
        return
      }
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
    showToast('success', `已設定 Tenant ID：${trimmed}`)
  }

  const handleClearTenant = () => {
    clearTenantId()
    showToast('info', '已清除 Tenant ID（localStorage）')
  }

  return (
    <div className="register-page">
      <section className="register-card">
        <h2 className="register-title">註冊 / 初始化（tenant + API key）</h2>
        <p className="register-hint">
          這個頁面做兩件事：
          <strong>（1）保存/清除 API key</strong>、
          <strong>（2）初始化/選擇 tenant</strong>。
        </p>
      </section>

      <section className="register-card">
        <h3 className="register-subtitle">你需要準備哪些資料（交給註冊頁）</h3>
        <ul className="register-list">
          <li>
            <strong>Admin API key（raw key）</strong>：只給管理者使用，用來建立/管理 tenants（key：{ADMIN_API_KEY_STORAGE_KEY}）
          </li>
          <li>
            <strong>API key（raw key）</strong>：由後端腳本建立（只顯示一次），貼到此頁保存到 localStorage（key：{API_KEY_STORAGE_KEY}）
          </li>
          <li>
            <strong>Tenant</strong>：通常只會有一個。若為空資料庫：可在此頁按「自動初始化 Tenant」建立預設 tenant（UT / ut）
          </li>
          <li>
            <strong>（可選）Tenant ID</strong>：當環境裡存在多個 tenant、且沒有唯一 default 時，需要手動指定（key：{TENANT_STORAGE_KEY}）
          </li>
        </ul>
      </section>

      <section className="register-card">
        <h3 className="register-subtitle">Admin API key（管理者）</h3>
        <div className="register-row">
          <div className="register-kv">
            <div className="register-k">Header 名稱</div>
            <div className="register-v"><code>{adminKeyHeaderName}</code></div>
          </div>
          <div className="register-kv">
            <div className="register-k">目前已保存</div>
            <div className="register-v">{storedAdminKey ? <code>{storedAdminKey}</code> : <span className="muted">（無）</span>}</div>
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
            備註：若後端已把 <code>AUTH_MODE</code> 預設成 <code>api_key</code>，首次建立 tenant 需要管理者提供 admin key。
          </p>
        </div>
      </section>

      <section className="register-card">
        <h3 className="register-subtitle">API key 設定</h3>
        <div className="register-row">
          <div className="register-kv">
            <div className="register-k">Header 名稱</div>
            <div className="register-v"><code>{apiKeyHeaderName}</code></div>
          </div>
          <div className="register-kv">
            <div className="register-k">目前已保存</div>
            <div className="register-v">{storedApiKey ? <code>{storedApiKey}</code> : <span className="muted">（無）</span>}</div>
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
            備註：若後端已啟用 <code>AUTH_MODE=api_key</code>，沒有 key 會拿到 401。
            初次上線通常是：先建立 tenant → 再 bootstrap key → 再開啟 AUTH_MODE。
          </p>
        </div>
      </section>

      <section className="register-card">
        <h3 className="register-subtitle">Tenant 初始化 / 選擇</h3>

        <div className="register-row">
          <div className="register-kv">
            <div className="register-k">目前已保存 Tenant ID</div>
            <div className="register-v">{storedTenantId ? <code>{storedTenantId}</code> : <span className="muted">（無）</span>}</div>
          </div>
          <div className="register-actions">
            <button className="btn-primary" onClick={handleAutoInitTenant}>自動初始化 Tenant</button>
            <button className="btn-secondary" onClick={handleClearTenant}>清除 Tenant ID</button>
          </div>
        </div>

        <div className="register-actions">
          <button className="btn-secondary" disabled={loadingTenants} onClick={refreshTenants}>
            {loadingTenants ? '讀取中…' : '刷新 tenants 列表'}
          </button>
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
