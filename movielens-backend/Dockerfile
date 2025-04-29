FROM python:3.9-slim

# Set working directory
WORKDIR /app

# Copy application code and requirements
COPY main.py .
COPY requirements-minimal.txt requirements.txt

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Configure for Cloud Run
ENV PORT=8080
ENV PYTHONUNBUFFERED=TRUE

# Expose port for Cloud Run
EXPOSE 8080

# Use Gunicorn as the entry point
CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 0 main:app
