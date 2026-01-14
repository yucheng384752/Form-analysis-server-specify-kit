"""
侑特 (UT) 資料查詢 API
提供按月查詢各站點資料（P1, P2, P3, P1+P2+P3）
"""

from fastapi import APIRouter, Depends, Query, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Dict
import time

from app.core.database import get_db
from app.services.ut_flattener import UTFlattener

router = APIRouter(prefix="/api/v2/ut")

# ============ Rate Limiting（簡易實作）============
_rate_limit_store = {}  # {ip: [timestamps]}

def check_rate_limit(request: Request):
    """Rate limiting 檢查（每 IP 每分鐘最多 30 次）"""
    client_ip = request.client.host
    current_time = time.time()
    window_start = current_time - 60
    
    if client_ip in _rate_limit_store:
        _rate_limit_store[client_ip] = [
            ts for ts in _rate_limit_store[client_ip]
            if ts > window_start
        ]
        request_count = len(_rate_limit_store[client_ip])
    else:
        _rate_limit_store[client_ip] = []
        request_count = 0
    
    if request_count >= 30:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded. Max 30 requests per minute."
        )
    
    _rate_limit_store[client_ip].append(current_time)


# ============ API 端點 ============

@router.get("/flatten")
async def flatten_ut_data(
    year: int = Query(..., ge=2010, le=2050, description="年份（2010-2050）"),
    month: int = Query(..., ge=1, le=12, description="月份（1-12）"),
    location: str = Query(
        default="P1+P2+P3",
        description="資料來源（P1=原料, P2=分條, P3=生產, P1+P2+P3=完整追溯）",
        pattern="^(P1|P2|P3|P1\\+P2\\+P3)$"
    ),
    type: str = Query(default="ut", description="資料類型（ut=侑特）"),
    request: Request = None,
    session: AsyncSession = Depends(get_db)
):
    """
    查詢侑特資料（按月）
    
    **使用場景**：外部 server 按月拉取各站點生產資料
    
    **參數**：
    - `year`: 年份（2010-2050）
    - `month`: 月份（1-12）
    - `location`: 資料來源
      - `P1`: 只返回原料/擠出資料
      - `P2`: 只返回分條資料
      - `P3`: 只返回生產資料
      - `P1+P2+P3`: 返回完整追溯鏈資料（預設）
    - `type`: 資料類型（目前僅支援 "ut"）
    
    **返回格式**：
    ```json
    [
      {
        "timestamp": "20250401",     // P3: YYYYMMDD / P1+P2: YYMMDD
        "type": "ut",
        "location": "P1+P2+P3",
        "metrics": {
          "Actual Temp_C1(℃)": 190,  // P1 欄位
          "Sheet Width(mm)": 7.964,   // P2 欄位
          "Produce_No.": "20250401_P22_2381_301",  // P3 欄位
          ...
        }
      }
    ]
    ```
    
    **時間格式說明**：
    - P3 單獨查詢：`"timestamp": "20250401"` (8位數 YYYYMMDD)
    - P1/P2 單獨查詢：`"timestamp": "250303"` (6位數 YYMMDD)
    - P1+P2+P3 組合查詢：使用 P3 格式 (8位數 YYYYMMDD)
    
    **空資料處理**：
    - 當 `location=P1+P2+P3` 時，若找不到對應的 P1 或 P2 資料，相關欄位填入 `null`
    
    **性能優化**：
    - 資料量 ≥ 200 筆自動啟用 gzip 壓縮
    - Rate Limiting: 每 IP 每分鐘最多 30 次請求
    """
    # Rate limiting 檢查
    if request:
        check_rate_limit(request)
    
    # 初始化 flattener
    flattener = UTFlattener(session)
    
    # 執行查詢
    try:
        result = await flattener.flatten_by_month(
            year=year,
            month=month,
            location=location
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/health")
async def health_check():
    """
    健康檢查端點
    
    **返回**：
    ```json
    {
      "status": "healthy",
      "api": "ut",
      "supported_locations": ["P1", "P2", "P3", "P1+P2+P3"]
    }
    ```
    """
    return {
        "status": "healthy",
        "api": "ut",
        "supported_locations": ["P1", "P2", "P3", "P1+P2+P3"],
        "rate_limit": "30 requests/minute per IP"
    }
