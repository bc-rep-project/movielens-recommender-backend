"""
WSGI entry point that creates a simple application.
"""
import os
import sys
import json
from http.server import HTTPServer, BaseHTTPRequestHandler
import socket

# Alternative application for WSGI servers (gunicorn/uvicorn)
def create_app():
    # Simple WSGI application callable
    def app(environ, start_response):
        # Get the request path
        path = environ.get('PATH_INFO', '/')
        
        # Generate response content
        if path == '/':
            status = '200 OK'
            content = json.dumps({
                "message": "Welcome to MovieLens Recommender API v1.1.0"
            })
        elif path == '/health':
            status = '200 OK'
            content = json.dumps({"status": "ok"})
        else:
            status = '404 Not Found'
            content = json.dumps({"error": "Not found", "path": path})
        
        # Encode response to bytes
        content_bytes = content.encode('utf-8')
        
        # Create response headers
        response_headers = [
            ('Content-Type', 'application/json'),
            ('Content-Length', str(len(content_bytes))),
            ('Access-Control-Allow-Origin', '*'),
        ]
        
        # Start the response
        start_response(status, response_headers)
        
        # Return the response body
        return [content_bytes]
    
    return app

# Create the application
application = create_app()

# For direct execution
if __name__ == "__main__":
    print("This module is meant to be imported by a WSGI server.")
    print("For testing, you can run: gunicorn wsgi:application") 