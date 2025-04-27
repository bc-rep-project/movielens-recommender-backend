"""
Primary FastAPI application entry point
"""
import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware

# Import settings and core components
try:
    from app.core.config import settings
    from app.api.deps import initialize_connections, close_connections
    from app.api.api import api_router
except ImportError as e:
    print(f"ERROR: Failed to import required modules: {str(e)}")
    raise

# Configure logging
logging.basicConfig(
    level="INFO",
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)
logger.info("Starting MovieLens API server...")

# Define application lifespan
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Application startup: Initializing connections...")
    await initialize_connections()
    yield
    # Shutdown
    logger.info("Application shutdown: Closing connections...")
    await close_connections()

# Create FastAPI application
app = FastAPI(
    title="MovieLens Recommender API",
    version="0.1.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
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
app.include_router(api_router, prefix="/api")

# Root endpoint
@app.get("/", status_code=status.HTTP_200_OK)
async def root():
    """Root endpoint to confirm the API is running."""
    return {"message": "Welcome to MovieLens Recommender API"}

# For local development
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.server:app", host="0.0.0.0", port=8080, reload=True) 