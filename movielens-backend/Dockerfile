# Builds the container image for Cloud Run
# Use an official Python runtime as a parent image
# Choose a specific version for reproducibility (e.g., 3.10 or 3.11)
FROM python:3.10-slim

# Set environment variables
# Prevents Python from writing pyc files to disc (optional)
ENV PYTHONDONTWRITEBYTECODE=1
# Ensures Python output is sent straight to terminal (Docker logs) without buffering
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Set the working directory in the container
WORKDIR /app

# Install debugging tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    procps \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
# Copy only requirements first to leverage Docker cache
COPY requirements.txt /app/
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir pytest pytest-cov

# Copy the rest of the application code into the working directory
# Assumes your FastAPI code is in an 'app' directory and main.py is at the root of 'backend'
COPY ./app /app/app/
COPY ./main.py /app/
COPY ./run_app.py /app/
# Make the entrypoint script executable
RUN chmod +x /app/run_app.py && \
    # Create a startup message for sanity check
    echo "print('Container is starting up - Python is working!')" > /app/startup_test.py && \
    # Create a healthcheck endpoint
    echo "import os,sys,http.server,socketserver\n\
class HealthHandler(http.server.SimpleHTTPRequestHandler):\n\
    def do_GET(self):\n\
        self.send_response(200)\n\
        self.send_header('Content-type', 'text/plain')\n\
        self.end_headers()\n\
        self.wfile.write(b'Container is running')\n\
\n\
if __name__ == '__main__':\n\
    with socketserver.TCPServer(('', 8081), HealthHandler) as httpd:\n\
        print('Starting healthcheck server on port 8081')\n\
        httpd.serve_forever()" > /app/healthcheck.py

# Expose the port the app runs on (matching the Gunicorn bind port)
# Cloud Run expects apps to listen on port 8080 by default
EXPOSE 8080

# Run the application directly with Python
CMD ["python3", "-u", "/app/run_app.py"]

# Note on Workers: The number of workers (e.g., 2) should be tuned.
# A common starting point is (2 * number_of_cores) + 1.
# For Cloud Run with 1 CPU, 2-4 workers might be reasonable.
# You can set the WORKERS env var in Cloud Run and use it in the CMD:
# CMD ["gunicorn", ..., "--workers", "${WORKERS:-2}", ...]