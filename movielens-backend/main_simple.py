#!/usr/bin/env python3
"""
Simplified version of the main entry point for the MovieLens Recommender API.
This is a fallback version with minimal dependencies in case the full version fails.
"""
import os
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Create a simplified FastAPI application
app = FastAPI(
    title="MovieLens Recommender API (Simplified)",
    version="1.1.0",
    description="Simplified version of the MovieLens Recommender API for diagnostic purposes",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    """Root endpoint for basic health check"""
    return {"message": "Welcome to MovieLens Recommender API (Simplified)", "status": "running"}

@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "ok"}

@app.get("/info")
async def info():
    """Information about the current deployment"""
    return {
        "app": "MovieLens Recommender API (Simplified)",
        "version": "1.1.0",
        "environment": {
            "python_path": os.environ.get("PYTHONPATH", "Not set"),
            "port": os.environ.get("PORT", "8080")
        }
    }

@app.get("/api/v1/health/health")
async def api_health():
    """API health check endpoint"""
    return {"status": "ok"}

# This is used when running the app directly (for development)
if __name__ == "__main__":
    import uvicorn
    
    port = int(os.environ.get("PORT", 8080))
    logger.info(f"Starting simplified development server on port {port}")
    
    uvicorn.run(
        "main_simple:app",
        host="0.0.0.0",
        port=port,
        log_level="info",
    ) 