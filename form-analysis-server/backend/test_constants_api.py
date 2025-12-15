"""測試常數 API"""

import sys
from fastapi.testclient import TestClient

# 匯入主應用
from app.main import app

# 建立測試客戶端
client = TestClient(app)

print("=" * 60)
print("測試常數 API")
print("=" * 60)

# 測試 1: 取得材料清單
print("\n1. GET /api/constants/materials")
response = client.get("/api/constants/materials")
print(f"   狀態碼: {response.status_code}")
data = response.json()
print(f"   回應: {data}")
assert response.status_code == 200
assert data == ["H2", "H5", "H8"]
print("   ✓ 正確")

# 測試 2: 取得分條機清單
print("\n2. GET /api/constants/slitting-machines")
response = client.get("/api/constants/slitting-machines")
print(f"   狀態碼: {response.status_code}")
data = response.json()
print(f"   回應: {data}")
assert response.status_code == 200
assert len(data) == 2
assert data[0]["number"] == 1
assert data[0]["display_name"] == "分1Points 1"
assert data[1]["number"] == 2
assert data[1]["display_name"] == "分2Points 2"
print("   ✓ 正確")

# 測試 3: 取得單一分條機
print("\n3. GET /api/constants/slitting-machines/1")
response = client.get("/api/constants/slitting-machines/1")
print(f"   狀態碼: {response.status_code}")
data = response.json()
print(f"   回應: {data}")
assert response.status_code == 200
assert data["number"] == 1
assert data["display_name"] == "分1Points 1"
print("   ✓ 正確")

# 測試 4: 不存在的分條機
print("\n4. GET /api/constants/slitting-machines/999")
response = client.get("/api/constants/slitting-machines/999")
print(f"   狀態碼: {response.status_code}")
assert response.status_code == 404
data = response.json()
print(f"   錯誤訊息: {data['detail']}")
print("   ✓ 正確回傳 404")

# 測試 5: 取得所有常數
print("\n5. GET /api/constants/all")
response = client.get("/api/constants/all")
print(f"   狀態碼: {response.status_code}")
data = response.json()
print(f"   材料: {data['materials']}")
print(f"   分條機: {data['slitting_machines']}")
assert response.status_code == 200
assert "materials" in data
assert "slitting_machines" in data
assert data["materials"] == ["H2", "H5", "H8"]
assert len(data["slitting_machines"]) == 2
print("   ✓ 正確")

print("\n" + "=" * 60)
print("🎉 常數 API 測試全部通過！")
print("=" * 60)
