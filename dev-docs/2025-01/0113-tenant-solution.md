# Tenant 配置問題解決方案
*日期: 2026-01-13*
*問題: X-Tenant-Id header is required*

## 問題分析

### 1. 錯誤訊息
```
"detail": "X-Tenant-Id header is required (Multiple tenants exist and no unique default)"
```

### 2. 根本原因
資料庫中沒有任何 tenant 記錄，導致系統無法自動解析預設 tenant。

### 3. Tenant 自動解析邏輯
根據 [app/api/deps.py](../form-analysis-server/backend/app/api/deps.py) 的 `get_current_tenant()` 函數：

**不帶 X-Tenant-Id Header 時的解析邏輯**:
1. **僅 1 個 tenant**: 自動使用該 tenant ✓
2. **多個 tenant + 唯一 is_default=true**: 自動使用預設 tenant ✓  
3. **0 個 tenant** 或 **多個 tenant 無預設**: 拋出 422 錯誤 ✗

## 解決方案對比

### 方案 1: 建立預設 Tenant（✓ 建議採用）

**優點**:
- 保留 multi-tenant 架構彈性
- 未來可擴充支援多場域
- 符合系統原始設計

**執行步驟**:

1. **使用 seed 腳本建立 tenant**:
   ```bash
   # 在 Docker 環境中
   docker exec form_analysis_api python seed_tenant.py
   
   # 或在本地環境
   cd form-analysis-server/backend
   python seed_tenant.py
   ```

2. **驗證 tenant 建立成功**:
   ```bash
   docker exec form_analysis_db psql -U app -d form_analysis_db -c "SELECT id, name, code, is_default FROM tenants;"
   ```
   
   預期輸出:
   ```
                      id                   |      name       |  code   | is_default 
   --------------------------------------+-----------------+---------+------------
    ee5e3236-3c60-4e49-ad7c-5b36a12e6d8c | Default Tenant  | DEFAULT | f
   ```

3. **測試 API（不帶 Header）**:
   ```powershell
   Invoke-RestMethod -Uri "http://localhost:18002/api/v2/query/records/advanced?lot_no=test"
   ```
   
   ✓ 應該返回正常回應（不再有 422 錯誤）

**結果**: ✅ **已執行完成** - Default Tenant 已建立 (ID: ee5e3236-3c60-4e49-ad7c-5b36a12e6d8c)

---

### 方案 2: 簡化 Tenant 檢查（適用於單場域專案）

**適用情境**: 確定專案永遠只有單一場域使用

**優點**:
- 簡化 API 呼叫（不需要 header）
- 減少複雜度

**缺點**:
- 失去 multi-tenant 彈性
- 需要修改程式碼

**實作方式** (僅供參考，目前不建議執行):

<details>
<summary>點擊展開程式碼修改</summary>

修改 `app/api/deps.py`:

```python
async def get_current_tenant(
    x_tenant_id: Optional[str] = Header(None, alias="X-Tenant-Id"),
    db: AsyncSession = Depends(get_db)
) -> Tenant:
    """簡化版: 永遠使用第一個 tenant，如果沒有則建立"""
    
    # 1. 如果有 Header，驗證並使用
    if x_tenant_id:
        try:
            tenant_uuid = UUID(x_tenant_id)
            result = await db.execute(select(Tenant).where(Tenant.id == tenant_uuid))
            tenant = result.scalar_one_or_none()
            if not tenant:
                raise HTTPException(status_code=404, detail="Tenant not found")
            return tenant
        except ValueError:
            raise HTTPException(status_code=422, detail="Invalid tenant ID format")
    
    # 2. 沒有 Header: 自動建立或使用第一個 tenant
    result = await db.execute(select(Tenant).limit(1))
    tenant = result.scalar_one_or_none()
    
    if not tenant:
        # 沒有任何 tenant，自動建立預設 tenant
        tenant = Tenant(
            name="Default Tenant",
            code="DEFAULT",
            is_default=True,
            is_active=True
        )
        db.add(tenant)
        await db.flush()
        await db.refresh(tenant)
    
    return tenant
```

**影響範圍**: 所有使用 `Depends(get_current_tenant)` 的 API 端點

</details>

---

## 建議採用方案

✅ **方案 1** - 已經執行完成

**理由**:
1. 專案設計已考慮 multi-tenant 架構
2. 前端已實作 tenant 選擇器邏輯（當 tenants > 1 時顯示）
3. 保留未來擴充彈性（如需支援多工廠/多場域）
4. 只需執行一次 seed 腳本，無需修改程式碼

---

## 驗證檢查清單

- [x] 資料庫中有至少 1 個 tenant
- [x] API 可以不帶 header 正常查詢
- [x] 測試腳本可以執行（雖然沒有測試資料）
- [ ] 前端可以正常查詢並顯示資料
- [ ] 匯入資料時 tenant 關聯正確

---

## 後續步驟

### 1. 匯入測試資料
確保匯入的資料關聯到正確的 tenant：

```bash
# 檢查匯入腳本是否正確處理 tenant
grep -r "tenant_id" form-analysis-server/backend/app/api/routes_import*.py
```

### 2. 前端 Tenant 選擇器
目前前端會自動獲取第一個 tenant：

```typescript
// QueryPage.tsx
React.useEffect(() => {
  fetch('/api/tenants')
    .then(res => res.json())
    .then(data => {
      if (data && data.length > 0) setTenantId(data[0].id);
    })
}, []);
```

驗證前端是否正確帶入 `X-Tenant-Id` header。

### 3. 長期建議

如果確定永遠只有單一場域，可以考慮：

**選項 A**: 保持現狀（推薦）
- 優點: 架構完整，未來可擴充
- 缺點: 多一層抽象（但影響很小）

**選項 B**: 移除 Tenant 機制
- 需要大量重構（修改所有 model、API、前端）
- 風險高，不建議

**選項 C**: 設定預設 tenant 為 is_default=true
```sql
UPDATE tenants SET is_default = true WHERE code = 'DEFAULT';
```

---

## 相關檔案

- Tenant 模型: [app/models/core/tenant.py](../form-analysis-server/backend/app/models/core/tenant.py)
- Dependency: [app/api/deps.py](../form-analysis-server/backend/app/api/deps.py)
- Seed 腳本: [seed_tenant.py](../form-analysis-server/backend/seed_tenant.py)
- 測試案例: [tests/api/test_tenant_dependency.py](../form-analysis-server/backend/tests/api/test_tenant_dependency.py)

---

## 總結

✅ **問題已解決** - 透過建立預設 tenant
- 執行 `docker exec form_analysis_api python seed_tenant.py`
- Default Tenant 已建立成功
- API 現在可以不帶 header 正常查詢
- 保留 multi-tenant 架構彈性

**下一步**: 匯入測試資料並驗證 P2 顯示修正是否正常運作
