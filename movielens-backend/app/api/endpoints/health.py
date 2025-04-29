# /health endpoint

# backend/app/api/endpoints/health.py

import logging
from fastapi import APIRouter, status, Depends
from pydantic import BaseModel
from typing import Dict, Any, Optional
from ..deps import get_current_user, get_dataset_service, get_model_service

logger = logging.getLogger(__name__)
router = APIRouter()

class HealthResponse(BaseModel):
    status: str = "ok"

@router.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    tags=["Health"],
    summary="Perform a Health Check",
    response_description="Returns the health status of the API.",
)
async def health_check():
    """
    Simple health check endpoint to confirm the API is running.
    Used by Cloud Run for health checks.
    """
    # Could potentially add checks for DB/Cache connectivity here if needed,
    # but keep it fast for liveness probes.
    # logger.debug("Health check endpoint called.")
    return HealthResponse(status="ok")

@router.get("/health/retraining", status_code=status.HTTP_200_OK)
async def retraining_health_check(
    dataset_service = Depends(get_dataset_service),
    model_service = Depends(get_model_service),
    current_user = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Health check endpoint for model training functionality.
    This checks:
    1. If the necessary services are available
    2. If any training jobs are in progress
    3. Basic stats about models and datasets
    
    Protected by authentication to avoid unnecessary DB queries from public health checks.
    """
    # Get active models count
    active_models = []
    model_types = ["content_based", "collaborative_filtering", "hybrid"]
    
    for model_type in model_types:
        model = await model_service.get_active_model(model_type)
        if model:
            active_models.append({
                "type": model_type,
                "id": model.model_id,
                "name": model.name
            })
    
    # Get count of training jobs by status
    training_jobs_count = {
        "pending": await model_service.training_jobs_collection.count_documents({"status": "PENDING"}),
        "in_progress": await model_service.training_jobs_collection.count_documents({"status": "IN_PROGRESS"}),
        "completed": await model_service.training_jobs_collection.count_documents({"status": "COMPLETE"}),
        "failed": await model_service.training_jobs_collection.count_documents({"status": "FAILED"})
    }
    
    # Get dataset stats
    datasets = await dataset_service.list_datasets()
    
    # Get a count of MongoDB collections
    movie_count = await dataset_service.movies_collection.count_documents({})
    rating_count = await dataset_service.ratings_collection.count_documents({})
    
    return {
        "status": "ok",
        "active_models": active_models,
        "training_jobs": training_jobs_count,
        "data": {
            "datasets": len(datasets),
            "movies": movie_count,
            "ratings": rating_count
        }
    }