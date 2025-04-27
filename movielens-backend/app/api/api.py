"""
API Router Module - Aggregates all endpoint routers
"""
from fastapi import APIRouter

from app.api.endpoints import health, movies, recommendations, interactions, auth

# Create the main API router
api_router = APIRouter()

# Include all endpoint routers with appropriate prefixes and tags
api_router.include_router(health.router, prefix="/health", tags=["Health"])
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(movies.router, prefix="/movies", tags=["Movies"])
api_router.include_router(recommendations.router, prefix="/recommendations", tags=["Recommendations"])
api_router.include_router(interactions.router, prefix="/interactions", tags=["Interactions"]) 