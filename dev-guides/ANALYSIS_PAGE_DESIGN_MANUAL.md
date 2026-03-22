## daily 模式
1.日期輸入UI -> 狀態
    - input 日期模式/日期選擇器
    - function: handleRangeModeChange() 更新 rangeMode -> 呼叫 applyAnchorForMode()
    - output: 更新 startDate, endDate
    - 檔案: AnalysisPage.tsx
2. 點擊「分析」送出分析請求
    - input: startDate, endDate, statoins
    - function: handleRun() -> requectAnalyz()
    - output: HTTP POST  /api/v2/analytics/analyze，payload 帶 start_date/end_date
    - 檔案: AnalyticsPage.tsx
3. 解析分析結果 → 存 state
    - Input: API 回傳 JSON
    - Function: normalizeAnalysisResult()
    - Output: analysisResult（State）
    - 位置：AnalyticsPage.tsx, AnalyticsPage.tsx
4. 分類結果 → 直方圖資料
    - Input: analysisResult
    - Function: categoryCards (useMemo) → winderChartData (useMemo)
    - Output: winderChartData（直方圖用的序列）                                                         
    - 位置：AnalyticsPage.tsx
5. 渲染直方圖