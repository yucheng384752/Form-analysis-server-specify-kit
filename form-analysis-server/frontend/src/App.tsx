// src/App.tsx
import { useEffect, useMemo, useState } from "react";
import { UploadPage } from "./pages/UploadPage";
import { QueryPage } from "./pages/QueryPage";
import { RegisterPage } from "./pages/RegisterPage";
import { AdminPage } from "./pages/AdminPage";
import { ToastContainer } from "./components/common/ToastContainer";
import LogViewer from "./components/SimpleLogViewer";
import "./styles/app.css";

import { getAdminApiKeyValue } from "./services/adminAuth";

type MainTab = "upload" | "query" | "register" | "admin" | "logs";

function App() {
  const [tab, setTab] = useState<MainTab>("upload");

  const [adminUnlocked, setAdminUnlocked] = useState<boolean>(() => Boolean(getAdminApiKeyValue()));
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
        <h1 className="app-title">檔案上傳系統</h1>
        <p className="app-subtitle">支援 CSV 檔案上傳、驗證與資料查詢</p>

        <div className="app-main-tabs">
          <button
            className={`app-main-tab ${tab === "register" ? "is-active" : ""}`}
            onClick={() => setTab("register")}
          >
            登入
          </button>
          <button
            className={`app-main-tab ${tab === "upload" ? "is-active" : ""}`}
            onClick={() => setTab("upload")}
          >
            檔案上傳
          </button>
          <button
            className={`app-main-tab ${tab === "query" ? "is-active" : ""}`}
            onClick={() => setTab("query")}
          >
            資料查詢
          </button>
          {canShowAdmin ? (
            <button
              className={`app-main-tab ${tab === "admin" ? "is-active" : ""}`}
              onClick={() => setTab("admin")}
            >
              管理者
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
        ) : tab === "admin" ? (
          <AdminPage />
        ) : (
          <LogViewer />
        )}
      </main>

      <ToastContainer />
    </div>
  );
}

export default App;
