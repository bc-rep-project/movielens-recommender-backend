"""
Simple entry point that directly imports and exposes the FastAPI app
"""
import os
import sys

# Add the current directory to the Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

# Directly import the app from main
try:
    from main import app
    print(f"Successfully imported app from {current_dir}/main.py")
except Exception as e:
    print(f"ERROR importing app from main.py: {e}")
    
    # Debug info
    print("\nDebug information:")
    print(f"Current directory: {os.getcwd()}")
    print(f"Python path: {sys.path}")
    print("\nListing directory contents:")
    
    try:
        files = os.listdir(current_dir)
        for file in files:
            print(f" - {file}")
    except Exception as listing_error:
        print(f"Error listing directory: {listing_error}")
    
    raise

# Expose the app for Gunicorn
application = app

if __name__ == "__main__":
    print("This file is meant to be imported by a WSGI server like Gunicorn.") 