import csv
import uuid
from pathlib import Path
from typing import List, Dict, Any
import logging

from sqlalchemy import select, func
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

        # 2. Define Validation Rules (Hardcoded for now based on P1)
        required_fields = []
        numeric_fields = []
        
        if table.table_code == "P1":
            # Example rules for P1
            required_fields = ["Lot No.", "Winder"]
            numeric_fields = ["Winder"]
        elif table.table_code == "P3":
            # Rules for P3
            required_fields = ["date", "time", "value"]
            numeric_fields = ["value"]
        
        # Track seen keys for E_UNIQUE_IN_FILE
        seen_keys = set()

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
                
                # Deduplication Logic
                unique_key = None
                lot_no_raw = self._extract_lot_no(filename)
                lot_no_norm = normalize_lot_no(lot_no_raw)
                
                if table.table_code == "P1":
                    unique_key = (job.tenant_id, lot_no_norm)
                    # Check DB
                    from app.models.p1_record import P1Record
                    db_stmt = select(P1Record).where(
                        P1Record.tenant_id == job.tenant_id,
                        P1Record.lot_no_norm == lot_no_norm
                    )
                    if (await self.db.execute(db_stmt)).scalar_one_or_none():
                         errors.append({"field": "lot_no", "message": "E_UNIQUE_IN_DB"})

                elif table.table_code == "P2":
                    winder = self._extract_p2_info(filename, [data])
                    unique_key = (job.tenant_id, lot_no_norm, winder)
                    # Check DB
                    from app.models.p2_record import P2Record
                    db_stmt = select(P2Record).where(
                        P2Record.tenant_id == job.tenant_id,
                        P2Record.lot_no_norm == lot_no_norm,
                        P2Record.winder_number == winder
                    )
                    if (await self.db.execute(db_stmt)).scalar_one_or_none():
                         errors.append({"field": "lot_no", "message": "E_UNIQUE_IN_DB"})

                elif table.table_code == "P3":
                    p3_info = self._extract_p3_info(filename, [data])
                    unique_key = (
                        job.tenant_id, 
                        p3_info["production_date_yyyymmdd"], 
                        p3_info["machine_no"], 
                        p3_info["mold_no"], 
                        lot_no_norm
                    )
                    # Check DB
                    from app.models.p3_record import P3Record
                    db_stmt = select(P3Record).where(
                        P3Record.tenant_id == job.tenant_id,
                        P3Record.lot_no_norm == lot_no_norm,
                        P3Record.machine_no == p3_info["machine_no"],
                        P3Record.mold_no == p3_info["mold_no"],
                        P3Record.production_date_yyyymmdd == p3_info["production_date_yyyymmdd"]
                    )
                    if (await self.db.execute(db_stmt)).scalar_one_or_none():
                         errors.append({"field": "lot_no", "message": "E_UNIQUE_IN_DB"})

                # Check E_UNIQUE_IN_FILE
                if unique_key:
                    if unique_key in seen_keys:
                        errors.append({"field": "lot_no", "message": "E_UNIQUE_IN_FILE"})
                    else:
                        seen_keys.add(unique_key)

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
                    
                    # Extract Winder Number
                    winder_number = self._extract_p2_info(file_record.filename, row_data)
                    
                    # Check existence
                    existing_stmt = select(P2Record).where(
                        P2Record.tenant_id == job.tenant_id,
                        P2Record.lot_no_norm == lot_no_norm,
                        P2Record.winder_number == winder_number
                    )
                    existing_result = await self.db.execute(existing_stmt)
                    existing_record = existing_result.scalar_one_or_none()
                    
                    if existing_record:
                        # Update
                        existing_record.extras = {"rows": row_data}
                        existing_record.updated_at = func.now()
                    else:
                        # Create
                        new_record = P2Record(
                            id=uuid.uuid4(),
                            tenant_id=job.tenant_id,
                            lot_no_raw=lot_no_raw,
                            lot_no_norm=lot_no_norm,
                            schema_version_id=job.schema_version_id,
                            winder_number=winder_number,
                            extras={"rows": row_data}
                        )
                        self.db.add(new_record)

                elif table.table_code == "P3":
                    from app.models.p3_record import P3Record
                    
                    # Extract P3 Info (content overrides filename when possible)
                    p3_info = self._extract_p3_info(file_record.filename, row_data)
                    
                    # Generate product_id
                    # Format: YYYYMMDD_Machine_Mold_Lot
                    # production_date_yyyymmdd is e.g. 20250717
                    date_str = str(p3_info.get("production_date_yyyymmdd") or 0)
                    # Prefer production lot from p3_info (from 'lot' column). Product ID last segment is expected to be an integer.
                    lot_part_raw = p3_info.get('lot')
                    lot_part: int
                    try:
                        lot_part = int(lot_part_raw) if lot_part_raw is not None else 0
                    except (ValueError, TypeError):
                        lot_part = 0

                    product_id = f"{date_str}-{p3_info.get('machine_no')}-{p3_info.get('mold_no')}-{lot_part}"

                    # Check existence
                    existing_stmt = select(P3Record).where(
                        P3Record.tenant_id == job.tenant_id,
                        P3Record.lot_no_norm == lot_no_norm,
                        P3Record.machine_no == p3_info["machine_no"],
                        P3Record.mold_no == p3_info["mold_no"],
                        P3Record.production_date_yyyymmdd == p3_info["production_date_yyyymmdd"]
                    )
                    existing_result = await self.db.execute(existing_stmt)
                    existing_record = existing_result.scalar_one_or_none()
                    
                    if existing_record:
                        # Update
                        existing_record.extras = {"rows": row_data}
                        existing_record.product_id = product_id
                        existing_record.updated_at = func.now()
                    else:
                        # Create
                        new_record = P3Record(
                            id=uuid.uuid4(),
                            tenant_id=job.tenant_id,
                            lot_no_raw=lot_no_raw,
                            lot_no_norm=lot_no_norm,
                            schema_version_id=job.schema_version_id,
                            production_date_yyyymmdd=p3_info["production_date_yyyymmdd"],
                            machine_no=p3_info["machine_no"],
                            mold_no=p3_info["mold_no"],
                            product_id=product_id,
                            extras={"rows": row_data}
                        )
                        self.db.add(new_record)
                
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
            
            # Guess year? Current year?
            # Let's assume 2025 for now or use current year
            import datetime
            current_year = datetime.datetime.now().year
            try:
                info["production_date_yyyymmdd"] = current_year * 10000 + int(date_str)
            except ValueError:
                pass
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
                    
        return info
