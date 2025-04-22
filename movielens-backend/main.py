# FastAPI/Flask app initialization and entry point
# backend/main.py

import logging
import logging.config
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware

# Import settings and core components
from app.core.config import settings
from app.api.deps import initialize_connections, close_connections # Lifespan functions
from app.api.api import api_router # Assuming you have an aggregator router

# --- Logging Configuration ---
# Configure logging (can be more sophisticated, e.g., using dictConfig)
# Ensure logs go to stdout/stderr for Cloud Run / Docker
log_level = settings.LOG_LEVEL.upper()
logging.basicConfig(
    level=log_level,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout,
)
# Optionally configure JSON logging for better parsing in Cloud Logging
# from pythonjsonlogger import jsonlogger
# handler = logging.StreamHandler()
# formatter = jsonlogger.JsonFormatter('%(asctime)s %(name)s %(levelname)s %(message)s')
# handler.setFormatter(formatter)
# logging.getLogger().handlers.clear() # Remove default handlers
# logging.getLogger().addHandler(handler)
# logging.getLogger().setLevel(log_level)

logger = logging.getLogger(__name__)
logger.info(f"Starting {settings.PROJECT_NAME} v{settings.VERSION}...")
logger.info(f"Log Level set to: {log_level}")


# --- Lifespan Management (Database/Cache Connections) ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Code to run on startup
    logger.info("Application startup: Initializing connections...")
    await initialize_connections()
    yield
    # Code to run on shutdown
    logger.info("Application shutdown: Closing connections...")
    await close_connections()


# --- FastAPI Application Instance ---
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json", # Standard OpenAPI path
    docs_url=f"{settings.API_V1_STR}/docs", # Standard Swagger UI path
    redoc_url=f"{settings.API_V1_STR}/redoc", # Standard ReDoc path
    lifespan=lifespan # Attach the lifespan context manager
)


# --- CORS Middleware ---
# Set up CORS (Cross-Origin Resource Sharing)
if settings.BACKEND_CORS_ORIGINS:
    logger.info(f"Configuring CORS for origins: {settings.BACKEND_CORS_ORIGINS}")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin).strip() for origin in settings.BACKEND_CORS_ORIGINS],
        allow_credentials=True,
        allow_methods=["*"], # Allow all standard methods
        allow_headers=["*"], # Allow all standard headers
    )
else:
    logger.warning("No CORS origins configured. CORS middleware not added.")


# --- API Routers ---
# Include the main API router defined in app/api/api.py
# All routes defined in api_router will be prefixed with /api (or settings.API_V1_STR)
app.include_router(api_router, prefix=settings.API_V1_STR)
logger.info(f"Included API router with prefix: {settings.API_V1_STR}")


# --- Root Endpoint (Optional) ---
@app.get("/", status_code=status.HTTP_200_OK, tags=["Root"], include_in_schema=False)
async def root():
    """
    Simple root endpoint to confirm the API is running.
    """
    logger.debug("Root endpoint '/' called.")
    return {"message": f"Welcome to {settings.PROJECT_NAME} v{settings.VERSION}"}

# --- Health Check (Alternative to separate router) ---
# You could also include the health check directly here if preferred
# from app.api.endpoints.health import HealthResponse # Assuming model exists
# @app.get("/health", response_model=HealthResponse, tags=["Health"])
# async def health_check():
#     return {"status": "ok"}


# --- Main execution block (for local debugging, not used by Gunicorn/Uvicorn directly) ---
if __name__ == "__main__":
    import uvicorn
    logger.info("Running Uvicorn directly for local development...")
    # Note: Lifespan events might behave differently when run this way vs Gunicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000, # Match the port expected locally
        reload=True, # Enable auto-reload for development
        log_level=settings.LOG_LEVEL.lower() # Pass log level to uvicorn
    )