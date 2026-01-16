import hashlib
import shutil
import uuid
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status, BackgroundTasks, Request
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


async def _mark_job_failed(job_id: uuid.UUID, error: Exception | str) -> None:
    if not database.async_session_factory:
        logger.error(f"Async session factory not initialized; cannot mark job {job_id} as FAILED")
        return

    error_text = str(error)
    async with database.async_session_factory() as db:
        stmt = select(ImportJob).where(ImportJob.id == job_id)
        result = await db.execute(stmt)
        job = result.scalar_one_or_none()
        if not job:
            return
        job.status = ImportJobStatus.FAILED
        job.error_summary = {"error": error_text}
        job.last_status_changed_at = datetime.now(timezone.utc)
        job.last_status_actor_kind = "system"
        job.last_status_actor_api_key_id = None
        job.last_status_actor_label_snapshot = None
        await db.commit()

async def process_import_job_background(job_id: uuid.UUID):
    """
    Background task to parse and validate import job.
    """
    if not database.async_session_factory:
        await _mark_job_failed(job_id, "Async session factory not initialized")
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
            await _mark_job_failed(job_id, e)

@router.post("/jobs", response_model=ImportJobRead, status_code=status.HTTP_201_CREATED)
async def create_import_job(
    request: Request,
    background_tasks: BackgroundTasks,
    table_code: str = Form(..., description="Target table code (e.g., 'P1', 'P2')"),
    allow_duplicate: bool = Form(False, description="Allow importing the same file content multiple times"),
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
    actor_api_key_id = getattr(getattr(request, "state", None), "auth_api_key_id", None)
    actor_api_key_label = getattr(getattr(request, "state", None), "auth_api_key_label", None)
    if actor_api_key_id:
        job.actor_api_key_id = actor_api_key_id
        job.actor_label_snapshot = actor_api_key_label
        job.last_status_actor_api_key_id = actor_api_key_id
        job.last_status_actor_label_snapshot = actor_api_key_label
    job.last_status_changed_at = datetime.now(timezone.utc)
    job.last_status_actor_kind = "user"
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
            if (not allow_duplicate) and dup_result.scalars().first():
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
    
    # Trigger background processing (only if global session factory is available).
    # In tests we often override `get_db` without initializing the global factory.
    if database.async_session_factory:
        background_tasks.add_task(process_import_job_background, job.id)
    else:
        # Avoid noisy errors in testing; callers can invoke service methods directly.
        if settings.environment.lower() != "testing":
            logger.warning(
                "Skip background processing: async_session_factory not initialized"
            )
    
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
    request: Request,
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
        
    if job.status not in (ImportJobStatus.READY, ImportJobStatus.COMMITTING):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Job is not ready to commit (status: {job.status})"
        )
    
    # Update status to COMMITTING immediately to prevent double clicks.
    # If job is already COMMITTING (e.g., background task crashed/restarted), allow re-trigger.
    if job.status != ImportJobStatus.COMMITTING:
        job.status = ImportJobStatus.COMMITTING
        actor_api_key_id = getattr(getattr(request, "state", None), "auth_api_key_id", None)
        actor_api_key_label = getattr(getattr(request, "state", None), "auth_api_key_label", None)
        if actor_api_key_id:
            job.actor_api_key_id = actor_api_key_id
            job.actor_label_snapshot = actor_api_key_label
            job.last_status_actor_api_key_id = actor_api_key_id
            job.last_status_actor_label_snapshot = actor_api_key_label
        job.last_status_changed_at = datetime.now(timezone.utc)
        job.last_status_actor_kind = "user"
        await db.commit()
        await db.refresh(job)
    
    # In tests we need deterministic behavior; commit synchronously.
    if settings.environment.lower() == "testing":
        service = ImportService(db)
        actor_api_key_id = getattr(getattr(request, "state", None), "auth_api_key_id", None)
        actor_api_key_label = getattr(getattr(request, "state", None), "auth_api_key_label", None)
        await service.commit_job(
            job.id,
            actor_api_key_id=actor_api_key_id,
            actor_label_snapshot=actor_api_key_label,
            actor_kind="user",
        )
    else:
        # Trigger background commit
        background_tasks.add_task(process_commit_job_background, job.id)
    
    # Re-fetch with files for response schema
    from sqlalchemy.orm import selectinload
    stmt = select(ImportJob).options(selectinload(ImportJob.files)).where(ImportJob.id == job_id)
    result = await db.execute(stmt)
    job = result.scalar_one()
    
    return job


@router.post("/jobs/{job_id}/cancel", response_model=ImportJobRead)
async def cancel_import_job(
    job_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_tenant: Tenant = Depends(get_current_tenant),
):
    """Cancel an import job (idempotent)."""
    stmt = select(ImportJob).where(
        ImportJob.id == job_id,
        ImportJob.tenant_id == current_tenant.id,
    )
    result = await db.execute(stmt)
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Import job not found",
        )

    if job.status != ImportJobStatus.CANCELLED:
        job.status = ImportJobStatus.CANCELLED
        actor_api_key_id = getattr(getattr(request, "state", None), "auth_api_key_id", None)
        actor_api_key_label = getattr(getattr(request, "state", None), "auth_api_key_label", None)
        if actor_api_key_id:
            job.actor_api_key_id = actor_api_key_id
            job.actor_label_snapshot = actor_api_key_label
            job.last_status_actor_api_key_id = actor_api_key_id
            job.last_status_actor_label_snapshot = actor_api_key_label
        job.last_status_changed_at = datetime.now(timezone.utc)
        job.last_status_actor_kind = "user"
        await db.commit()

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
        await _mark_job_failed(job_id, "Async session factory not initialized")
        return

    async with database.async_session_factory() as db:
        service = ImportService(db)
        try:
            logger.info(f"Starting background commit for job {job_id}")
            await service.commit_job(job_id)
            logger.info(f"Completed background commit for job {job_id}")
        except Exception as e:
            logger.exception(f"Background commit failed for job {job_id}: {e}")
            await _mark_job_failed(job_id, e)

