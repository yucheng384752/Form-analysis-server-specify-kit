// src/App.tsx
import { useState } from "react";
import { UploadPage } from "./pages/UploadPage";
import { QueryPage } from "./pages/QueryPage";
import { ToastContainer } from "./components/common/ToastContainer";
import "./styles/app.css";

type MainTab = "upload" | "query";

function App() {
  const [tab, setTab] = useState<MainTab>("upload");

  return (
    <div className="app-root">
      <header className="app-header">
        <h1 className="app-title">檔案上傳系統</h1>
        <p className="app-subtitle">支援 CSV 檔案上傳、驗證與資料查詢</p>

        <div className="app-main-tabs">
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
        </div>
      </header>

      <main className="app-main">
        {tab === "upload" ? <UploadPage /> : <QueryPage />}
      </main>

      <ToastContainer />
    </div>
  );
}

export default App;
