FROM python:3.10-slim

# Set environment variables
ENV PORT=8080
ENV PYTHONUNBUFFERED=1

# Working directory
WORKDIR /app

# Create the web server directly in the Dockerfile
RUN echo '#!/usr/bin/env python3\n\
import os\n\
import sys\n\
import time\n\
import json\n\
from http.server import HTTPServer, BaseHTTPRequestHandler\n\
\n\
# Configuration\n\
PORT = int(os.environ.get("PORT", 8080))\n\
HOST = "0.0.0.0"\n\
\n\
print(f"Starting server on {HOST}:{PORT}")\n\
print(f"Python version: {sys.version}")\n\
\n\
class SimpleHandler(BaseHTTPRequestHandler):\n\
    def _set_headers(self, status=200):\n\
        self.send_response(status)\n\
        self.send_header("Content-type", "application/json")\n\
        self.send_header("Access-Control-Allow-Origin", "*")\n\
        self.end_headers()\n\
    \n\
    def do_GET(self):\n\
        if self.path == "/" or self.path == "":\n\
            self._set_headers()\n\
            response = {\n\
                "message": "Welcome to MovieLens Recommender API v1.1.0"\n\
            }\n\
            self.wfile.write(json.dumps(response).encode())\n\
        elif self.path == "/health":\n\
            self._set_headers()\n\
            response = {"status": "ok"}\n\
            self.wfile.write(json.dumps(response).encode())\n\
        else:\n\
            self._set_headers(404)\n\
            response = {"error": "Not found", "path": self.path}\n\
            self.wfile.write(json.dumps(response).encode())\n\
\n\
def run_server():\n\
    server_address = (HOST, PORT)\n\
    httpd = HTTPServer(server_address, SimpleHandler)\n\
    print("Server is running...")\n\
    httpd.serve_forever()\n\
\n\
if __name__ == "__main__":\n\
    run_server()\n\
' > /app/server.py

# Create app.py as a WSGI entry point
RUN echo '#!/usr/bin/env python3\n\
import os, json\n\
# For WSGI compatibility\n\
def application(environ, start_response):\n\
    path = environ.get("PATH_INFO", "/")\n\
    if path == "/" or path == "":\n\
        status = "200 OK"\n\
        body = json.dumps({"message": "Welcome to MovieLens Recommender API v1.1.0"})\n\
    elif path == "/health":\n\
        status = "200 OK"\n\
        body = json.dumps({"status": "ok"})\n\
    else:\n\
        status = "404 Not Found"\n\
        body = json.dumps({"error": "Not found", "path": path})\n\
    body_bytes = body.encode("utf-8")\n\
    headers = [\n\
        ("Content-Type", "application/json"),\n\
        ("Content-Length", str(len(body_bytes))),\n\
        ("Access-Control-Allow-Origin", "*"),\n\
    ]\n\
    start_response(status, headers)\n\
    return [body_bytes]\n\
\n\
# Export for various frameworks\n\
wsgi_app = application\n\
app = application\n\
' > /app/app.py

# Create main.py as a final fallback
RUN echo 'import os, sys, json\n\
from http.server import HTTPServer, BaseHTTPRequestHandler\n\
class Handler(BaseHTTPRequestHandler):\n\
    def do_GET(self):\n\
        self.send_response(200)\n\
        self.send_header("Content-type", "application/json")\n\
        self.end_headers()\n\
        if self.path == "/" or self.path == "":\n\
            self.wfile.write(b\'{"message": "Welcome to MovieLens Recommender API v1.1.0"}\');\n\
        else:\n\
            self.wfile.write(b\'{"status": "ok"}\');\n\
\n\
# For WSGI compatibility\n\
def application(environ, start_response):\n\
    status = "200 OK"\n\
    body = b\'{"message": "Welcome to MovieLens Recommender API v1.1.0"}\'\n\
    headers = [("Content-Type", "application/json"), ("Content-Length", str(len(body)))]\n\
    start_response(status, headers)\n\
    return [body]\n\
\n\
# Simple app for ASGI frameworks\n\
async def app(scope, receive, send):\n\
    await send({"type": "http.response.start", "status": 200, "headers": [[b"content-type", b"application/json"]]})\n\
    await send({"type": "http.response.body", "body": b\'{"message": "Welcome to MovieLens Recommender API v1.1.0"}\'})\n\
\n\
# Only run server if executed directly\n\
if __name__ == "__main__":\n\
    port = int(os.environ.get("PORT", "8080"))\n\
    httpd = HTTPServer(("0.0.0.0", port), Handler)\n\
    httpd.serve_forever()\n\
' > /app/main.py

# Make all scripts executable
RUN chmod +x /app/server.py /app/app.py /app/main.py

# Install minimal dependencies
RUN pip install --no-cache-dir gunicorn

# Expose the port
EXPOSE 8080

# Multiple options for running the app, in order of preference
# 1. Direct Python HTTP server (most reliable)
# 2. Gunicorn with app.py
# 3. Python with main.py
CMD python -u /app/server.py || gunicorn --bind 0.0.0.0:8080 app || python -u /app/main.py 