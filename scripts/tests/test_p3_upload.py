"""測試 P3 檔案上傳/驗證（v2 import job create，不 commit）"""

import json
import os

import requests


BASE_URL = os.environ.get("BASE_URL", "http://localhost:18002")
TENANT_ID = os.environ.get("TENANT_ID", "")
TEST_FILE = os.environ.get(
    "TEST_FILE",
    r"C:\Users\yucheng\Desktop\侑特資料\新侑特資料\P3_0902_P24 copy.csv",
)


def _get_tenant_id() -> str:
    if TENANT_ID:
        return TENANT_ID
    resp = requests.get(f"{BASE_URL}/api/tenants", timeout=10)
    resp.raise_for_status()
    items = resp.json() or []
    if not items:
        raise RuntimeError("No tenants found; create a tenant first")
    return items[0].get("tenant_id") or items[0].get("id")


def test_upload_p3():
    print("=" * 80)
    print("測試 P3 v2 import job create")
    print("=" * 80)

    if not os.path.exists(TEST_FILE):
        raise FileNotFoundError(f"檔案不存在: {TEST_FILE}")

    tenant_id = _get_tenant_id()

    print(f"BASE_URL: {BASE_URL}")
    print(f"TENANT_ID: {tenant_id}")
    print(f"TEST_FILE: {TEST_FILE}")

    with open(TEST_FILE, "rb") as f:
        files = [("files", (os.path.basename(TEST_FILE), f, "text/csv"))]
        data = {"table_code": "P3", "allow_duplicate": "false"}
        resp = requests.post(
            f"{BASE_URL}/api/v2/import/jobs",
            headers={"X-Tenant-Id": tenant_id},
            files=files,
            data=data,
            timeout=60,
        )

    print(f"HTTP {resp.status_code}")
    resp.raise_for_status()
    print(json.dumps(resp.json(), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    test_upload_p3()
