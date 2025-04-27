"""
Self-contained FastAPI application for Cloud Run deployment
This file contains all components needed to run the application.
"""
import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware

# Configure logging
logging.basicConfig(
    level="INFO",
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

# Create a sample router (in production, import your actual routers)
from fastapi import APIRouter
router = APIRouter()

@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "ok"}

# Define application lifespan
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Application startup...")
    # Add your initialization code here
    yield
    # Shutdown
    logger.info("Application shutdown...")
    # Add your cleanup code here

# Create FastAPI application
app = FastAPI(
    title="MovieLens Recommender API",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(router)

# Root endpoint
@app.get("/")
async def root():
    """Root endpoint to confirm the API is running."""
    return {"message": "Welcome to MovieLens Recommender API"}

# For local testing only
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("application:app", host="0.0.0.0", port=8080, reload=True) 