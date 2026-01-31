# I18N 擴充範圍（Scope）

最後更新：2026-01-23

目的：
- 讓中/英文切換時，主要流程不再混雜硬編中文/英文
- 將 i18n 工作拆成可 merge 的批次（避免永遠補不完）

## 現況

- i18n 基礎已存在：`frontend/src/i18n.ts`
- 翻譯檔：
  - `frontend/src/locales/zh-TW/common.json`
  - `frontend/src/locales/en/common.json`
- 已有大量 key（含 Upload/Query/Analytics 的大部分文字），但仍有不少 **alert/toast/modal/table header** 是硬編字串。

## Key 命名規範（建議）

- 預設 namespace：`common`
- 頁面級：`register.*`, `upload.*`, `query.*`, `analytics.*`, `admin.*`
- 通用 UI：`common.*`（OK/Cancel/Loading/NoData 等）
- 錯誤/提示：放在各頁面的 `*.errors.*` 或 `*.toasts.*`，避免散落。

## 待補齊清單（頁面/元件）

### Pages

- RegisterPage
  - 待補：多數 toast 仍為硬編中文

- UploadPage
  - 已有：卡片狀態（部分）
  - 待補：toast 文案、Modal（批次匯入確認）、錯誤訊息、按鈕提示

- QueryPage
  - 已有：頁面標題/描述/提示/placeholder（多數）
  - 待補：alert 錯誤訊息、表格欄位標題、EditRecordModal 文案、Modal 按鈕

- AnalyticsPage
  - 已有：大部分 UI 文案已改用 i18n
  - 待補：若有硬編錯誤訊息/空狀態（持續掃描）

- AdminPage
  - 待補：多數 toast/confirm/label

### Shared Components

- `components/common/Modal.tsx`
  - 待補：取消/確認預設文字不應硬編（需由呼叫端傳入或由 component 內取 t）

- `components/EditRecordModal.tsx`
  - 待補：標題、Reason/Note/按鈕、錯誤處理（alert → toast）

## 分批落地計畫

- Batch A（示範頁，需完整）：**QueryPage**
  - 完成條件：
    - 表格欄位標題/空狀態/錯誤提示
    - Toast/Modal 文案
    - EditRecordModal 文案

- Batch B：UploadPage
- Batch C：RegisterPage + AdminPage

## 檢查方式

- 前端：`npm run type-check`
- 可選：加入 lint/掃描規則，避免新增硬編中文（視 repo 工具現況再決定）
