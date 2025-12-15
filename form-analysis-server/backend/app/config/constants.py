"""
系統常數配置

此檔案定義系統中使用的所有常數，包括：
- 有效的材料代碼清單
- 有效的分條機編號清單
- 分條機顯示名稱映射

## 維護說明

此配置由工程師維護，修改後需要重啟服務。

### 如何新增材料代號

1. 在 VALID_MATERIALS 清單中新增材料代碼（大寫）
   範例：VALID_MATERIALS = ["H2", "H5", "H8", "H10"]  # 新增 H10

2. 儲存檔案

3. 重啟後端服務
   ```bash
   # 停止服務後重新啟動
   python -m uvicorn app.main:app --reload --port 18002
   ```

4. 測試驗證：上傳包含新材料代碼的 CSV，確認不會報錯

### 如何新增分條機

1. 在 VALID_SLITTING_MACHINES 清單中新增機台編號
   範例：VALID_SLITTING_MACHINES = [1, 2, 3]  # 新增分條機 3

2. 在 SLITTING_MACHINE_DISPLAY_NAMES 中新增對應的顯示名稱
   範例：
   ```python
   SLITTING_MACHINE_DISPLAY_NAMES = {
       1: "分1Points 1",
       2: "分2Points 2",
       3: "分3Points 3",  # 新增顯示名稱
   }
   ```

3. 儲存檔案

4. 重啟後端服務

5. 測試驗證：
   - 呼叫 GET /api/constants/slitting-machines 確認新機台出現
   - 上傳包含新機台編號的 P2 CSV，確認不會報錯

### 注意事項

- 材料代碼建議使用大寫（系統會自動標準化）
- 分條機編號必須是整數
- 修改此檔案後務必重啟服務才會生效
- 修改前建議先備份此檔案
- 不要刪除正在使用的材料或機台（會導致歷史資料查詢錯誤）
"""

# ==================== 材料清單 ====================
# 有效的材料代碼，用於驗證 P1 和 P2 的 Material 欄位
VALID_MATERIALS = [
    "H2",
    "H5",
    "H8",
]

# ==================== 分條機清單 ====================
# 有效的分條機編號，用於驗證 P2 的 Slitting machine 欄位
VALID_SLITTING_MACHINES = [
    1,  # 分條機 1
    2,  # 分條機 2
]

# ==================== 分條機顯示名稱映射 ====================
# 用於 API 回應時提供使用者友善的顯示名稱
# 資料庫只儲存數字，顯示時透過此映射轉換
SLITTING_MACHINE_DISPLAY_NAMES = {
    1: "分1Points 1",
    2: "分2Points 2",
}


# ==================== 輔助函數 ====================

def get_material_list() -> list[str]:
    """
    取得有效的材料清單
    
    Returns:
        list[str]: 材料代碼清單
    """
    return VALID_MATERIALS.copy()


def get_slitting_machine_list() -> list[int]:
    """
    取得有效的分條機編號清單
    
    Returns:
        list[int]: 分條機編號清單
    """
    return VALID_SLITTING_MACHINES.copy()


def get_slitting_machine_display_name(machine_number: int) -> str:
    """
    取得分條機的顯示名稱
    
    Args:
        machine_number: 分條機編號
        
    Returns:
        str: 顯示名稱，如果找不到則返回預設格式
    """
    return SLITTING_MACHINE_DISPLAY_NAMES.get(
        machine_number,
        f"分條機 {machine_number}"
    )


def get_slitting_machines_with_display_names() -> list[dict]:
    """
    取得分條機清單（包含顯示名稱）
    
    Returns:
        list[dict]: 包含 number 和 display_name 的字典清單
    """
    return [
        {
            "number": num,
            "display_name": get_slitting_machine_display_name(num)
        }
        for num in VALID_SLITTING_MACHINES
    ]
