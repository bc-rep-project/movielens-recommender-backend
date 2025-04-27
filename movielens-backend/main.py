"""
Main entry point - imports the FastAPI app from app.server module
This file exists for backward compatibility
"""
import sys
import logging

# Configure basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    # Import the application from the app.server module
    from app.server import app

    # Log successful import
    logger.info("Successfully imported app from app.server")
except ImportError as e:
    # Log import error
    logger.error(f"Error importing app from app.server: {e}")
    raise

# If this file is run directly
if __name__ == "__main__":
    import uvicorn
    logger.info("Running application directly with uvicorn")
    uvicorn.run("app.server:app", host="0.0.0.0", port=8080)