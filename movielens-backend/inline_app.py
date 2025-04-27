#!/usr/bin/env python3
"""
Self-contained script that defines and runs a FastAPI app directly,
without any imports from other modules.
"""
import os
import sys
import logging
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger("inline_app")

# Print startup information
logger.info(f"Starting inline app with Python {sys.version}")
logger.info(f"Current directory: {os.getcwd()}")
logger.info(f"Script location: {__file__}")
logger.info(f"Environment variables: PYTHONPATH={os.environ.get('PYTHONPATH', 'Not set')}, PORT={os.environ.get('PORT', '8080')}")

# Create FastAPI app directly in this script
app = FastAPI(
    title="MovieLens Inline Test API",
    description="Inline test API to verify Cloud Run deployment",
    version="0.1.0",
)

# Add endpoints
@app.get("/")
async def root():
    logger.info("Root endpoint called")
    return {"message": "Inline MovieLens API is running!"}

@app.get("/health")
async def health():
    logger.info("Health check called")
    return {"status": "ok"}

@app.get("/info")
async def info():
    logger.info("Info endpoint called")
    # Collect some useful debugging information
    return {
        "system_info": {
            "python_version": sys.version,
            "paths": sys.path,
            "cwd": os.getcwd(),
            "files": os.listdir("."),
        }
    }

# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={"message": f"Server error: {str(exc)}"},
    )

# Start the server directly from this script
if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    logger.info(f"Starting uvicorn server on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info") 