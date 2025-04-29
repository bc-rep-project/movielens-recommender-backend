#!/usr/bin/env python3
"""
Backup implementation for main.py using Python's built-in web server
if the original FastAPI app fails to load.
"""
import os
import sys
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler
import json

# Set up basic logging
logging.basicConfig(level="INFO", format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("main")

# Constants
PORT = int(os.environ.get("PORT", "8080"))
HOST = "0.0.0.0"

logger.info(f"Fallback server starting on {HOST}:{PORT}")

class SimpleHandler(BaseHTTPRequestHandler):
    def _set_headers(self, content_type="application/json", status=200):
        self.send_response(status)
        self.send_header("Content-type", content_type)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
    
    def do_GET(self):
        try:
            if self.path == "/" or self.path == "":
                self._set_headers()
                response = {
                    "message": "Welcome to MovieLens Recommender API v1.1.0"
                }
                self.wfile.write(json.dumps(response).encode())
            elif self.path == "/health":
                self._set_headers()
                response = {"status": "ok"}
                self.wfile.write(json.dumps(response).encode())
else:
                self._set_headers(status=404)
                response = {"error": "Not found", "path": self.path}
                self.wfile.write(json.dumps(response).encode())
        except Exception as e:
            logger.error(f"Error handling request: {e}")
            self._set_headers(status=500)
            response = {"error": str(e)}
            self.wfile.write(json.dumps(response).encode())
    
    def log_message(self, format, *args):
        logger.info(f"{self.address_string()} - {format % args}")

# Create a simple FastAPI-compatible app object
class DummyApp:
    def __call__(self, scope, receive, send):
        # This is just a placeholder to make it look like a FastAPI/ASGI app
        # It's never actually used because we run the HTTP server directly
        pass
app = DummyApp()

# The application will run from here directly
def run_server():
    try:
        logger.info("Starting HTTP server")
        server = HTTPServer((HOST, PORT), SimpleHandler)
        server.serve_forever()
    except Exception as e:
        logger.critical(f"Server error: {e}")
        sys.exit(1)

# Direct execution (similar to FastAPI apps)
if __name__ == "__main__":
    run_server()