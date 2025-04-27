#!/usr/bin/env python3
"""
Minimal web server using Python's built-in http.server.
No external dependencies required.
"""
import os
import sys
import time
import json
from http.server import HTTPServer, BaseHTTPRequestHandler

# Configuration
PORT = int(os.environ.get("PORT", 8080))
HOST = "0.0.0.0"

print(f"Starting minimal web server on {HOST}:{PORT}")
print(f"Python version: {sys.version}")
print(f"Current directory: {os.getcwd()}")
print(f"Files in current directory: {os.listdir('.')}")

class SimpleHandler(BaseHTTPRequestHandler):
    """Simple HTTP request handler with GET support"""
    
    def _set_headers(self, content_type="application/json"):
        self.send_response(200)
        self.send_header("Content-type", content_type)
        self.end_headers()
    
    def do_GET(self):
        """Handle GET requests"""
        if self.path == "/":
            self._set_headers()
            response = {
                "message": "MovieLens API is running (minimal web server)",
                "time": time.time(),
                "path": self.path
            }
            self.wfile.write(json.dumps(response).encode())
            
        elif self.path == "/health":
            self._set_headers()
            response = {"status": "ok"}
            self.wfile.write(json.dumps(response).encode())
            
        elif self.path == "/info":
            self._set_headers()
            response = {
                "system": {
                    "python_version": sys.version,
                    "cwd": os.getcwd(),
                    "path": sys.path,
                    "files": os.listdir("."),
                    "environment": {k: v for k, v in os.environ.items() 
                                  if k in ["PYTHONPATH", "PORT", "PATH", "HOME"]}
                }
            }
            self.wfile.write(json.dumps(response).encode())
            
        else:
            self._set_headers()
            response = {"error": "Not found", "path": self.path}
            self.wfile.write(json.dumps(response).encode())
        
        print(f"Handled request: {self.path}")

def run_server():
    """Run the HTTP server"""
    print(f"Server starting on http://{HOST}:{PORT}")
    server_address = (HOST, PORT)
    httpd = HTTPServer(server_address, SimpleHandler)
    print("Server is running. Press Ctrl+C to stop.")
    httpd.serve_forever()

if __name__ == "__main__":
    run_server() 