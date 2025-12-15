"""
常數查詢 API 路由

提供系統常數的查詢接口，用於前端下拉選單和驗證
"""

from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any

from app.config.constants import (
    get_material_list,
    get_slitting_machine_list,
    get_slitting_machines_with_display_names,
    get_slitting_machine_display_name,
)

router = APIRouter(prefix="/api/constants", tags=["constants"])


@router.get("/materials", response_model=List[str])
async def get_materials():
    """
    取得有效的材料代碼清單
    
    Returns:
        材料代碼清單，如 ["H2", "H5", "H8"]
    
    Example:
        GET /api/constants/materials
        
        Response:
        [
            "H2",
            "H5",
            "H8"
        ]
    """
    return get_material_list()


@router.get("/slitting-machines", response_model=List[Dict[str, Any]])
async def get_slitting_machines():
    """
    取得分條機清單（包含顯示名稱）
    
    Returns:
        分條機清單，包含編號和顯示名稱
    
    Example:
        GET /api/constants/slitting-machines
        
        Response:
        [
            {
                "number": 1,
                "display_name": "分條1"
            },
            {
                "number": 2,
                "display_name": "分條2"
            }
        ]
    """
    return get_slitting_machines_with_display_names()


@router.get("/slitting-machines/{machine_number}", response_model=Dict[str, Any])
async def get_slitting_machine(machine_number: int):
    """
    取得單一分條機資訊
    
    Args:
        machine_number: 分條機編號
    
    Returns:
        分條機資訊，包含編號和顯示名稱
    
    Raises:
        HTTPException: 如果分條機編號不存在
    
    Example:
        GET /api/constants/slitting-machines/1
        
        Response:
        {
            "number": 1,
            "display_name": "分條1"
        }
    """
    # 檢查機台編號是否有效
    valid_machines = get_slitting_machine_list()
    if machine_number not in valid_machines:
        raise HTTPException(
            status_code=404,
            detail=f"分條機編號 {machine_number} 不存在"
        )
    
    display_name = get_slitting_machine_display_name(machine_number)
    
    return {
        "number": machine_number,
        "display_name": display_name
    }


@router.get("/all", response_model=Dict[str, Any])
async def get_all_constants():
    """
    一次取得所有常數（減少 API 呼叫次數）
    
    Returns:
        包含所有常數的字典
    
    Example:
        GET /api/constants/all
        
        Response:
        {
            "materials": ["H2", "H5", "H8"],
            "slitting_machines": [
                {"number": 1, "display_name": "分條1"},
                {"number": 2, "display_name": "分條2"}
            ]
        }
    """
    return {
        "materials": get_material_list(),
        "slitting_machines": get_slitting_machines_with_display_names(),
    }
