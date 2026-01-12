"""
Analytics API 配置
針對多 server 並發呼叫與大資料量查詢優化
"""

class AnalyticsConfig:
    """分析 API 閥值與效能配置"""
    
    # ============ 閥值設定 ============
    # 基於月度查詢場景（600-1500 筆/月）
    AUTO_GZIP_THRESHOLD = 200              # 超過 200 筆自動壓縮
    SINGLE_RESPONSE_MAX = 1500             # 一次回傳上限（涵蓋單月）
    FORCE_PAGINATION_THRESHOLD = 3000      # 強制分頁閥值
    ABSOLUTE_MAX_RECORDS = 5000            # 絕對上限（防濫用）
    
    # ============ 查詢限制 ============
    MAX_PRODUCT_IDS_PER_REQUEST = 500      # 單次最多 500 個 ID
    MAX_MONTHS_RANGE = 3                   # 最多查詢 3 個月
    
    # ============ 並發處理設定 ============
    # Connection Pool 設定（已在 database.py 配置）
    DB_POOL_SIZE = 10                      # 連線池大小
    DB_MAX_OVERFLOW = 20                   # 最大溢出連線
    
    # Rate Limiting（防止濫用）
    RATE_LIMIT_REQUESTS_PER_MINUTE = 30    # 每分鐘最多 30 次請求
    RATE_LIMIT_BURST = 10                  # 允許短時爆發 10 次
    
    # 並發查詢鎖定機制（避免重複查詢）
    ENABLE_QUERY_CACHE = True              # 啟用查詢快取
    CACHE_TTL_SECONDS = 300                # 快取有效期 5 分鐘
    
    # ============ 效能設定 ============
    QUERY_TIMEOUT_SECONDS = 45             # 查詢超時（處理大資料量）
    TYPICAL_RECORDS_PER_DAY = 30           # 平均每天筆數（用於預估）
    MONTHLY_BUFFER_RATIO = 1.2             # 20% 緩衝
    
    # ============ 壓縮設定 ============
    GZIP_MINIMUM_SIZE = 1024               # 1KB 以上才壓縮
    GZIP_COMPRESSION_LEVEL = 6             # 壓縮等級（1-9，預設 6）
    
    # ============ 資料完整性設定 ============
    # 針對新規定：資料庫內沒有的值填入 null
    USE_NULL_FOR_MISSING = True            # 缺失值使用 null 而非省略
    PRESERVE_EMPTY_ARRAYS = True           # 空資料維持空陣列 []
    DEFAULT_NULL_FIELDS = [
        # 數值型欄位預設 null（而非 0）
        'Semi-finished Sheet Width(mm)',
        'Semi-finished Length(M)',
        'Weight(Kg)',
        'Line Speed(M/min)',
        'Current(A)',
        'Extruder Speed (rpm)',
        'Frame (cm)',
        # 溫度欄位預設 null
        'Actual Temp_C1(°C)', 'Actual Temp_C2(°C)', 'Actual Temp_C3(°C)',
        'Actual Temp_C4(°C)', 'Actual Temp_C5(°C)', 'Actual Temp_C6(°C)',
        'Actual Temp_C7(°C)', 'Actual Temp_C8(°C)',
        'Set Temp_C1(°C)', 'Set Temp_C2(°C)', 'Set Temp_C3(°C)',
        'Set Temp_C4(°C)', 'Set Temp_C5(°C)', 'Set Temp_C6(°C)',
        'Set Temp_C7(°C)', 'Set Temp_C8(°C)',
        'Actual Temp_A bucket(°C)', 'Set Temp_A bucket(°C)',
        'Actual Temp_Top(°C)', 'Actual Temp_Mid(°C)', 'Actual Temp_Bottom(°C)',
        'Set Temp_Top(°C)', 'Set Temp_Mid(°C)', 'Set Temp_Bottom(°C)',
        # P2 厚度欄位
        'Thicknessss High(μm)', 'Thicknessss Low(μm)',
        'Board Width(mm)',
    ]
