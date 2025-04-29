#!/usr/bin/env python3
"""
Main entry point for the MovieLens Recommender API
This file is intended to be imported as a module by Gunicorn
or run directly to start a development server.
"""
import os
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

# Import router and initialization functions
from app.api.api import api_router
from app.api.deps import initialize_connections, close_connections
from app.core.config import settings

# Configure logging
logging.basicConfig(
    level=settings.LOG_LEVEL,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Setup and teardown operations for the application.
    This is called when the application starts and stops.
    """
    # Startup: initialize MongoDB and Redis connections
    logger.info("Starting up MovieLens Recommender API...")
    await initialize_connections()
    yield
    # Shutdown: close connections
    logger.info("Shutting down MovieLens Recommender API...")
    await close_connections()

# Create FastAPI application
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="MovieLens Recommender API provides movie recommendations based on content and collaborative filtering",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[str(origin) for origin in settings.BACKEND_CORS_ORIGINS],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API router
app.include_router(api_router, prefix=settings.API_V1_STR)

@app.get("/")
async def root():
    """Root endpoint for basic health check"""
    return {"message": f"Welcome to {settings.PROJECT_NAME} v{settings.VERSION}"}

# This is used when running the app directly (for development)
if __name__ == "__main__":
    import uvicorn
    
    port = int(os.environ.get("PORT", 8080))
    logger.info(f"Starting development server on port {port}")
    
    uvicorn.run(
        "main:app",  # Import string for the app variable in this file
        host="0.0.0.0",
        port=port,
        reload=True,  # Enable auto-reload for development
        log_level=settings.LOG_LEVEL.lower(),
    )