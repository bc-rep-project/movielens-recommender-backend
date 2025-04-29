FROM python:3.10-slim

WORKDIR /app

# Copy the entire application
COPY . .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Make run.py executable
RUN chmod +x run.py

# Make sure the application directory is in the Python path
ENV PYTHONPATH="/app:${PYTHONPATH}"

# Expose the port the app runs on
EXPOSE 8080

# Command to run the application
# Primary approach: Run uvicorn through python -m for proper module resolution
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
# Alternative approach (if needed): Use run.py as a fallback
# CMD ["python", "run.py"]
