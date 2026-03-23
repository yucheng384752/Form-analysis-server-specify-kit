# PDF 上傳：主按鈕（CTA）整合規格

最後更新：2026-01-23

對應 TODO：PDF 上傳時，"上傳" 與 "開始轉檔" 按鈕整合在一起（NEEDS-SPEC）

## 目標

在 UploadPage 的 PDF 卡片中，提供「單一 primary CTA」覆蓋兩種狀態：
- 未上傳：引導使用者上傳 PDF
- 已上傳：引導使用者開始 PDF→CSV 轉檔

避免：
- 使用者誤觸開始轉檔（尚未上傳）
- 使用者搞不清楚下一步

## 使用者流程

1) 初始（尚未選檔/尚未上傳）
- Primary CTA 文案：`上傳 PDF`
- 點擊行為：打開檔案選擇器（accept=pdf）

2) 已選檔但尚未上傳（本機列表中）
- Primary CTA 文案：`上傳 PDF`
- 點擊行為：呼叫上傳 API，成功後進入狀態 3

3) 已上傳成功（有 process_id，待轉檔）
- Primary CTA 文案：`開始轉檔`
- 點擊行為：呼叫 PDF convert start API

4) 轉檔中
- Primary CTA：disabled
- 文案：`轉檔中…`

5) 轉檔完成（已 ingest 並建立 CSV UploadJob）
- Primary CTA 可改為 Secondary（或隱藏）
- Primary CTA 若保留：`查看 CSV`（可選，視 UI 決策）

## 錯誤/保護

- 若缺少 `process_id`：顯示 toast 錯誤（例如：`找不到 process_id，請先上傳 PDF`）
- 轉檔失敗：toast 顯示錯誤訊息，並提供 Retry（次要按鈕）

## 修改檔案（候選）

- `form-analysis-server/frontend/src/pages/UploadPage.tsx`

## 完成條件

- 只有一個 primary CTA
- 覆蓋「未上傳/已上傳」兩種狀態且不誤觸
- `npm run type-check` 通過
