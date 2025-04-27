#!/bin/bash
set -e

echo "=== DEBUG INFO ==="
echo "Current directory: $(pwd)"
echo "Listing files in current directory:"
ls -la
echo "Listing files in /app:"
ls -la /app
echo "Listing files in /app/app (if it exists):"
if [ -d "/app/app" ]; then
  ls -la /app/app
else
  echo "/app/app directory does not exist!"
fi
echo "Python path: $PYTHONPATH"
echo "Python version: $(python --version)"
echo "Checking for main.py:"
find / -name "main.py" -type f 2>/dev/null || echo "main.py not found in filesystem!"
echo "=== END DEBUG INFO ==="

# Run the Python debug script
echo "Running Python import debug script:"
python /app/debug_import.py

# Try to import the main module in Python to see what happens
echo "Attempting to import 'main' module in Python:"
python -c "import main; print('Successfully imported main')" || echo "Failed to import main module"

# For a more direct approach, try to run the app using the full path to main.py
echo "Trying a more direct approach:"
python -c "import sys; sys.path.insert(0, '/app'); import main; print('main.py exists and can be imported')" || echo "Failed with sys.path approach"

# Try to run with the WSGI file
echo "Testing WSGI file:"
python /app/wsgi.py || echo "Failed to import app through WSGI file"

# Now try to run the application using the WSGI file
echo "Starting Gunicorn server with WSGI file..."
cd /app
exec gunicorn --bind 0.0.0.0:8080 --workers 2 --worker-class uvicorn.workers.UvicornWorker wsgi:application 