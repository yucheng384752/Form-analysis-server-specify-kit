import { StrictMode } from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.tsx'
import { ToastProvider } from './components/common/ToastContext.tsx'
import './index.css'
import './styles/figma.css'

import { installGlobalFetchWrapper } from './services/fetchWrapper'

installGlobalFetchWrapper()

// Render the React application
ReactDOM.createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ToastProvider>
      <App />
    </ToastProvider>
  </StrictMode>,
)