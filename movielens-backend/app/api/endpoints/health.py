# /health endpoint

# backend/app/api/endpoints/health.py

import logging
from fastapi import APIRouter, status
from pydantic import BaseModel

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