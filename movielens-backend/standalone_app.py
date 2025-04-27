#!/usr/bin/env python3
"""
Completely self-contained FastAPI application with no external imports.
This is a test to determine if we can get any FastAPI app running on Cloud Run.
"""
import os
import sys
import logging
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger("standalone_app")
logger.info("Starting standalone app")

# Create FastAPI app
app = FastAPI(
    title="MovieLens Standalone Test API",
    description="Test API to verify Cloud Run deployment",
    version="0.1.0",
)

# Health check endpoint
@app.get("/health")
async def health_check():
    logger.info("Health check called")
    return {"status": "ok", "message": "Standalone app is running"}

# Root endpoint
@app.get("/")
async def root():
    logger.info("Root endpoint called")
    return {
        "message": "Standalone MovieLens API is running",
        "system_info": {
            "python_version": sys.version,
            "environment": {k: v for k, v in os.environ.items() if k in ["PYTHONPATH", "HOME", "PATH"]},
            "cwd": os.getcwd(),
            "files_in_app": os.listdir("/app") if os.path.exists("/app") else "No /app directory",
        }
    }

# Endpoint to list all routes
@app.get("/routes")
async def list_routes():
    logger.info("Routes endpoint called")
    routes = []
    for route in app.routes:
        routes.append({
            "path": route.path,
            "name": route.name,
            "methods": getattr(route, "methods", None),
        })
    return {"routes": routes}

# Generic exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={"message": f"Internal server error: {str(exc)}"},
    )

# Print confirmation message
logger.info(f"App created with {len(app.routes)} routes")
logger.info("This file is meant to be run directly by uvicorn")

# Direct execution (for testing)
if __name__ == "__main__":
    import uvicorn
    logger.info("Starting uvicorn server...")
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8080")), log_level="info") 