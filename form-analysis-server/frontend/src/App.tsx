// src/App.tsx
import { useState } from "react";
import { UploadPage } from "./pages/UploadPage";
import { QueryPage } from "./pages/QueryPage";
import { RegisterPage } from "./pages/RegisterPage";
import { ToastContainer } from "./components/common/ToastContainer";
import LogViewer from "./components/SimpleLogViewer";
import "./styles/app.css";

type MainTab = "upload" | "query" | "register" | "logs";

function App() {
  const [tab, setTab] = useState<MainTab>("upload");

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
            註冊/初始化
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
          <RegisterPage />
        ) : tab === "upload" ? (
          <UploadPage />
        ) : tab === "query" ? (
          <QueryPage />
        ) : (
          <LogViewer />
        )}
      </main>

      <ToastContainer />
    </div>
  );
}

export default App;
