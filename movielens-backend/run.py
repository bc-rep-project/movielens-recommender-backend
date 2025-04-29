#!/usr/bin/env python3
"""
Alternative entry point for the MovieLens Recommender API.
This file helps solve import issues by importing the app directly
and then running uvicorn programmatically.
"""
import os
import sys
import logging

# Add the current directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Configure basic logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

def main():
    """Main entry point for the application"""
    try:
        # Log the Python path to help with debugging
        logger.info(f"Python version: {sys.version}")
        logger.info(f"Current directory: {os.getcwd()}")
        logger.info(f"Files in directory: {os.listdir('.')}")
        logger.info(f"Python path: {sys.path}")
        
        # Try to import the FastAPI app from main.py
        try:
            logger.info("Attempting to import app from main module...")
            from main import app
            logger.info("Successfully imported app from main module")
        except ImportError as e:
            logger.warning(f"Could not import app from main module: {e}")
            logger.info("Attempting to import app from main_simple module...")
            
            # Check if main_simple.py exists
            if os.path.exists('main_simple.py'):
                from main_simple import app
                logger.info("Successfully imported app from main_simple module")
            else:
                logger.error("Both main.py and main_simple.py cannot be imported")
                raise
        
        # Run the app using uvicorn
        import uvicorn
        
        port = int(os.environ.get("PORT", 8080))
        logger.info(f"Starting server on port {port}")
        
        uvicorn.run(
            app,
            host="0.0.0.0",
            port=port,
            log_level="info"
        )
        
    except Exception as e:
        logger.error(f"Error starting application: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main() 