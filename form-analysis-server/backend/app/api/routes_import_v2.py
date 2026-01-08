import hashlib
import shutil
import uuid
import logging
from datetime import datetime
from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status, BackgroundTasks
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_current_tenant
from app.core import database
from app.core.config import get_settings
from app.models.core.tenant import Tenant
from app.models.core.schema_registry import TableRegistry
from app.models.import_job import ImportJob, ImportFile, ImportJobStatus, StagingRow
from app.schemas.import_job import ImportJobRead, ImportJobErrorRow
from app.services.import_v2 import ImportService

router = APIRouter()
settings = get_settings()
logger = logging.getLogger(__name__)

async def process_import_job_background(job_id: uuid.UUID):
    """
    Background task to parse and validate import job.
    """
    if not database.async_session_factory:
        logger.error("Async session factory not initialized")
        return

    async with database.async_session_factory() as db:
        service = ImportService(db)
        try:
            logger.info(f"Starting background processing for job {job_id}")
            # 1. Parse
            await service.parse_job(job_id)
            # 2. Validate
            await service.validate_job(job_id)
            logger.info(f"Completed background processing for job {job_id}")
        except Exception as e:
            logger.exception(f"Background processing failed for job {job_id}: {e}")

@router.post("/jobs", response_model=ImportJobRead, status_code=status.HTTP_201_CREATED)
async def create_import_job(
    background_tasks: BackgroundTasks,
    table_code: str = Form(..., description="Target table code (e.g., 'P1', 'P2')"),
    files: List[UploadFile] = File(..., description="Files to upload"),
    db: AsyncSession = Depends(get_db),
    current_tenant: Tenant = Depends(get_current_tenant),
):
    """
    Create a new import job with uploaded files.
    """
    # 1. Validate Table Code
    stmt = select(TableRegistry).where(TableRegistry.table_code == table_code)
    result = await db.execute(stmt)
    table_registry = result.scalar_one_or_none()
    
    if not table_registry:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid table code: {table_code}"
        )

    # 1.5 Check Mixed Batch (Extensions)
    exts = {Path(f.filename).suffix.lower() for f in files}
    if len(exts) > 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Mixed file formats are not allowed. Found: {', '.join(exts)}"
        )

    # 2. Create Job
    job_id = uuid.uuid4()
    # Generate batch_id
    batch_id = f"{datetime.now().strftime('%Y%m%d')}-{str(job_id)[:8]}"
    
    job = ImportJob(
        id=job_id,
        tenant_id=current_tenant.id,
        table_id=table_registry.id,
        batch_id=batch_id,
        status=ImportJobStatus.UPLOADED,
        total_files=len(files)
    )
    db.add(job)
    
    # 3. Process Files
    upload_dir = Path(settings.upload_temp_dir) / str(job_id)
    upload_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        for file in files:
            # Calculate Hash & Save
            file_path = upload_dir / file.filename
            
            sha256_hash = hashlib.sha256()
            file_size = 0
            
            # Write to disk and hash
            with open(file_path, "wb") as buffer:
                while content := await file.read(1024 * 1024): # 1MB chunks
                    sha256_hash.update(content)
                    buffer.write(content)
                    file_size += len(content)
            
            file_hash = sha256_hash.hexdigest()
            
            # Check for duplicates (L2-3)
            dup_stmt = select(ImportFile).where(
                ImportFile.tenant_id == current_tenant.id,
                ImportFile.table_id == table_registry.id,
                ImportFile.file_hash == file_hash
            )
            dup_result = await db.execute(dup_stmt)
            if dup_result.scalars().first():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Duplicate file detected: {file.filename}"
                )

            # Create ImportFile record
            import_file = ImportFile(
                job_id=job_id,
                tenant_id=current_tenant.id,
                table_id=table_registry.id,
                filename=file.filename,
                file_hash=file_hash,
                storage_path=str(file_path),
                file_size=file_size
            )
            db.add(import_file)
    except Exception as e:
        # Cleanup uploaded files
        if upload_dir.exists():
            shutil.rmtree(upload_dir)
        raise e
    
    await db.commit()
    await db.refresh(job)
    
    # Eager load files for response
    # In async sqlalchemy, relationships are lazy by default. 
    # We might need to select with options or rely on implicit loading if session is open (but await is needed)
    # For simplicity, let's re-fetch with files
    
    stmt = select(ImportJob).where(ImportJob.id == job_id).execution_options(populate_existing=True)
    # We rely on lazy loading working if we access it before session close, 
    # but with async it's tricky. Better to use selectinload.
    
    from sqlalchemy.orm import selectinload
    stmt = select(ImportJob).options(selectinload(ImportJob.files)).where(ImportJob.id == job_id)
    result = await db.execute(stmt)
    job = result.scalar_one()
    
    # Trigger background processing
    background_tasks.add_task(process_import_job_background, job.id)
    
    return job

@router.get("/jobs/{job_id}", response_model=ImportJobRead)
async def get_import_job(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_tenant: Tenant = Depends(get_current_tenant),
):
    """
    Get import job status and details.
    """
    from sqlalchemy.orm import selectinload
    
    stmt = select(ImportJob).options(selectinload(ImportJob.files)).where(
        ImportJob.id == job_id,
        ImportJob.tenant_id == current_tenant.id
    )
    result = await db.execute(stmt)
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Import job not found"
        )
    
    return job
    stmt = select(ImportJob).where(
        ImportJob.id == job_id,
        ImportJob.tenant_id == current_tenant.id
    )
    result = await db.execute(stmt)
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Import job not found"
        )

    service = ImportService(db)
    try:
        await service.commit_job(job_id)
        
        # Reload job with files for response
        from sqlalchemy.orm import selectinload
        stmt = select(ImportJob).options(selectinload(ImportJob.files)).where(ImportJob.id == job_id)
        result = await db.execute(stmt)
        job = result.scalar_one()
        
        return job
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.get("/jobs/{job_id}/errors", response_model=List[ImportJobErrorRow])
async def get_import_job_errors(
    job_id: uuid.UUID,
    page: int = 1,
    page_size: int = 50,
    db: AsyncSession = Depends(get_db),
    current_tenant: Tenant = Depends(get_current_tenant),
):
    """
    Get validation errors for an import job.
    """
    # Verify job ownership
    stmt = select(ImportJob).where(
        ImportJob.id == job_id,
        ImportJob.tenant_id == current_tenant.id
    )
    result = await db.execute(stmt)
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Import job not found"
        )
        
    # Query errors
    offset = (page - 1) * page_size
    stmt = select(StagingRow).where(
        StagingRow.job_id == job_id,
        StagingRow.is_valid == False
    ).order_by(StagingRow.row_index).offset(offset).limit(page_size)
    
    result = await db.execute(stmt)
    rows = result.scalars().all()
    
    return rows

@router.post("/jobs/{job_id}/commit", response_model=ImportJobRead)
async def commit_import_job(
    job_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_tenant: Tenant = Depends(get_current_tenant),
):
    """
    Commit a READY import job to target tables.
    """
    stmt = select(ImportJob).where(
        ImportJob.id == job_id,
        ImportJob.tenant_id == current_tenant.id
    )
    result = await db.execute(stmt)
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Import job not found"
        )
        
    if job.status != ImportJobStatus.READY:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Job is not ready to commit (status: {job.status})"
        )
    
    # Update status to COMMITTING immediately to prevent double clicks
    job.status = ImportJobStatus.COMMITTING
    await db.commit()
    await db.refresh(job)
    
    # Trigger background commit
    background_tasks.add_task(process_commit_job_background, job.id)
    
    # Re-fetch with files for response schema
    from sqlalchemy.orm import selectinload
    stmt = select(ImportJob).options(selectinload(ImportJob.files)).where(ImportJob.id == job_id)
    result = await db.execute(stmt)
    job = result.scalar_one()
    
    return job

async def process_commit_job_background(job_id: uuid.UUID):
    """
    Background task to commit import job.
    """
    if not database.async_session_factory:
        logger.error("Async session factory not initialized")
        return

    async with database.async_session_factory() as db:
        service = ImportService(db)
        try:
            logger.info(f"Starting background commit for job {job_id}")
            await service.commit_job(job_id)
            logger.info(f"Completed background commit for job {job_id}")
        except Exception as e:
            logger.exception(f"Background commit failed for job {job_id}: {e}")

