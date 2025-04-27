#!/bin/bash
set -ex  # Exit on error, print commands

# Print environment and files for debugging
echo "=== ENVIRONMENT ==="
pwd
ls -la
echo "PYTHONPATH: $PYTHONPATH"
echo "Python version:"
python --version

# Show what's in the main directory
echo "=== MAIN DIRECTORY CONTENTS ==="
ls -la /app
find /app -type f -name "*.py" | sort

# Create a symlink for easier Python path resolution (as a fallback)
echo "=== CREATING PYTHON MODULE SYMLINK ==="
ln -sf /app/main.py /usr/local/lib/python3.10/site-packages/main.py
ln -sf /app/package_app.py /usr/local/lib/python3.10/site-packages/package_app.py

# Set Python path explicitly and to Python's site-packages
export PYTHONPATH=/app:/usr/local/lib/python3.10/site-packages:$PYTHONPATH

# Try to import the main module directly
echo "=== TRYING IMPORTS ==="
python -c "import sys; print(sys.path); import main; print('Successfully imported main')" || echo "Failed to import main"

# Create a fallback server script if all else fails
echo "=== CREATING FALLBACK SERVER SCRIPT ==="
cat > /app/server.py << 'EOF'
import sys
import os
import importlib.util

# Explicitly add the app directory to Python's path
sys.path.insert(0, '/app')

def load_module_from_file(module_name, file_path):
    """Load a module from a file path"""
    print(f"Loading {module_name} from {file_path}")
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec is None:
        raise ImportError(f"Could not load spec for {module_name} from {file_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    sys.modules[module_name] = module
    return module

# Try to load the main module directly from the file
try:
    main_path = '/app/main.py'
    main = load_module_from_file('main', main_path)
    app = main.app
    print("Successfully loaded app from main.py")
except Exception as e:
    print(f"Error loading main.py: {e}")
    sys.exit(1)

# This is used by uvicorn when run with the command:
# uvicorn server:app
if __name__ == "__main__":
    print("Server script loaded successfully")
EOF

# Start with a direct approach - using uvicorn directly
echo "=== STARTING SERVER WITH UVICORN DIRECTLY ==="
cd /app

# Try direct approach first
if python -c "import main" 2>/dev/null; then
    echo "Using direct import method"
    exec uvicorn main:app --host 0.0.0.0 --port 8080
else
    echo "Using fallback server script"
    exec uvicorn server:app --host 0.0.0.0 --port 8080
fi 