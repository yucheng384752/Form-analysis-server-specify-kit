# 資料分析操作文件

本文件描述資料分析頁面（daily 模式/客訴模式）的操作方式與 Pareto 圖表來源。

## 1) 分析模式說明

- daily 模式：以日期範圍/站別進行分析，支援 NG 鑽取與 Pareto 圖表。
- 客訴模式（product_id）：以產品編號進行追溯分析，呈現客訴分析圖表與改善報告。

## 2) daily 模式操作流程

1. 進入「資料分析」頁面。
2. 選擇日期範圍與站別（P2/P3）。
3. 點擊「分析」開始計算。
4. 在類別圖表中點擊「NG」柱狀圖：
   - 進入 NG list 介面。
   - NG list 上方顯示 Pareto 圖表。

## 3) Pareto 圖表（daily 模式）

NG list 上方會顯示兩種 Pareto：

- NG Pareto（count_0）：
  - 來源：分類統計 `categorical_statistics` 的 `P2.NG_code`。
  - 數值：使用 `count_0` 作為 NG 計數。

- Feature Pareto（final_raw_score）：
  - 來源：`extraction_result.final_raw_score`。
  - 數值：使用特徵的最終分數作 Pareto 排序。

## 4) 可調設定（保留彈性）

以下設定位於前端 [form-analysis-server/frontend/src/pages/AnalyticsPage.tsx](form-analysis-server/frontend/src/pages/AnalyticsPage.tsx)：

- `PARETO_ENABLED_DAILY`：是否啟用 daily Pareto
- `PARETO_TOP_N`：最多顯示項目數
- `PARETO_CUM_THRESHOLD`：累積比例門檻（例如 0.8 = 80%）
- `PARETO_MIN_COUNT`：最小值門檻
- `PARETO_SHOW_ZERO`：是否顯示 0 值
- `PARETO_SOURCE_NG`：是否顯示 NG Pareto
- `PARETO_SOURCE_FEATURE`：是否顯示 Feature Pareto

## 5) 常見問題

- 看不到 Pareto 圖：
  - 確認是否已點擊「NG」柱狀圖進入 NG list。
  - 確認 daily 模式有資料（analysis 結果與 extraction 結果）。

- NG Pareto 沒資料：
  - `categorical_statistics` 中缺少 `P2.NG_code`。
  - 或所有 `count_0` 都為 0。

- Feature Pareto 沒資料：
  - `extraction_result.final_raw_score` 為空或無數值。

