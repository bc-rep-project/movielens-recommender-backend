from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status
from typing import List, Optional
from datetime import datetime

from ...core.config import settings
from ...models.dataset import DatasetInfo, DatasetDownloadStatus
from ...services.dataset_service import DatasetService
from ..deps import get_dataset_service, get_current_user, get_current_active_user

router = APIRouter()

@router.get("/datasets", response_model=List[DatasetInfo])
async def get_available_datasets(
    dataset_service: DatasetService = Depends(get_dataset_service),
    current_user = Depends(get_current_active_user)
):
    """
    Get a list of available datasets that can be used for recommendations.
    """
    return await dataset_service.list_datasets()

@router.post("/datasets/{dataset_name}/download", response_model=DatasetDownloadStatus)
async def download_dataset(
    dataset_name: str,
    background_tasks: BackgroundTasks,
    dataset_service: DatasetService = Depends(get_dataset_service),
    current_user = Depends(get_current_active_user)
):
    """
    Trigger download of a dataset in the background.
    This is optimized for Cloud Run by:
    1. Checking if the dataset already exists in GCS first
    2. Performing the actual download in a background task to avoid timeout
    3. Storing the download status in MongoDB for later retrieval
    """
    # Validate dataset name (only allow supported datasets)
    if dataset_name not in settings.SUPPORTED_DATASETS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Dataset '{dataset_name}' is not supported. Valid options: {', '.join(settings.SUPPORTED_DATASETS)}"
        )
    
    # Check if dataset already exists (to avoid unnecessary downloads)
    exists = await dataset_service.check_dataset_exists(dataset_name)
    if exists:
        return DatasetDownloadStatus(
            dataset_name=dataset_name,
            status="ALREADY_EXISTS",
            message="Dataset already exists in storage",
            requested_by=current_user.id,
            requested_at=datetime.utcnow(),
        )
    
    # Start download in background (creates job and returns status immediately)
    download_job = await dataset_service.start_dataset_download(
        dataset_name=dataset_name,
        user_id=current_user.id
    )
    
    # Queue the actual download as a background task
    background_tasks.add_task(
        dataset_service.process_dataset_download,
        job_id=download_job.job_id,
        dataset_name=dataset_name
    )
    
    return download_job

@router.get("/jobs/{job_id}", response_model=DatasetDownloadStatus)
async def get_job_status(
    job_id: str,
    dataset_service: DatasetService = Depends(get_dataset_service),
    current_user = Depends(get_current_active_user)
):
    """
    Check the status of a dataset download or processing job
    """
    job = await dataset_service.get_job_status(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job with ID {job_id} not found"
        )
    
    # Optionally: Check if current user can access this job
    # if job.requested_by != current_user.id and not current_user.is_admin:
    #    raise HTTPException(status_code=403, detail="Not authorized to view this job")
    
    return job 