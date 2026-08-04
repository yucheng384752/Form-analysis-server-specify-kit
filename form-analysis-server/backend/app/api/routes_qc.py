"""QC 日報表 API 路由"""

from __future__ import annotations

import csv
import io
from datetime import date, datetime
from typing import Any

import httpx
from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Request,
    Response,
    UploadFile,
)
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_tenant, get_db
from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.monitoring import report_user_action
from app.models.core.tenant import Tenant
from app.models.qc_record import QcRecord
from app.services.qc_import import parse_qc_csv, upsert_qc_records

router = APIRouter(prefix="/api/qc")
logger = get_logger(__name__)
settings = get_settings()


# --- Schemas ---

class QcRollItem(BaseModel):
    roll_no: int
    judgment: str | None
    thickness_H: int | None
    thickness_L: int | None


class QcRecordOut(BaseModel):
    id: str
    production_date: date
    machine_no: str
    source_file: str | None
    qc_A_H: float | None
    qc_A_L: float | None
    qc_B_H: float | None
    qc_B_L: float | None
    qc_E_prime_H: float | None
    qc_E_prime_L: float | None
    qc_10P0_H: float | None
    qc_10P0_L: float | None
    qc_bending: int | None
    qc_result: str | None
    ng_count: int
    bad_reason: str | None
    rolls_data: list[dict[str, Any]] | None


class QcQueryResponse(BaseModel):
    total: int
    records: list[QcRecordOut]


def _to_out(rec: QcRecord) -> QcRecordOut:
    return QcRecordOut(
        id=str(rec.id),
        production_date=rec.production_date,
        machine_no=rec.machine_no,
        source_file=rec.source_file,
        qc_A_H=rec.qc_A_H,
        qc_A_L=rec.qc_A_L,
        qc_B_H=rec.qc_B_H,
        qc_B_L=rec.qc_B_L,
        qc_E_prime_H=rec.qc_E_prime_H,
        qc_E_prime_L=rec.qc_E_prime_L,
        qc_10P0_H=rec.qc_10P0_H,
        qc_10P0_L=rec.qc_10P0_L,
        qc_bending=rec.qc_bending,
        qc_result=rec.qc_result,
        ng_count=rec.ng_count or 0,
        bad_reason=rec.bad_reason,
        rolls_data=rec.rolls_data,
    )


# --- Upload & Import ---

@router.post("/upload", summary="上傳 QC PDF 並寫入資料庫")
async def upload_qc_pdf(
    request: Request,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_tenant: Tenant = Depends(get_current_tenant),
):
    """接受 QC PDF → 送外部 PDF server 轉 CSV → 解析 → 寫入 qc_records"""
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="只接受 PDF 檔案")

    pdf_bytes = await file.read()
    if not pdf_bytes:
        raise HTTPException(status_code=400, detail="檔案內容為空")

    pdf_server_url = (getattr(settings, "pdf_server_url", None) or "").strip()
    if not pdf_server_url:
        raise HTTPException(status_code=503, detail="PDF_SERVER_URL 未設定")

    process_url = pdf_server_url.rstrip("/") + "/process"

    # 呼叫外部 PDF server
    try:
        async with httpx.AsyncClient(timeout=600) as client:
            resp = await client.post(
                process_url,
                files=[("files", (file.filename, pdf_bytes, "application/pdf"))],
                data={
                    "table": "QC",
                    "llm_model": "google/gemma-4-26b-a4b",
                    "llm_timeout": "300",
                },
            )
            resp.raise_for_status()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=502, detail=f"PDF server 錯誤: {e.response.status_code}")
    except httpx.RequestError as e:
        raise HTTPException(status_code=502, detail=f"PDF server 無法連線: {e}")

    # 解壓縮 ZIP → 取 CSV 文字
    import io as _io
    import zipfile

    content_type = (resp.headers.get("content-type") or "").lower()
    if "zip" in content_type or resp.content[:2] == b"PK":
        try:
            zf = zipfile.ZipFile(_io.BytesIO(resp.content))
            csv_text = None
            for info in zf.infolist():
                if info.filename.lower().endswith(".csv") and "error" not in info.filename.lower():
                    csv_text = zf.read(info).decode("utf-8-sig", errors="replace")
                    break
            if not csv_text:
                raise HTTPException(status_code=502, detail="PDF server 回傳 ZIP 中無有效 CSV")
        except zipfile.BadZipFile:
            raise HTTPException(status_code=502, detail="PDF server 回傳無效 ZIP")
    elif "json" in content_type:
        result = resp.json()
        csv_text = result.get("csv_text") or result.get("csv")
        if not csv_text:
            raise HTTPException(status_code=502, detail="PDF server 回傳 JSON 中無 csv_text")
    else:
        raise HTTPException(status_code=502, detail="PDF server 回傳未知格式")

    # 解析 CSV → 寫入 DB
    parsed = parse_qc_csv(csv_text, source_file=file.filename)
    if not parsed:
        raise HTTPException(status_code=422, detail="CSV 解析結果為空，請確認 PDF 格式")

    saved = await upsert_qc_records(db, current_tenant.id, parsed)

    report_user_action(request, "qc_upload", {"file": file.filename, "count": len(saved)})
    return {"message": f"成功匯入 {len(saved)} 筆 QC 記錄", "count": len(saved)}


# --- Query ---

@router.get("/records", response_model=QcQueryResponse, summary="查詢 QC 記錄")
async def query_qc_records(
    request: Request,
    date_from: date | None = None,
    date_to: date | None = None,
    machine_no: str | None = None,
    ng_only: bool = False,
    page: int = 1,
    page_size: int = 50,
    db: AsyncSession = Depends(get_db),
    current_tenant: Tenant = Depends(get_current_tenant),
):
    stmt = select(QcRecord).where(QcRecord.tenant_id == current_tenant.id)

    if date_from:
        stmt = stmt.where(QcRecord.production_date >= date_from)
    if date_to:
        stmt = stmt.where(QcRecord.production_date <= date_to)
    if machine_no:
        stmt = stmt.where(QcRecord.machine_no.ilike(f"%{machine_no}%"))
    if ng_only:
        stmt = stmt.where(QcRecord.ng_count > 0)

    from sqlalchemy import func as sqlfunc
    count_stmt = select(sqlfunc.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar() or 0

    stmt = (
        stmt.order_by(QcRecord.production_date.desc(), QcRecord.machine_no)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    records = list((await db.execute(stmt)).scalars().all())

    report_user_action(request, "qc_query", {"total": total})
    return QcQueryResponse(total=total, records=[_to_out(r) for r in records])


_QC_EXPORT_MAX_ROWS = 5000

# 生產捲數欄位固定為 1~9（見 qc_import.py 的 ROLL_COLS），逐卷展開成獨立欄位，
# 讓每一卷的判定/上下層厚度都能在 CSV/Excel 中個別篩選、排序、分析。
_QC_EXPORT_MAX_ROLLS = 9

_QC_EXPORT_BASE_COLUMNS = [
    "production_date",
    "machine_no",
    "mold_no",
    "source_file",
    "qc_A_H",
    "qc_A_L",
    "qc_B_H",
    "qc_B_L",
    "qc_E_prime_H",
    "qc_E_prime_L",
    "qc_10P0_H",
    "qc_10P0_L",
    "qc_bending",
    "qc_result",
    "ng_count",
    "bad_reason",
]

_QC_EXPORT_ROLL_COLUMNS = [
    f"roll{n}_{field}"
    for n in range(1, _QC_EXPORT_MAX_ROLLS + 1)
    for field in ("judgment", "thickness_H", "thickness_L")
]

_QC_EXPORT_COLUMNS = _QC_EXPORT_BASE_COLUMNS + _QC_EXPORT_ROLL_COLUMNS


@router.get("/records/export", summary="匯出 QC 記錄為 CSV")
async def export_qc_records_csv(
    request: Request,
    date_from: date | None = None,
    date_to: date | None = None,
    machine_no: str | None = None,
    ng_only: bool = False,
    db: AsyncSession = Depends(get_db),
    current_tenant: Tenant = Depends(get_current_tenant),
) -> Response:
    result = await query_qc_records(
        request=request,
        date_from=date_from,
        date_to=date_to,
        machine_no=machine_no,
        ng_only=ng_only,
        page=1,
        page_size=_QC_EXPORT_MAX_ROWS,
        db=db,
        current_tenant=current_tenant,
    )

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(_QC_EXPORT_COLUMNS)
    for rec in result.records:
        row = rec.model_dump()
        rolls_by_no = {
            r.get("roll_no"): r
            for r in (row.get("rolls_data") or [])
            if r.get("roll_no")
        }

        base_values = [
            row.get("production_date", ""),
            row.get("machine_no", ""),
            row.get("mold_no") or "",
            row.get("source_file") or "",
            row.get("qc_A_H", ""),
            row.get("qc_A_L", ""),
            row.get("qc_B_H", ""),
            row.get("qc_B_L", ""),
            row.get("qc_E_prime_H", ""),
            row.get("qc_E_prime_L", ""),
            row.get("qc_10P0_H", ""),
            row.get("qc_10P0_L", ""),
            row.get("qc_bending", ""),
            row.get("qc_result") or "",
            row.get("ng_count", 0),
            row.get("bad_reason") or "",
        ]

        roll_values: list[Any] = []
        for n in range(1, _QC_EXPORT_MAX_ROLLS + 1):
            roll = rolls_by_no.get(n)
            if roll is None:
                roll_values.extend(["", "", ""])
            else:
                roll_values.extend(
                    [
                        roll.get("judgment") or "",
                        roll.get("thickness_H", ""),
                        roll.get("thickness_L", ""),
                    ]
                )

        writer.writerow(base_values + roll_values)

    content = buffer.getvalue()
    buffer.close()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"qc_records_{timestamp}.csv"
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    if result.total > _QC_EXPORT_MAX_ROWS:
        headers["X-Export-Truncated"] = "true"

    return Response(
        content=content.encode("utf-8-sig"), media_type="text/csv", headers=headers
    )
