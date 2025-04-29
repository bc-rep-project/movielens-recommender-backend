from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status
from typing import List, Optional
from datetime import datetime

from ...core.config import settings
from ...models.model import ModelInfo, TrainingRequest, TrainingJob
from ...services.model_service import ModelService
from ..deps import get_model_service, get_current_active_user

router = APIRouter()

@router.get("/models", response_model=List[ModelInfo])
async def get_available_models(
    model_service: ModelService = Depends(get_model_service),
    current_user = Depends(get_current_active_user)
):
    """
    Get a list of all trained recommendation models
    """
    return await model_service.list_models()

@router.post("/models/train", response_model=TrainingJob)
async def train_model(
    training_request: TrainingRequest,
    background_tasks: BackgroundTasks,
    model_service: ModelService = Depends(get_model_service),
    current_user = Depends(get_current_active_user)
):
    """
    Train a new recommendation model.
    This is optimized for Cloud Run by:
    1. Validating the request and creating a job record
    2. Performing the actual training in a background task
    3. Using resource-efficient models suitable for free tier
    """
    # Start training job and get the initial job status
    training_job = await model_service.start_model_training(
        model_name=training_request.model_name,
        model_type=training_request.model_type,
        dataset_name=training_request.dataset_name,
        description=training_request.description,
        parameters=training_request.parameters,
        user_id=current_user.id
    )
    
    # Queue the actual training as a background task
    background_tasks.add_task(
        model_service.process_model_training,
        job_id=training_job.job_id
    )
    
    return training_job

@router.get("/models/{model_id}", response_model=ModelInfo)
async def get_model_details(
    model_id: str,
    model_service: ModelService = Depends(get_model_service),
    current_user = Depends(get_current_active_user)
):
    """
    Get details for a specific model
    """
    model = await model_service.get_model(model_id)
    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model with ID {model_id} not found"
        )
    
    return model

@router.put("/models/{model_id}/activate", response_model=ModelInfo)
async def activate_model(
    model_id: str,
    model_service: ModelService = Depends(get_model_service),
    current_user = Depends(get_current_active_user)
):
    """
    Activate a model (set it as the active model for its type)
    """
    updated_model = await model_service.activate_model(model_id)
    if not updated_model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model with ID {model_id} not found"
        )
    
    return updated_model

@router.get("/admin/retraining-jobs/{job_id}", response_model=TrainingJob)
async def get_training_job_status(
    job_id: str,
    model_service: ModelService = Depends(get_model_service),
    current_user = Depends(get_current_active_user)
):
    """
    Check the status of a model training job
    """
    job = await model_service.get_job_status(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Training job with ID {job_id} not found"
        )
    
    # Optionally: Check if current user can access this job
    # if job.requested_by != current_user.id and not current_user.is_admin:
    #    raise HTTPException(status_code=403, detail="Not authorized to view this job")
    
    return job

@router.post("/admin/retrain-model", response_model=TrainingJob)
async def admin_retrain_model(
    training_request: TrainingRequest,
    background_tasks: BackgroundTasks,
    model_service: ModelService = Depends(get_model_service),
    current_user = Depends(get_current_active_user)
):
    """
    Admin endpoint to retrain a model with specific parameters.
    Acts as an alias for the standard train endpoint but may include admin-specific functionality.
    """
    # Check if user is admin (simplified example)
    # if not current_user.is_admin:
    #    raise HTTPException(status_code=403, detail="Admin access required")
    
    # Same logic as train_model but potentially with different defaults or validations
    # Start training job and get the initial job status
    training_job = await model_service.start_model_training(
        model_name=training_request.model_name,
        model_type=training_request.model_type,
        dataset_name=training_request.dataset_name,
        description=training_request.description,
        parameters=training_request.parameters,
        user_id=current_user.id
    )
    
    # Queue the actual training as a background task
    background_tasks.add_task(
        model_service.process_model_training,
        job_id=training_job.job_id
    )
    
    return training_job 