// src/pages/RegisterPage.tsx
import { useEffect, useMemo, useState, type KeyboardEventHandler } from 'react'
import { useTranslation } from 'react-i18next'
import { useToast } from '../components/common/ToastContext'
import { clearApiKeyValue, getApiKeyValue, setApiKeyValue } from '../services/auth'
import { clearTenantId, getTenantId, setTenantId } from '../services/tenant'
import { getTenantLabelById, writeTenantMap } from '../services/tenantMap'
import {
  clearAdminApiKeyValue,
  clearAdminUnlockedInSession,
  getAdminApiKeyHeaderName,
  setAdminApiKeyValue,
  setAdminUnlockedInSession,
} from '../services/adminAuth'
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
  const { t } = useTranslation()
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

  const storedTenantLabel = useMemo(() => {
    if (!storedTenantId) return ''

    const fromList = tenants?.find((t) => String(t?.id || '') === storedTenantId)
    if (fromList?.name || fromList?.code) {
      const code = String(fromList?.code || '').trim()
      return code || ''
    }

    return getTenantLabelById(storedTenantId)
  }, [storedTenantId, tenants])

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
      if (Array.isArray(data)) writeTenantMap(data)
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
      showToast('error', '區域 ID 不可為空')
      return
    }
    setTenantId(trimmed)
    setStoredTenantIdState(trimmed)
    const label = getTenantLabelById(trimmed)
    showToast('success', `已設定區域：${label || '（未知）'}`)
  }

  const handleClearTenant = () => {
    clearTenantId()
    setStoredTenantIdState('')
    showToast('info', '已清除區域 ID（localStorage）')
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
      showToast('success', '登入成功：已自動保存區域與權限')
    } catch {
      showToast('error', '登入失敗（網路或伺服器未啟動）')
    } finally {
      setLoginLoading(false)
    }
  }

  const handleLoginKeyDown: KeyboardEventHandler<HTMLInputElement> = (e) => {
    if (e.key !== 'Enter') return
    e.preventDefault()
    if (loginLoading) return
    void handlePasswordLogin()
  }

  const handleAdminKeyDown: KeyboardEventHandler<HTMLInputElement> = (e) => {
    if (e.key !== 'Enter') return
    e.preventDefault()
    if (adminKeyLoading) return
    void handleVerifyAdminKey()
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
        clearAdminUnlockedInSession()
        props.onAdminUnlocked?.(false)
        return
      }

      setAdminApiKeyValue(key)
      setAdminUnlockedInSession(true)
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
        <h2 className="register-title">{t('register.title')}</h2>

        {!hasApiKey ? (
          <>
            <div className="register-form">
              <div className="register-row">
                <label className="register-label" style={{ minWidth: 220, flex: 1 }}>
                  {t('register.tenantCodeOptional')}
                  <input
                    className="register-input"
                    type="text"
                    placeholder={t('register.tenantCodePlaceholder')}
                    value={loginTenantCode}
                    onChange={(e) => setLoginTenantCode(e.target.value)}
                    onKeyDown={handleLoginKeyDown}
                  />
                </label>
                <label className="register-label" style={{ minWidth: 220, flex: 1 }}>
                  {t('register.username')}
                  <input
                    className="register-input"
                    type="text"
                    placeholder={t('register.usernamePlaceholder')}
                    value={loginUsername}
                    onChange={(e) => setLoginUsername(e.target.value)}
                    onKeyDown={handleLoginKeyDown}
                  />
                </label>
                <label className="register-label" style={{ minWidth: 220, flex: 1 }}>
                  {t('register.password')}
                  <input
                    className="register-input"
                    type="password"
                    placeholder={t('register.passwordPlaceholder')}
                    value={loginPassword}
                    onChange={(e) => setLoginPassword(e.target.value)}
                    onKeyDown={handleLoginKeyDown}
                  />
                </label>
              </div>

              <div className="register-actions">
                <button className="btn-primary" disabled={loginLoading} onClick={handlePasswordLogin}>
                  {loginLoading ? t('register.loggingIn') : t('register.login')}
                </button>
              </div>
            </div>

            <details
              className="register-details"
              open={false}
            >
              <summary className="register-summary">{t('register.tips')}</summary>
              <div className="register-hint">
                {t('register.adminHint')}
              </div>
              <div className="register-form" style={{ marginTop: '0.75rem' }}>
                <label className="register-label">
                  {t('register.adminKey')}
                  <input
                    className="register-input"
                    type="password"
                    placeholder={t('register.adminKeyPlaceholder')}
                    value={adminKeyDraft}
                    onChange={(e) => setAdminKeyDraft(e.target.value)}
                    onKeyDown={handleAdminKeyDown}
                  />
                </label>
                <div className="register-actions">
                  <button className="btn-secondary" disabled={adminKeyLoading} onClick={handleVerifyAdminKey}>
                    {adminKeyLoading ? t('register.verifying') : t('register.verifyAndUnlock')}
                  </button>
                </div>
              </div>
            </details>
          </>
        ) : (
          <>
            <div className="register-row" style={{ marginTop: '0.75rem' }}>
              <div className="register-kv">
                <div className="register-k">{t('register.tenantId')}</div>
                <div className="register-v">
                  {storedTenantId ? (
                    <>
                      <strong title={storedTenantId}>{storedTenantLabel || '（未知）'}</strong>
                    </>
                  ) : (
                    <span className="muted">{t('register.tenantNotSaved')}</span>
                  )}
                </div>
              </div>
              <div className="register-kv">
                <div className="register-k">{t('register.role')}</div>
                <div className="register-v">
                  {whoami ? (
                    <code>{whoami.is_admin ? 'admin' : (whoami.actor_role || 'user')}</code>
                  ) : (
                    <span className="muted">{t('register.roleLoading')}</span>
                  )}
                </div>
              </div>
              <div className="register-actions">
                <button className="btn-secondary" disabled={diagLoading} onClick={handleFetchDiagnostics}>
                  {diagLoading ? t('common.loading') : t('register.updateIdentity')}
                </button>
                <button className="btn-secondary" onClick={handleClearApiKey}>{t('register.logout')}</button>
              </div>
            </div>

            <details className="register-details" open>
              <summary className="register-summary">{t('register.tenantSettings')}</summary>
              <div className="register-row">
                <div className="register-kv">
                  <div className="register-k">{t('register.tenantSelected')}</div>
                  <div className="register-v">{storedTenantId ? <span title={storedTenantId}>{storedTenantLabel || '（未知）'}</span> : <span className="muted">{t('register.none')}</span>}</div>
                </div>
                <div className="register-actions">
                  <button className="btn-secondary" onClick={handleClearTenant}>{t('register.clearTenantId')}</button>
                </div>
              </div>

              <div className="register-actions">
                <button className="btn-secondary" disabled={loadingTenants} onClick={refreshTenants}>
                  {loadingTenants ? t('common.loading') : t('register.refreshTenants')}
                </button>
                {tenantsAuthRequired === true && <span className="muted">{t('register.tenantsNeedAuth')}</span>}
              </div>

              {tenants && (
                <div className="register-tenants">
                  <div className="register-tenants-title">{t('register.tenants')}</div>
                  {tenants.length === 0 ? (
                    <div className="muted">{t('register.tenantsEmpty')}</div>
                  ) : (
                    <div className="register-tenants-grid">
                      {tenants.map((tenant) => (
                        <div key={tenant.id} className="register-tenant-item">
                          <div className="register-tenant-id">
                            <code title={tenant.id}>{getTenantLabelById(tenant.id) || '（未知）'}</code>
                          </div>
                          <div className="register-tenant-meta muted">
                            name={tenant.name ?? '-'} / code={tenant.code ?? '-'}
                          </div>
                          <div className="register-actions">
                            <button className="btn-secondary" onClick={() => handleSetTenant(tenant.id)}>{t('register.useTenant')}</button>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </details>

            <details className="register-details">
              <summary className="register-summary">{t('register.adminTips')}</summary>
              <div className="register-hint">{t('register.adminTipsText')}</div>
              <div className="register-form" style={{ marginTop: '0.75rem' }}>
                <label className="register-label">
                  {t('register.adminKey')}
                  <input
                    className="register-input"
                    type="password"
                    placeholder={t('register.adminKeyPlaceholder')}
                    value={adminKeyDraft}
                    onChange={(e) => setAdminKeyDraft(e.target.value)}
                    onKeyDown={handleAdminKeyDown}
                  />
                </label>
                <div className="register-actions">
                  <button className="btn-secondary" disabled={adminKeyLoading} onClick={handleVerifyAdminKey}>
                    {adminKeyLoading ? t('register.verifying') : t('register.verifyAndUnlock')}
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
