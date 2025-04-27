#!/usr/bin/env python3
"""
Minimal web server using Python's built-in http.server.
No external dependencies required. This is a fallback implementation
designed to always work, regardless of environment issues.
"""
import os
import sys
import time
import json
import traceback
from http.server import HTTPServer, BaseHTTPRequestHandler

# Configuration
PORT = int(os.environ.get("PORT", 8080))
HOST = "0.0.0.0"

# Print startup info to logs
print(f"[STARTUP] Starting minimal web server on {HOST}:{PORT}")
print(f"[STARTUP] Python version: {sys.version}")
print(f"[STARTUP] Current directory: {os.getcwd()}")
try:
    print(f"[STARTUP] Files in current directory: {os.listdir('.')}")
except Exception as e:
    print(f"[STARTUP] Error listing directory: {e}")

class SimpleHandler(BaseHTTPRequestHandler):
    """Simple HTTP request handler with GET support"""
    
    def log_message(self, format, *args):
        """Override log_message to print to stdout for Cloud Run logs"""
        print(f"[REQUEST] {self.address_string()} - {format % args}")
    
    def _set_headers(self, content_type="application/json", status=200):
        self.send_response(status)
        self.send_header("Content-type", content_type)
        self.send_header("Access-Control-Allow-Origin", "*")  # Allow CORS
        self.end_headers()
    
    def _send_json_response(self, data, status=200):
        """Helper to send JSON response with proper headers"""
        try:
            self._set_headers(status=status)
            self.wfile.write(json.dumps(data).encode())
        except Exception as e:
            print(f"[ERROR] Failed to send response: {e}")
            print(traceback.format_exc())
    
    def do_GET(self):
        """Handle GET requests"""
        try:
            if self.path == "/" or self.path == "":
                self._send_json_response({
                    "message": "Welcome to MovieLens Recommender API v1.1.0"
                })
                
            elif self.path == "/health":
                self._send_json_response({"status": "ok"})
                
            elif self.path == "/info":
                self._send_json_response({
                    "system": {
                        "python_version": sys.version,
                        "cwd": os.getcwd(),
                        "time": time.time(),
                        "environment": {
                            "PORT": os.environ.get("PORT", "8080"),
                            "PYTHONPATH": os.environ.get("PYTHONPATH", "Not set"),
                        }
                    }
                })
                
            else:
                self._send_json_response({
                    "error": "Not found", 
                    "path": self.path
                }, status=404)
                
        except Exception as e:
            print(f"[ERROR] Exception handling request: {e}")
            print(traceback.format_exc())
            self._send_json_response({
                "error": "Internal server error",
                "message": str(e)
            }, status=500)
    
    def do_OPTIONS(self):
        """Handle OPTIONS for CORS preflight requests"""
        self._set_headers()
        self._send_json_response({"status": "ok"})

def run_server():
    """Run the HTTP server"""
    try:
        print(f"[SERVER] Starting server on http://{HOST}:{PORT}")
        server_address = (HOST, PORT)
        httpd = HTTPServer(server_address, SimpleHandler)
        print("[SERVER] Server is running.")
        httpd.serve_forever()
    except Exception as e:
        print(f"[CRITICAL] Server failed to start: {e}")
        print(traceback.format_exc())
        # Exit with error code to make the container restart in Cloud Run
        sys.exit(1)

if __name__ == "__main__":
    try:
        print("[MAIN] Starting server process")
        run_server()
    except Exception as e:
        print(f"[FATAL] Unhandled exception: {e}")
        print(traceback.format_exc())
        sys.exit(1) 