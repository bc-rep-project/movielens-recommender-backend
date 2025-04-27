#!/usr/bin/env python3
"""
Simple WSGI application entry point.
This file should work when imported by Gunicorn or Uvicorn.
"""
import os
import sys
import json

# Create a simple ASGI/WSGI compatible application
async def app(scope, receive, send):
    """
    ASGI application that responds to HTTP requests.
    """
    if scope["type"] != "http":
        return
    
    # Get the path from the scope
    path = scope.get("path", "/")
    
    # Prepare response based on path
    if path == "/" or path == "":
        status = 200
        body = json.dumps({"message": "Welcome to MovieLens Recommender API v1.1.0"})
    elif path == "/health":
        status = 200
        body = json.dumps({"status": "ok"})
    else:
        status = 404
        body = json.dumps({"error": "Not found", "path": path})
    
    # Convert body to bytes
    body_bytes = body.encode("utf-8")
    
    # Send response
    await send({
        "type": "http.response.start",
        "status": status,
        "headers": [
            [b"content-type", b"application/json"],
            [b"content-length", str(len(body_bytes)).encode()],
            [b"access-control-allow-origin", b"*"],
        ],
    })
    
    await send({
        "type": "http.response.body",
        "body": body_bytes,
    })

# For WSGI compatibility (Gunicorn without Uvicorn workers)
def wsgi_app(environ, start_response):
    """
    WSGI compatible application.
    """
    # Get the path from the environment
    path = environ.get("PATH_INFO", "/")
    
    # Prepare response based on path
    if path == "/" or path == "":
        status = "200 OK"
        body = json.dumps({"message": "Welcome to MovieLens Recommender API v1.1.0"})
    elif path == "/health":
        status = "200 OK"
        body = json.dumps({"status": "ok"})
    else:
        status = "404 Not Found"
        body = json.dumps({"error": "Not found", "path": path})
    
    # Convert body to bytes
    body_bytes = body.encode("utf-8")
    
    # Set headers
    headers = [
        ("Content-Type", "application/json"),
        ("Content-Length", str(len(body_bytes))),
        ("Access-Control-Allow-Origin", "*"),
    ]
    
    # Start the response
    start_response(status, headers)
    
    # Return the response body
    return [body_bytes]

# Make the application available as "application" for Gunicorn
application = wsgi_app

# Direct execution with built-in HTTP server
if __name__ == "__main__":
    from http.server import HTTPServer, BaseHTTPRequestHandler
    
    class SimpleHandler(BaseHTTPRequestHandler):
        def _set_headers(self, status=200):
            self.send_response(status)
            self.send_header("Content-type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
        
        def do_GET(self):
            if self.path == "/" or self.path == "":
                self._set_headers()
                response = {"message": "Welcome to MovieLens Recommender API v1.1.0"}
                self.wfile.write(json.dumps(response).encode())
            elif self.path == "/health":
                self._set_headers()
                response = {"status": "ok"}
                self.wfile.write(json.dumps(response).encode())
            else:
                self._set_headers(404)
                response = {"error": "Not found", "path": self.path}
                self.wfile.write(json.dumps(response).encode())
    
    # Get port from environment
    port = int(os.environ.get("PORT", 8080))
    
    # Run server
    server = HTTPServer(("0.0.0.0", port), SimpleHandler)
    print(f"Starting server on port {port}")
    server.serve_forever() 