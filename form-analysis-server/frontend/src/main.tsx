import { StrictMode } from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.tsx'
import { ToastProvider } from './components/common/ToastContext.tsx'
import './index.css'
import './styles/figma.css'

const TENANT_STORAGE_KEY = 'form_analysis_tenant_id'

// Global fetch wrapper: auto-inject X-Tenant-Id for all /api* requests except /api/tenants.
// This prevents accidental cross-tenant calls and removes per-call header boilerplate.
const originalFetch = window.fetch.bind(window)

window.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
  try {
    const tenantId = window.localStorage.getItem(TENANT_STORAGE_KEY) || ''

    // Determine request URL
    const urlString =
      typeof input === 'string'
        ? input
        : input instanceof URL
          ? input.toString()
          : input.url

    const url = new URL(urlString, window.location.href)
    const isApiPath = url.pathname.startsWith('/api')
    const isTenantListPath = url.pathname.startsWith('/api/tenants')

    if (!tenantId || !isApiPath || isTenantListPath) {
      return originalFetch(input as any, init)
    }

    const mergedHeaders = new Headers(init?.headers || (input instanceof Request ? input.headers : undefined))
    if (!mergedHeaders.has('X-Tenant-Id')) {
      mergedHeaders.set('X-Tenant-Id', tenantId)
    }

    if (input instanceof Request) {
      const wrappedRequest = new Request(input, { ...init, headers: mergedHeaders })
      return originalFetch(wrappedRequest)
    }

    return originalFetch(input as any, { ...init, headers: mergedHeaders })
  } catch {
    // Fallback: never block fetch due to wrapper errors
    return originalFetch(input as any, init)
  }
}

// Render the React application
ReactDOM.createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ToastProvider>
      <App />
    </ToastProvider>
  </StrictMode>,
)