# Builds the container image for Cloud Run
# Use an official Python runtime as a parent image
# Choose a specific version for reproducibility (e.g., 3.10 or 3.11)
FROM python:3.10-slim

# Set environment variables
# Prevents Python from writing pyc files to disc (optional)
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Set the working directory in the container
WORKDIR /app

# Install system dependencies if needed (e.g., build-essential for C extensions)
# RUN apt-get update && apt-get install -y --no-install-recommends build-essential && rm -rf /var/lib/apt/lists/*
# Often not needed if using pre-compiled wheels

# Install Python dependencies
# Copy only requirements first to leverage Docker cache
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code into the working directory
# Assumes your FastAPI code is in an 'app' directory and main.py is at the root of 'backend'
COPY . .

# Expose the port the app runs on (matching the Gunicorn bind port)
# Cloud Run expects apps to listen on port 8080 by default
EXPOSE 8080

# Start the application
# Use Gunicorn with Uvicorn workers using the direct path to main.py
CMD ["gunicorn", "main:app", "--bind", "0.0.0.0:8080", "--workers", "2", "--worker-class", "uvicorn.workers.UvicornWorker", "--log-level", "info"]

# Note on Workers: The number of workers (e.g., 2) should be tuned.
# A common starting point is (2 * number_of_cores) + 1.
# For Cloud Run with 1 CPU, 2-4 workers might be reasonable.
# You can set the WORKERS env var in Cloud Run and use it in the CMD:
# CMD ["gunicorn", ..., "--workers", "${WORKERS:-2}", ...]