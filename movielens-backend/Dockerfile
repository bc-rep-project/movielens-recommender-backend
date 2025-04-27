FROM python:3.10-slim

# Set environment variables
ENV PORT=8080
ENV PYTHONUNBUFFERED=1

# Working directory
WORKDIR /app

# Copy the web server script
COPY web_server.py .

# Make it executable
RUN chmod +x /app/web_server.py

# Expose the port
EXPOSE 8080

# Run directly
CMD ["python", "-u", "/app/web_server.py"] 