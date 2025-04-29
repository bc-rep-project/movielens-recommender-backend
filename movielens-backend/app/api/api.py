"""
API Router Module - Aggregates all endpoint routers
"""
from fastapi import APIRouter

from app.api.endpoints import health, movies, recommendations, interactions, datasets, models

# Create the main API router
api_router = APIRouter()

# Include all endpoint routers with appropriate prefixes and tags
api_router.include_router(health.router, prefix="/health", tags=["Health"])
api_router.include_router(movies.router, prefix="/movies", tags=["Movies"])
api_router.include_router(recommendations.router, prefix="/recommendations", tags=["Recommendations"])
api_router.include_router(interactions.router, prefix="/interactions", tags=["Interactions"])
api_router.include_router(datasets.router, prefix="/data", tags=["Datasets"])
api_router.include_router(models.router, prefix="/data", tags=["Models"])

# Admin endpoints
api_router.include_router(models.router, prefix="/admin", tags=["Admin"]) 