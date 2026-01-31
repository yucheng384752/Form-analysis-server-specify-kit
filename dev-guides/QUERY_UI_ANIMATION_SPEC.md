# 查詢/進階查詢：按鈕視覺一致 + 展開動畫規格

最後更新：2026-01-23

目標：
- QueryPage 上「查詢」「清除」「進階搜尋」等按鈕視覺一致
- 進階搜尋展開/收合有一致的動畫與可讀性

## 範圍

- `frontend/src/pages/QueryPage.tsx`
- `frontend/src/components/AdvancedSearch.tsx`
- `frontend/src/styles/query-page.css`
- `frontend/src/components/AdvancedSearch/advanced-search.css`（若需要）

## 按鈕規格

- Primary（查詢）
  - 高度：36px
  - padding：左右 14px
  - font-size：14px
  - radius：8px
  - 狀態：hover 亮度 +5%，active 下壓 1px

- Secondary（清除、進階搜尋）
  - 同 Primary 高度與 padding
  - 顏色採用既有 `.btn-secondary` 或等價樣式

- Icon + Text（進階搜尋）
  - icon size：16px
  - icon 與文字間距：6px

## 展開動畫規格（Advanced Search Panel）

- 動畫時長：180ms
- timing-function：`cubic-bezier(0.2, 0.8, 0.2, 1)`
- 動畫屬性：
  - `max-height` + `opacity`（避免 layout 大抖動）
  - `overflow: hidden`

- 展開狀態
  - `max-height`: 520px（足夠容納全部欄位；必要時可調大）
  - `opacity`: 1

- 收合狀態
  - `max-height`: 0
  - `opacity`: 0

## 可用性/無障礙

- `AdvancedSearch` container 建議保留：
  - `aria-hidden={!isExpanded}`
  - `fieldset disabled={!isExpanded}`（避免收合時仍可 tab 到 input）

## 完成條件（NEEDS-SPEC）

- 文件有明確數值（尺寸/間距/動效時長）
- 或明確說明採用既有 Radix/現成樣式（不另造 token）
