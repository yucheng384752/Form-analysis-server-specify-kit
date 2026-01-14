import csv
import re
import uuid
from pathlib import Path
from typing import List, Dict, Any
import logging

from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.import_job import ImportJob, ImportFile, StagingRow, ImportJobStatus
from app.models.core.schema_registry import TableRegistry
from app.utils.normalization import normalize_lot_no
from app.services.csv_field_mapper import CSVFieldMapper, csv_field_mapper

logger = logging.getLogger(__name__)

class ImportService:
    def __init__(self, db: AsyncSession):
        self.db = db

    def _normalize_p3_lot_no_raw(self, val: str) -> str:
        """P3 專用 lot_no 正規化（僅取前兩段），例如：2507173_02_18 -> 2507173_02"""
        s = str(val or "").strip()
        if not s:
            return s
        parts = re.findall(r"\d+", s)
        if len(parts) >= 2 and len(parts[0]) >= 6 and len(parts[1]) <= 2:
            return f"{parts[0]}_{parts[1].zfill(2)}"
        return s

    async def parse_job(self, job_id: uuid.UUID) -> ImportJob:
        """
        Parse all files in the import job and populate staging_rows.
        """
        # 1. Fetch Job with Files
        stmt = select(ImportJob).options(selectinload(ImportJob.files)).where(ImportJob.id == job_id)
        result = await self.db.execute(stmt)
        job = result.scalar_one_or_none()

        if not job:
            raise ValueError(f"Import job {job_id} not found")

        # 2. Update Status to PARSING
        job.status = ImportJobStatus.PARSING
        await self.db.commit()

        total_rows_job = 0
        
        try:
            for file_record in job.files:
                file_path = Path(file_record.storage_path)
                if not file_path.exists():
                    logger.error(f"File not found: {file_path}")
                    continue

                # Parse CSV
                rows_to_insert = []
                row_count_file = 0
                
                # TODO: Handle encoding detection if needed. Defaulting to utf-8-sig for now.
                try:
                    with open(file_path, mode='r', encoding='utf-8-sig', newline='') as csvfile:
                        reader = csv.DictReader(csvfile)
                        
                        # Normalize headers? 
                        # For now, we assume headers match the keys we want or we store raw dict.
                        
                        for i, row in enumerate(reader, start=1):
                            # Basic cleanup: strip whitespace from keys and values
                            clean_row = {k.strip(): v.strip() for k, v in row.items() if k}
                            
                            staging_row = StagingRow(
                                id=uuid.uuid4(),
                                job_id=job.id,
                                file_id=file_record.id,
                                row_index=i,
                                parsed_json=clean_row,
                                is_valid=True, # Assume valid until validation step
                                errors_json=[]
                            )
                            rows_to_insert.append(staging_row)
                            row_count_file += 1
                            
                            # Batch insert every 1000 rows to avoid memory issues
                            if len(rows_to_insert) >= 1000:
                                self.db.add_all(rows_to_insert)
                                await self.db.flush() # Flush to send to DB but not commit yet
                                rows_to_insert = []

                    # Insert remaining rows
                    if rows_to_insert:
                        self.db.add_all(rows_to_insert)
                        await self.db.flush()

                    # Update file row count
                    file_record.row_count = row_count_file
                    total_rows_job += row_count_file
                    
                except UnicodeDecodeError:
                    # Fallback to cp950 (Big5) commonly used in Taiwan/Windows
                     with open(file_path, mode='r', encoding='cp950', newline='') as csvfile:
                        reader = csv.DictReader(csvfile)
                        for i, row in enumerate(reader, start=1):
                            clean_row = {k.strip(): v.strip() for k, v in row.items() if k}
                            staging_row = StagingRow(
                                id=uuid.uuid4(),
                                job_id=job.id,
                                file_id=file_record.id,
                                row_index=i,
                                parsed_json=clean_row,
                                is_valid=True,
                                errors_json=[]
                            )
                            rows_to_insert.append(staging_row)
                            row_count_file += 1
                            if len(rows_to_insert) >= 1000:
                                self.db.add_all(rows_to_insert)
                                await self.db.flush()
                                rows_to_insert = []
                        if rows_to_insert:
                            self.db.add_all(rows_to_insert)
                            await self.db.flush()
                            
                     file_record.row_count = row_count_file
                     total_rows_job += row_count_file

            # 3. Update Job Status to VALIDATING (or READY if we skip validation for now)
            # The plan implies validation is next.
            job.total_rows = total_rows_job
            job.status = ImportJobStatus.VALIDATING 
            
            await self.db.commit()
            return job

        except Exception as e:
            logger.exception(f"Error parsing job {job_id}: {e}")
            job.status = ImportJobStatus.FAILED
            job.error_summary = {"error": str(e)}
            await self.db.commit()
            raise e

    async def validate_job(self, job_id: uuid.UUID) -> ImportJob:
        """
        Validate staging rows against schema.
        """
        # 1. Fetch Job with Table info and Files
        stmt = select(ImportJob).options(selectinload(ImportJob.files)).where(ImportJob.id == job_id)
        result = await self.db.execute(stmt)
        job = result.scalar_one_or_none()

        if not job:
            raise ValueError(f"Import job {job_id} not found")
            
        # Fetch table code to determine validation rules
        table_stmt = select(TableRegistry).where(TableRegistry.id == job.table_id)
        table_result = await self.db.execute(table_stmt)
        table = table_result.scalar_one_or_none()
        
        if not table:
             raise ValueError(f"Table for job {job_id} not found")

        # Map file_id to filename
        file_map = {f.id: f.filename for f in job.files}

        # 2. Define Validation Rules
        # Import V2 目前採用「一個檔案 → 1 筆 records + N 筆 items」的混合架構。
        # 因此 staging_rows 不應以「同一檔案內 key 重複」判錯（會把多列 items 全打成 invalid）。
        # 這裡僅做非常保守的欄位檢查；真正的欄位映射/解析放在 commit_job。
        required_fields: List[str] = []
        numeric_fields: List[str] = []

        if table.table_code == "P1":
            # Minimal validation expected by tests/api/test_import_v2.py
            required_fields = ["Line Speed(M/min)", "Screw Pressure(psi)"]
            numeric_fields = ["Line Speed(M/min)", "Screw Pressure(psi)"]

        # 3. Iterate and Validate Staging Rows
        offset = 0
        limit = 1000
        error_count_job = 0
        
        while True:
            rows_stmt = select(StagingRow).where(StagingRow.job_id == job_id).offset(offset).limit(limit)
            rows_result = await self.db.execute(rows_stmt)
            rows = rows_result.scalars().all()
            
            if not rows:
                break
                
            for row in rows:
                errors = []
                data = row.parsed_json
                filename = file_map.get(row.file_id, "")
                
                # Check required fields
                for field in required_fields:
                    if field not in data or not data[field]:
                        errors.append({"field": field, "message": "Missing required field"})
                
                # Check numeric fields
                for field in numeric_fields:
                    if field in data and data[field]:
                        try:
                            float(data[field])
                        except ValueError:
                            errors.append({"field": field, "message": "Value must be numeric"})
                
                if errors:
                    row.is_valid = False
                    row.errors_json = errors
                    error_count_job += 1
                else:
                    row.is_valid = True
                    row.errors_json = []
            
            # Flush changes for this chunk
            await self.db.flush()
            offset += limit

        # 4. Update Job Status
        job.error_count = error_count_job
        # If validation is done, we mark it as READY (for review/commit)
        job.status = ImportJobStatus.READY
        await self.db.commit()
        return job

    async def commit_job(self, job_id: uuid.UUID) -> ImportJob:
        """
        Commit valid staging rows to target tables.
        """
        logger.info(f"Starting commit_job for {job_id}")
        # 1. Fetch Job
        stmt = select(ImportJob).options(selectinload(ImportJob.files)).where(ImportJob.id == job_id)
        result = await self.db.execute(stmt)
        job = result.scalar_one_or_none()

        if not job:
            logger.error(f"Import job {job_id} not found")
            raise ValueError(f"Import job {job_id} not found")
            
        if job.status != ImportJobStatus.READY and job.status != ImportJobStatus.COMMITTING:
             logger.error(f"Job {job_id} is not ready to commit (status: {job.status})")
             raise ValueError(f"Job {job_id} is not ready to commit (status: {job.status})")

        # Update status
        job.status = ImportJobStatus.COMMITTING
        await self.db.commit()

        # Get Table Code
        table_stmt = select(TableRegistry).where(TableRegistry.id == job.table_id)
        table_result = await self.db.execute(table_stmt)
        table = table_result.scalar_one_or_none()
        
        if not table:
             logger.error(f"Table for job {job_id} not found")
             raise ValueError(f"Table for job {job_id} not found")

        logger.info(f"Commit job {job_id}: Table code {table.table_code}, Files: {len(job.files)}")

        try:
            # Process by file
            for file_record in job.files:
                logger.info(f"Processing file {file_record.filename} (ID: {file_record.id})")
                # Get staging rows
                rows_stmt = select(StagingRow).where(
                    StagingRow.file_id == file_record.id,
                    StagingRow.is_valid == True
                ).order_by(StagingRow.row_index)
                
                rows_result = await self.db.execute(rows_stmt)
                rows = rows_result.scalars().all()
                
                if not rows:
                    continue
                    
                # Extract Lot No
                lot_no_raw = self._extract_lot_no(file_record.filename)
                lot_no_norm = normalize_lot_no(lot_no_raw)
                
                # Prepare Data
                row_data = [r.parsed_json for r in rows]
                
                if table.table_code == "P1":
                    from app.models.p1_record import P1Record
                    
                    # Check existence
                    existing_stmt = select(P1Record).where(
                        P1Record.tenant_id == job.tenant_id,
                        P1Record.lot_no_norm == lot_no_norm
                    )
                    existing_result = await self.db.execute(existing_stmt)
                    existing_record = existing_result.scalar_one_or_none()
                    
                    if existing_record:
                        # Update
                        existing_record.extras = {"rows": row_data}
                        existing_record.updated_at = func.now()
                    else:
                        # Create
                        new_record = P1Record(
                            id=uuid.uuid4(),
                            tenant_id=job.tenant_id,
                            lot_no_raw=lot_no_raw,
                            lot_no_norm=lot_no_norm,
                            schema_version_id=job.schema_version_id,
                            extras={"rows": row_data}
                        )
                        self.db.add(new_record)
                
                elif table.table_code == "P2":
                    from app.models.p2_record import P2Record
                    from app.models.p2_item_v2 import P2ItemV2
                    
                    # P2 匯入：通常每個檔案對應 1 個 winder（例如 P2_Lot123_05.csv）。
                    # 因此以 (tenant_id, lot_no_norm, winder_number) 為 key 建立/更新 P2Record。
                    winder_num_for_file = self._extract_p2_info(file_record.filename, row_data)

                    existing_stmt = select(P2Record).where(
                        P2Record.tenant_id == job.tenant_id,
                        P2Record.lot_no_norm == lot_no_norm,
                        P2Record.winder_number == winder_num_for_file,
                    )
                    existing_result = await self.db.execute(existing_stmt)
                    p2_record = existing_result.scalar_one_or_none()

                    if not p2_record:
                        p2_record = P2Record(
                            id=uuid.uuid4(),
                            tenant_id=job.tenant_id,
                            lot_no_raw=lot_no_raw,
                            lot_no_norm=lot_no_norm,
                            schema_version_id=job.schema_version_id,
                            winder_number=winder_num_for_file,
                            extras={"rows": row_data},
                        )
                        self.db.add(p2_record)
                        await self.db.flush()  # Get ID
                    else:
                        p2_record.extras = {"rows": row_data}
                        p2_record.updated_at = func.now()
                    
                    # Delete existing items for this record (if re-importing)
                    await self.db.execute(
                        delete(P2ItemV2).where(P2ItemV2.p2_record_id == p2_record.id)
                    )
                    # Ensure DELETE is flushed before INSERT to avoid unique constraint conflicts
                    await self.db.flush()
                    
                    # Create one P2ItemV2 for this file's winder.
                    # 若內容缺少 winder 欄位，使用檔名推導的 winder；避免因缺欄位而整筆跳過。
                    if row_data:
                        row = row_data[0]
                        winder_num = None
                        for field in CSVFieldMapper.WINDER_NUMBER_FIELD_NAMES:
                            if field in row and row[field]:
                                try:
                                    winder_num = int(float(row[field]))
                                    break
                                except (ValueError, TypeError):
                                    pass
                        if winder_num is None:
                            winder_num = winder_num_for_file

                        if winder_num != winder_num_for_file:
                            logger.warning(
                                f"P2 file winder mismatch (filename={winder_num_for_file}, row={winder_num}); using filename winder"
                            )
                            winder_num = winder_num_for_file

                        p2_item = P2ItemV2(
                            id=uuid.uuid4(),
                            p2_record_id=p2_record.id,
                            tenant_id=job.tenant_id,
                            winder_number=winder_num,
                            row_data=row,
                        )

                        for field in [
                            'sheet_width',
                            'thickness1',
                            'thickness2',
                            'thickness3',
                            'thickness4',
                            'thickness5',
                            'thickness6',
                            'thickness7',
                            'appearance',
                            'rough_edge',
                            'slitting_result',
                        ]:
                            if field in row and row[field]:
                                try:
                                    setattr(p2_item, field, float(row[field]))
                                except (ValueError, TypeError):
                                    pass

                        self.db.add(p2_item)

                elif table.table_code == "P3":
                    from app.models.p3_record import P3Record
                    from app.models.p3_item_v2 import P3ItemV2
                    
                    # P3 改用混合架構: 依 lot_no 分組 → 每個 lot 1筆 p3_records + N筆 p3_items_v2
                    # 注意：你的檔名 (例如 P3_0902_P24 copy.csv) 不包含 lot_no，不能用檔名推 lot。

                    p3_info = self._extract_p3_info(file_record.filename, row_data)

                    # Group rows by lot_no_norm extracted from row content
                    groups: Dict[int, Dict[str, Any]] = {}
                    for row in row_data:
                        lot_from_row = None
                        for field in CSVFieldMapper.LOT_NO_FIELD_NAMES:
                            if field in row and row[field]:
                                lot_from_row = str(row[field]).strip()
                                break
                        if not lot_from_row:
                            # Fallback: use filename-derived lot (may be wrong but prevents crash)
                            lot_from_row = lot_no_raw

                        # P3 lot_no 可能帶尾碼（如 _18），分組與 records 關聯只需要前兩段
                        lot_from_row = self._normalize_p3_lot_no_raw(lot_from_row)

                        lot_norm_row = normalize_lot_no(lot_from_row)
                        if lot_norm_row not in groups:
                            groups[lot_norm_row] = {"lot_no_raw": lot_from_row, "rows": []}
                        groups[lot_norm_row]["rows"].append(row)

                    for lot_norm_row, payload in groups.items():
                        group_lot_raw = payload["lot_no_raw"]
                        group_rows = payload["rows"]

                        # Check existence of P3Record for this lot
                        existing_stmt = select(P3Record).where(
                            P3Record.tenant_id == job.tenant_id,
                            P3Record.lot_no_norm == lot_norm_row,
                            P3Record.machine_no == p3_info["machine_no"],
                            P3Record.mold_no == p3_info["mold_no"],
                            P3Record.production_date_yyyymmdd == p3_info["production_date_yyyymmdd"]
                        )
                        existing_result = await self.db.execute(existing_stmt)
                        p3_record = existing_result.scalar_one_or_none()

                        # Generate product_id for P3Record
                        production_date_yyyymmdd = int(p3_info.get("production_date_yyyymmdd") or 0)
                        date_str = f"{production_date_yyyymmdd:08d}" if production_date_yyyymmdd else ""
                        lot_part_raw = None
                        if group_rows:
                            for field in CSVFieldMapper.LOT_FIELD_NAMES:
                                if field in group_rows[0] and group_rows[0][field]:
                                    lot_part_raw = group_rows[0][field]
                                    break
                        lot_part: int
                        try:
                            lot_part = int(float(lot_part_raw)) if lot_part_raw is not None else 0
                        except (ValueError, TypeError):
                            lot_part = 0

                        # product_id 格式：YYYYMMDD-machine-mold-lot
                        # 注意：mold_no 可能含 '-'（例如 238-2），解析需使用 product_id_generator 的智慧解析。
                        product_id = f"{date_str}-{p3_info.get('machine_no')}-{p3_info.get('mold_no')}-{lot_part}"

                        if not p3_record:
                            p3_record = P3Record(
                                id=uuid.uuid4(),
                                tenant_id=job.tenant_id,
                                lot_no_raw=group_lot_raw,
                                lot_no_norm=lot_norm_row,
                                schema_version_id=job.schema_version_id,
                                production_date_yyyymmdd=p3_info["production_date_yyyymmdd"],
                                machine_no=p3_info["machine_no"],
                                mold_no=p3_info["mold_no"],
                                product_id=product_id,
                                extras={}
                            )
                            self.db.add(p3_record)
                            await self.db.flush()
                        else:
                            p3_record.product_id = product_id
                            p3_record.updated_at = func.now()

                        # Delete existing items for this record (if re-importing)
                        await self.db.execute(
                            delete(P3ItemV2).where(P3ItemV2.p3_record_id == p3_record.id)
                        )
                        # Ensure DELETE is flushed before INSERT to avoid unique constraint conflicts
                        await self.db.flush()

                        # Create P3ItemV2 for each row
                        for row_idx, row in enumerate(group_rows, start=1):
                            # Extract fields from row
                            item_product_id = None
                            item_lot_no = group_lot_raw
                            item_production_date = None
                            item_machine_no = p3_info["machine_no"]
                            item_mold_no = p3_info["mold_no"]
                            item_production_lot = None
                            item_source_winder = None
                            item_specification = None
                            item_bottom_tape_lot = None
                            
                            # Map fields from row
                            for field in CSVFieldMapper.PRODUCT_ID_FIELD_NAMES:
                                if field in row and row[field]:
                                    item_product_id = str(row[field]).strip()
                                    break
                            
                            for field in CSVFieldMapper.LOT_NO_FIELD_NAMES:
                                if field in row and row[field]:
                                    item_lot_no = str(row[field]).strip()
                                    break
                            
                            for field in CSVFieldMapper.DATE_FIELD_NAMES:
                                if field in row and row[field]:
                                    try:
                                        ymd = csv_field_mapper._normalize_date_to_yyyymmdd(str(row[field]))
                                        if ymd:
                                            year = ymd // 10000
                                            month = (ymd % 10000) // 100
                                            day = ymd % 100
                                            from datetime import date
                                            item_production_date = date(year, month, day)
                                            break
                                    except Exception:
                                        pass
                            
                            for field in CSVFieldMapper.MACHINE_NO_FIELD_NAMES:
                                if field in row and row[field]:
                                    item_machine_no = str(row[field]).strip()
                                    break
                            
                            for field in CSVFieldMapper.MOLD_NO_FIELD_NAMES:
                                if field in row and row[field]:
                                    item_mold_no = str(row[field]).strip()
                                    break
                            
                            for field in CSVFieldMapper.LOT_FIELD_NAMES:
                                if field in row and row[field]:
                                    try:
                                        item_production_lot = int(float(row[field]))
                                    except (ValueError, TypeError):
                                        pass
                                    break
                            
                            for field in CSVFieldMapper.SOURCE_WINDER_FIELD_NAMES:
                                if field in row and row[field]:
                                    try:
                                        item_source_winder = int(float(row[field]))
                                    except (ValueError, TypeError):
                                        pass
                                    break
                            
                            for field in CSVFieldMapper.SPECIFICATION_FIELD_NAMES:
                                if field in row and row[field]:
                                    item_specification = str(row[field]).strip()
                                    break
                            
                            for field in CSVFieldMapper.BOTTOM_TAPE_LOT_FIELD_NAMES:
                                if field in row and row[field]:
                                    item_bottom_tape_lot = str(row[field]).strip()
                                    break
                            
                            # Create P3ItemV2
                            p3_item = P3ItemV2(
                                id=uuid.uuid4(),
                                p3_record_id=p3_record.id,
                                tenant_id=job.tenant_id,
                                row_no=row_idx,
                                product_id=item_product_id,
                                lot_no=item_lot_no,
                                production_date=item_production_date,
                                machine_no=item_machine_no,
                                mold_no=item_mold_no,
                                production_lot=item_production_lot,
                                source_winder=item_source_winder,
                                specification=item_specification,
                                bottom_tape_lot=item_bottom_tape_lot,
                                row_data=row
                            )
                            self.db.add(p3_item)
                
            job.status = ImportJobStatus.COMPLETED
            await self.db.commit()
            return job
            
        except Exception as e:
            logger.exception(f"Error committing job {job_id}: {e}")
            job.status = ImportJobStatus.FAILED
            job.error_summary = {"error": str(e)}
            await self.db.commit()
            raise e

    def _extract_lot_no(self, filename: str) -> str:
        stem = Path(filename).stem

        # Test scripts may copy files with a leading prefix like "_import_test_".
        # Strip it first so the regular P1_/P2_/P3_ parsing still works.
        for test_prefix in ["_import_test_", "import_test_"]:
            if stem.lower().startswith(test_prefix):
                stem = stem[len(test_prefix):]
                break
        for prefix in ["P1_", "P2_", "P3_", "QC_"]:
            if stem.upper().startswith(prefix):
                return stem[len(prefix):]
        return stem

    def _extract_p2_info(self, filename: str, row_data: List[Dict[str, Any]]) -> int:
        # Try to get winder from filename
        # Format: P2_LotNo_Winder.csv or P2_LotNo.csv (if winder in content)
        parts = Path(filename).stem.split('_')
        winder = None
        
        # Try last part of filename if it's a number and length is small (e.g. 1, 01, 17)
        if len(parts) >= 3:
            last_part = parts[-1]
            if last_part.isdigit() and len(last_part) <= 2:
                winder = int(last_part)
        
        if winder is not None:
            return winder
            
        # Try to get from content (first row)
        if row_data:
            first_row = row_data[0]
            for field in CSVFieldMapper.WINDER_NUMBER_FIELD_NAMES:
                if field in first_row and first_row[field]:
                    try:
                        return int(first_row[field])
                    except (ValueError, TypeError):
                        pass
                        
        # Default or Error
        # For now, default to 1 if not found, but log warning
        logger.warning(f"Could not extract winder number for {filename}, defaulting to 1")
        return 1

    def _extract_p3_info(self, filename: str, row_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        info = {
            "production_date_yyyymmdd": 0,
            "machine_no": "UNKNOWN",
            "mold_no": "UNKNOWN"
        }
        
        # Try filename first
        # P3_YYYYMDD_MM_WW.csv
        parts = Path(filename).stem.split('_')
        
        if len(parts) >= 4:
             # P3_2507173_02_17 -> Date: 2507173, Machine: 02
             # Wait, 2507173 is 7 digits. YYYYMDD? 2025-07-17?
             # If so, YYYYMMDD = 20250717
             date_str = parts[1]
             machine_str = parts[2]
             
             if len(date_str) == 7:
                 # 2507173 -> 20250717
                 # First 2 digits are year (25 -> 2025)
                 # Next 2 are month (07)
                 # Next 2 are day (17)
                 # Last digit? 3?
                 # Wait, PRD says "YYYYMDD". 
                 # 2024 11 01 2 -> 2411012.
                 # 24 (Year) 11 (Month) 01 (Day) 2 (Shift/Seq?)
                 # So date is 20241101.
                 
                 try:
                    year = int("20" + date_str[:2])
                    month = int(date_str[2:4])
                    day = int(date_str[4:6])
                    info["production_date_yyyymmdd"] = year * 10000 + month * 100 + day
                 except ValueError:
                    pass
                 
             info["machine_no"] = machine_str
             
        elif len(parts) >= 3:
            # P3_0902_P24 -> Date: 0902, Machine: P24
            date_str = parts[1]
            machine_str = parts[2]

            # 僅有 MMDD 無法推導年份；禁止用 now/year 猜測，以免污染資料。
            # 正確年份應從內容欄位（例如 114年09月02日）解析。
            # 因此這裡不設定 production_date_yyyymmdd。
            info["machine_no"] = machine_str

        # Try content overrides (prefer content values over filename parsing)
        if row_data:
            first_row = row_data[0]
            # Date (year-month-day etc.)
            for field in CSVFieldMapper.DATE_FIELD_NAMES:
                if field in first_row and first_row[field]:
                    try:
                        ymd = csv_field_mapper._normalize_date_to_yyyymmdd(str(first_row[field]))
                        if ymd:
                            info["production_date_yyyymmdd"] = ymd
                            break
                    except Exception:
                        pass

            # Machine
            for field in CSVFieldMapper.MACHINE_NO_FIELD_NAMES:
                if field in first_row and first_row[field]:
                    info["machine_no"] = str(first_row[field]).strip()
                    break

            # Mold
            for field in CSVFieldMapper.MOLD_NO_FIELD_NAMES:
                if field in first_row and first_row[field]:
                    info["mold_no"] = str(first_row[field]).strip()
                    break

            # Lot / production_lot
            for field in CSVFieldMapper.LOT_FIELD_NAMES:
                if field in first_row and first_row[field]:
                    try:
                        info['lot'] = int(float(first_row[field]))
                    except (ValueError, TypeError):
                        info['lot'] = str(first_row[field])
                    break

        # 最終保護：若仍無法取得日期，直接讓匯入失敗，避免寫入錯誤年份。
        if not info.get("production_date_yyyymmdd"):
            raise ValueError(
                f"P3 production_date missing or unparseable for file={filename}; "
                f"expected a parsable date in content (e.g. 114年09月02日 / 114/09/02)."
            )

        return info
