FROM python:3.10-slim

WORKDIR /app
COPY minimal_server.py .

# Install pymongo for database connectivity
RUN pip install --no-cache-dir pymongo

# Make script executable
RUN chmod +x /app/minimal_server.py

EXPOSE 8080
CMD ["python", "-u", "/app/minimal_server.py"]
