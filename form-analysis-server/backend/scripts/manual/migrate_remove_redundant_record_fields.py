import asyncio
import logging
import sys
import os

# 添加路徑以確保可以導入 app 模組
sys.path.append(os.getcwd())

from sqlalchemy import text
from app.core.database import engine, init_db

# 設定日誌
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def migrate():
    """
    移除 Record 表中多餘的欄位
    這些欄位已經遷移到 p2_items 和 p3_items 子表中
    """
    # 初始化資料庫連線
    await init_db()
    
    columns_to_drop = [
        # P2 相關
        "sheet_width",
        "thickness1",
        "thickness2",
        "thickness3",
        "thickness4",
        "thickness5",
        "thickness6",
        "thickness7",
        "appearance",
        "rough_edge",
        "slitting_result",
        "winder_number",
        "slitting_machine_number",
        
        # P3 相關
        "p3_no",
        "specification",
        "bottom_tape_lot",
        "source_winder"
    ]

    logger.info("開始移除 Record 表多餘欄位...")
    
    # 重新導入 engine，因為 init_db 會更新全域變數
    from app.core.database import engine
    
    async with engine.begin() as conn:
        for column in columns_to_drop:
            try:
                logger.info(f"正在移除欄位: {column}")
                # 使用 DROP COLUMN IF EXISTS 避免錯誤
                await conn.execute(text(f"ALTER TABLE records DROP COLUMN IF EXISTS {column}"))
            except Exception as e:
                logger.warning(f"移除欄位 {column} 時發生錯誤: {e}")
                
    logger.info("遷移完成！所有多餘欄位已移除。")

if __name__ == "__main__":
    # 確保在正確的目錄下執行
    if not os.path.exists("app"):
        print("錯誤：請在 backend 目錄下執行此腳本")
        sys.exit(1)
        
    asyncio.run(migrate())
