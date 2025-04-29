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
api_router.include_router(models.router, prefix="/models", tags=["Models"])

# Note: The models router should not be included twice. The admin endpoints 
# in models.py already have "/admin/" in their paths, so they will be properly
# routed through the single router inclusion above. 