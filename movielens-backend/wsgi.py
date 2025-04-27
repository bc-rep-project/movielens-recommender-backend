"""
WSGI entry point for Gunicorn
This file imports the FastAPI app from main.py and makes it available as 'application'
"""
import os
import sys

# Ensure Python can find modules in the current directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import the app from main.py
try:
    from main import app as application
    print("Successfully imported app from main.py")
except ImportError as e:
    print(f"ERROR: Failed to import app from main.py: {str(e)}")
    raise

# Make the app available for Gunicorn
if __name__ == "__main__":
    print("This module is designed to be imported by Gunicorn, not run directly.") 