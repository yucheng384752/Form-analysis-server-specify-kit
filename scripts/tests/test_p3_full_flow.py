#!/usr/bin/env python3
"""測試 P3 檔案完整流程（v2 import jobs：上傳→poll→commit→v2 query）"""

import json
import os
import time

import requests


BASE_URL = os.environ.get("BASE_URL", "http://localhost:18002")
TENANT_ID = os.environ.get("TENANT_ID", "")


def _get_tenant_id() -> str:
    if TENANT_ID:
        return TENANT_ID
    resp = requests.get(f"{BASE_URL}/api/tenants", timeout=10)
    resp.raise_for_status()
    items = resp.json() or []
    if not items:
        raise RuntimeError("No tenants found; create a tenant first")
    return items[0].get("tenant_id") or items[0].get("id")


def _poll_job_ready(job_id: str, tenant_id: str, timeout_s: int = 60) -> str:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        resp = requests.get(
            f"{BASE_URL}/api/v2/import/jobs/{job_id}",
            headers={"X-Tenant-Id": tenant_id},
            timeout=10,
        )
        resp.raise_for_status()
        status = (resp.json() or {}).get("status")
        if status in {"READY", "FAILED", "COMPLETED", "CANCELLED"}:
            return status
        time.sleep(1)
    return "TIMEOUT"


def test_full_flow():
    file_path = r"C:\Users\yucheng\Desktop\侑特資料\新侑特資料\P3_0902_P24 copy.csv"
    tenant_id = _get_tenant_id()

    print("=" * 80)
    print("步驟 1: 建立 v2 import job（P3）")
    print("=" * 80)

    with open(file_path, "rb") as f:
        files = [("files", ("P3_0902_P24.csv", f, "text/csv"))]
        data = {"table_code": "P3", "allow_duplicate": "false"}
        resp = requests.post(
            f"{BASE_URL}/api/v2/import/jobs",
            headers={"X-Tenant-Id": tenant_id},
            files=files,
            data=data,
            timeout=30,
        )

    resp.raise_for_status()
    job = resp.json()
    job_id = job.get("id")
    print(json.dumps(job, indent=2, ensure_ascii=False))

    if not job_id:
        raise RuntimeError("Create job succeeded but missing job id")

    print("\n" + "=" * 80)
    print("步驟 2: poll job 狀態")
    print("=" * 80)
    status = _poll_job_ready(job_id, tenant_id, timeout_s=90)
    print(f"job status: {status}")

    print("\n" + "=" * 80)
    print("步驟 3: commit")
    print("=" * 80)
    if status != "READY":
        print("job 未 READY，跳過 commit；可改用 /errors 查看原因")
    else:
        resp = requests.post(
            f"{BASE_URL}/api/v2/import/jobs/{job_id}/commit",
            headers={"X-Tenant-Id": tenant_id},
            timeout=30,
        )
        resp.raise_for_status()
        print(json.dumps(resp.json(), indent=2, ensure_ascii=False))

    print("\n" + "=" * 80)
    print("步驟 4: v2 query 驗證（lot_no=2507173_02）")
    print("=" * 80)
    resp = requests.get(
        f"{BASE_URL}/api/v2/query/records",
        headers={"X-Tenant-Id": tenant_id},
        params={"lot_no": "2507173_02", "page": 1, "page_size": 50},
        timeout=30,
    )
    resp.raise_for_status()
    body = resp.json() or {}
    records = body.get("records") or []
    print(f"records: {len(records)}")
    for r in records[:5]:
        if not isinstance(r, dict):
            continue
        print(f"- {r.get('data_type')} lot={r.get('lot_no')} product_id={r.get('product_id')}")


if __name__ == "__main__":
    test_full_flow()
