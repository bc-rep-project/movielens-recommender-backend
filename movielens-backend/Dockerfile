# Builds the container image for Cloud Run
# Use an official Python runtime as a parent image
# Choose a specific version for reproducibility (e.g., 3.10 or 3.11)
FROM python:3.10-slim

# Set environment variables
# Prevents Python from writing pyc files to disc (optional)
ENV PYTHONDONTWRITEBYTECODE 1
# Ensures Python output is sent straight to terminal (Docker logs) without buffering
ENV PYTHONUNBUFFERED 1

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
COPY ./app /app/app
COPY ./main.py /app/main.py
# Copy other necessary files or directories if they exist at the backend root

# Expose the port the app runs on (matching the Gunicorn bind port)
# Cloud Run defaults to 8080, but Gunicorn below uses 8000.
# You can either change the port here and in Gunicorn, or configure Cloud Run port.
# Let's use 8000 for this example.
EXPOSE 8000

# Define the command to run the application using Gunicorn as the process manager
# and Uvicorn as the worker.
# -w: Number of workers (adjust based on CPU/memory, can use env var)
# -k: Worker class
# --bind: Address and port to bind to (0.0.0.0 to accept external connections)
# app.main:app: Path to the FastAPI app instance (module:variable)
# Use environment variables for host/port/workers for flexibility
ENV GUNICORN_CMD_ARGS="--bind=0.0.0.0:8000 --workers=2 --worker-class=uvicorn.workers.UvicornWorker"
# CMD gunicorn app.main:app $GUNICORN_CMD_ARGS
# Or specify directly:
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "2", "--worker-class", "uvicorn.workers.UvicornWorker", "app.main:app"]

# Note on Workers: The number of workers (e.g., 2) should be tuned.
# A common starting point is (2 * number_of_cores) + 1.
# For Cloud Run with 1 CPU, 2-4 workers might be reasonable.
# You can set the WORKERS env var in Cloud Run and use it in the CMD:
# CMD ["gunicorn", ..., "--workers", "${WORKERS:-2}", ...]