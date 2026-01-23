// src/App.tsx
import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { UploadPage } from "./pages/UploadPage";
import { QueryPage } from "./pages/QueryPage";
import { RegisterPage } from "./pages/RegisterPage";
import { AdminPage } from "./pages/AdminPage";
import { AnalyticsPage } from "./pages/AnalyticsPage";
import { ToastContainer } from "./components/common/ToastContainer";
import LogViewer from "./components/SimpleLogViewer";
import "./styles/app.css";

import { getAdminApiKeyValue, isAdminUnlockedInSession } from "./services/adminAuth";

type MainTab = "upload" | "query" | "analysis" | "register" | "admin" | "logs";

function App() {
  const { t, i18n } = useTranslation();
  const [tab, setTab] = useState<MainTab>("register");

  const currentLang = useMemo(() => {
    const raw = (i18n.resolvedLanguage || i18n.language || 'zh-TW').toLowerCase();
    if (raw === 'zh-tw' || raw === 'zh_tw') return 'zh-TW';
    if (raw.startsWith('zh')) return 'zh-TW';
    return 'en';
  }, [i18n.language, i18n.resolvedLanguage]);

  const [adminUnlocked, setAdminUnlocked] = useState<boolean>(() => Boolean(getAdminApiKeyValue()) && isAdminUnlockedInSession());
  const canShowAdmin = useMemo(() => adminUnlocked, [adminUnlocked]);

  useEffect(() => {
    // If admin key is cleared, force-exit admin tab.
    if (!canShowAdmin && tab === "admin") {
      setTab("register");
    }
  }, [canShowAdmin, tab]);

  return (
    <div className="app-root">
      <header className="app-header">
        <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: '12px' }}>
          <div>
            <h1 className="app-title">{t('app.title')}</h1>
            <p className="app-subtitle">{t('app.subtitle')}</p>
          </div>

          <div className="app-lang-switch" aria-label={t('language.label')}>
            <span className="app-lang-label">{t('language.label')}</span>
            <div className="app-lang-tabs" role="tablist" aria-label={t('language.label')}>
              <button
                type="button"
                role="tab"
                aria-selected={currentLang === 'zh-TW'}
                className={`app-lang-tab ${currentLang === 'zh-TW' ? 'is-active' : ''}`}
                onClick={() => i18n.changeLanguage('zh-TW')}
              >
                {t('language.zhTW')}
              </button>
              <button
                type="button"
                role="tab"
                aria-selected={currentLang === 'en'}
                className={`app-lang-tab ${currentLang === 'en' ? 'is-active' : ''}`}
                onClick={() => i18n.changeLanguage('en')}
              >
                {t('language.en')}
              </button>
            </div>
          </div>
        </div>

        <div className="app-main-tabs">
          <button
            className={`app-main-tab ${tab === "register" ? "is-active" : ""}`}
            onClick={() => setTab("register")}
          >
            {t('tabs.register')}
          </button>
          <button
            className={`app-main-tab ${tab === "upload" ? "is-active" : ""}`}
            onClick={() => setTab("upload")}
          >
            {t('tabs.upload')}
          </button>
          <button
            className={`app-main-tab ${tab === "query" ? "is-active" : ""}`}
            onClick={() => setTab("query")}
          >
            {t('tabs.query')}
          </button>
          <button
            className={`app-main-tab ${tab === "analysis" ? "is-active" : ""}`}
            onClick={() => setTab("analysis")}
          >
            {t('tabs.analysis')}
          </button>
          {canShowAdmin ? (
            <button
              className={`app-main-tab ${tab === "admin" ? "is-active" : ""}`}
              onClick={() => setTab("admin")}
            >
              {t('tabs.admin')}
            </button>
          ) : null}
          {/* <button
            className={`app-main-tab ${tab === "logs" ? "is-active" : ""}`}
            onClick={() => setTab("logs")}
          >
            系統日誌
          </button> */}
          {/* <button
            className={`app-main-tab ${tab === "analysis" ? "is-active" : ""}`}
            onClick={() => setTab("analysis")}
          >
            系統日誌
          </button> */}
        </div>
      </header>

      <main className="app-main">
        {tab === "register" ? (
          <RegisterPage onAdminUnlocked={(ok) => setAdminUnlocked(Boolean(ok))} />
        ) : tab === "upload" ? (
          <UploadPage />
        ) : tab === "query" ? (
          <QueryPage />
        ) : tab === "analysis" ? (
          <AnalyticsPage />
        ) : tab === "admin" ? (
          <AdminPage onAdminLocked={() => setAdminUnlocked(false)} onAdminUnlocked={() => setAdminUnlocked(true)} />
        ) : (
          <LogViewer />
        )}
      </main>

      <ToastContainer />
    </div>
  );
}

export default App;
