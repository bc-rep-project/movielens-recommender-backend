#!/usr/bin/env python3
"""
Enhanced minimal web server using Python's built-in http.server.
Supports both GET and POST requests with JSON parsing and a basic router.
Now with MongoDB integration for data persistence.
"""
import os
import sys
import json
import uuid
import hashlib
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

# Try importing MongoDB client
try:
    import pymongo
    from pymongo import MongoClient
    MONGODB_AVAILABLE = True
except ImportError:
    print("WARNING: pymongo not available. Running without database support.")
    MONGODB_AVAILABLE = False

# Configuration
PORT = int(os.environ.get("PORT", 8080))
HOST = "0.0.0.0"
MONGODB_URI = os.environ.get("MONGODB_URI", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "movielens")

print(f"Starting enhanced server on {HOST}:{PORT}")

# Initialize MongoDB connection
mongodb_client = None
db = None

if MONGODB_AVAILABLE:
    try:
        print(f"Connecting to MongoDB at {MONGODB_URI}...")
        mongodb_client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
        # Validate connection
        mongodb_client.server_info()
        db = mongodb_client[DB_NAME]
        print(f"Successfully connected to MongoDB, using database '{DB_NAME}'")
    except Exception as e:
        print(f"Failed to connect to MongoDB: {e}")
        MONGODB_AVAILABLE = False
        mongodb_client = None
        db = None

# Simple router to map endpoints to handler functions
class Router:
    def __init__(self):
        # Initialize route maps for different HTTP methods
        self.get_routes = {}
        self.post_routes = {}
    
    def add_get_route(self, path, handler):
        """Register a GET route handler"""
        self.get_routes[path] = handler
    
    def add_post_route(self, path, handler):
        """Register a POST route handler"""
        self.post_routes[path] = handler
    
    def get_handler(self, method, path):
        """Get the appropriate handler for a method and path"""
        if method == "GET":
            return self.get_routes.get(path)
        elif method == "POST":
            return self.post_routes.get(path)
        return None

# Create a router instance
router = Router()

class EnhancedHandler(BaseHTTPRequestHandler):
    def _set_headers(self, content_type="application/json", status=200):
        """Set response headers with proper content type and status code"""
        self.send_response(status)
        self.send_header("Content-type", content_type)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
    
    def _send_json_response(self, data, status=200):
        """Helper to send JSON response with proper headers"""
        self._set_headers(status=status)
        self.wfile.write(json.dumps(data).encode())
    
    def _parse_json_body(self):
        """Parse JSON from request body"""
        content_length = int(self.headers.get('Content-Length', 0))
        if content_length > 0:
            try:
                body = self.rfile.read(content_length)
                return json.loads(body.decode('utf-8'))
            except json.JSONDecodeError as e:
                print(f"Error decoding JSON: {e}")
                return None
        return {}
    
    def do_GET(self):
        """Handle GET requests using router"""
        path = self.path.split('?')[0]  # Remove query parameters
        
        # Try to find a registered handler
        handler = router.get_handler("GET", path)
        if handler:
            try:
                handler(self)
            except Exception as e:
                print(f"Error in handler {handler.__name__}: {e}")
                self._send_json_response({
                    "error": "Internal server error",
                    "message": str(e)
                }, status=500)
        else:
            # Default 404 response
            self._send_json_response({
                "error": "Not found", 
                "path": path
            }, status=404)
    
    def do_POST(self):
        """Handle POST requests using router"""
        # Parse the request body as JSON
        body = self._parse_json_body()
        if body is None:  # Invalid JSON
            self._send_json_response({
                "error": "Invalid JSON in request body"
            }, status=400)
            return
        
        # Find and call the appropriate handler
        handler = router.get_handler("POST", self.path)
        if handler:
            try:
                handler(self, body)
            except Exception as e:
                print(f"Error in handler {handler.__name__}: {e}")
                self._send_json_response({
                    "error": "Internal server error",
                    "message": str(e)
                }, status=500)
        else:
            self._send_json_response({
                "error": "Not found or method not allowed", 
                "path": self.path
            }, status=404)
    
    def do_OPTIONS(self):
        """Handle OPTIONS requests for CORS preflight"""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        self.end_headers()

# Authentication helper functions
def hash_password(password, salt=None):
    """Hash a password using SHA-256 with a random salt"""
    if salt is None:
        salt = uuid.uuid4().hex
    hash_obj = hashlib.sha256((password + salt).encode())
    password_hash = hash_obj.hexdigest()
    return {"hash": password_hash, "salt": salt}

def verify_password(password, stored_hash, salt):
    """Verify a password against a stored hash and salt"""
    hash_obj = hashlib.sha256((password + salt).encode())
    password_hash = hash_obj.hexdigest()
    return password_hash == stored_hash

# Define handler functions for specific routes

def handle_root(handler):
    """Handler for the root endpoint (/)"""
    handler._send_json_response({
        "message": "Welcome to MovieLens Recommender API v1.1.0",
        "database_status": "connected" if MONGODB_AVAILABLE else "disconnected"
    })

def handle_health(handler):
    """Handler for the health endpoint (/health)"""
    status = "ok"
    details = {
        "database": "connected" if MONGODB_AVAILABLE else "disconnected"
    }
    
    if MONGODB_AVAILABLE:
        try:
            # Simple ping to check database health
            mongodb_client.admin.command('ping')
        except Exception as e:
            status = "degraded"
            details["database_error"] = str(e)
    
    handler._send_json_response({
        "status": status,
        "details": details
    })

def handle_register(handler, body):
    """Handler for user registration endpoint (/auth/register)"""
    if not body.get('email') or not body.get('password'):
        handler._send_json_response({
            "error": "Email and password are required"
        }, status=400)
        return
    
    email = body.get('email')
    password = body.get('password')
    
    if MONGODB_AVAILABLE:
        # Check if user already exists
        existing_user = db.users.find_one({"email": email})
        if existing_user:
            handler._send_json_response({
                "error": "User with this email already exists"
            }, status=409)
            return
        
        # Hash the password
        password_data = hash_password(password)
        
        # Create user document
        user = {
            "user_id": str(uuid.uuid4()),
            "email": email,
            "password_hash": password_data["hash"],
            "password_salt": password_data["salt"],
            "created_at": int(time.time()),
            "updated_at": int(time.time())
        }
        
        # Insert user into the database
        db.users.insert_one(user)
        
        # Response without password data
        handler._send_json_response({
            "message": "User registered successfully",
            "user_id": user["user_id"],
            "email": user["email"]
        }, status=201)
    else:
        # Fallback when no database is available
        handler._send_json_response({
            "message": "Registration successful (mock mode - no database)",
            "user_id": str(uuid.uuid4()),
            "email": email
        }, status=201)

def handle_login(handler, body):
    """Handler for user login endpoint (/auth/login)"""
    if not body.get('email') or not body.get('password'):
        handler._send_json_response({
            "error": "Email and password are required"
        }, status=400)
        return
    
    email = body.get('email')
    password = body.get('password')
    
    if MONGODB_AVAILABLE:
        # Find user by email
        user = db.users.find_one({"email": email})
        if not user:
            handler._send_json_response({
                "error": "Invalid email or password"
            }, status=401)
            return
        
        # Verify password
        if not verify_password(password, user["password_hash"], user["password_salt"]):
            handler._send_json_response({
                "error": "Invalid email or password"
            }, status=401)
            return
        
        # Generate a simple token (in production, use a proper JWT)
        token = str(uuid.uuid4())
        
        # Store the token in the database (simple session management)
        db.sessions.update_one(
            {"user_id": user["user_id"]},
            {"$set": {
                "token": token,
                "created_at": int(time.time()),
                "expires_at": int(time.time()) + 3600
            }},
            upsert=True
        )
        
        handler._send_json_response({
            "message": "Login successful",
            "session": {
                "access_token": token,
                "token_type": "bearer",
                "expires_in": 3600
            },
            "user": {
                "id": user["user_id"],
                "email": user["email"]
            }
        })
    else:
        # Fallback when no database is available
        handler._send_json_response({
            "message": "Login successful (mock mode - no database)",
            "session": {
                "access_token": str(uuid.uuid4()),
                "token_type": "bearer",
                "expires_in": 3600
            },
            "user": {
                "id": str(uuid.uuid4()),
                "email": email
            }
        })

def handle_movies(handler):
    """Handler for getting movie list (/movies)"""
    # In a real implementation, this would query the database
    # and paginate the results
    
    if MONGODB_AVAILABLE:
        # Get movies from database (limit to 10 for this example)
        movies_list = list(db.movies.find({}, {
            "_id": 0,
            "movieId": 1, 
            "title": 1, 
            "genres": 1
        }).limit(10))
        
        # Check if we found movies
        if not movies_list:
            # If no movies in database, return mock data
            movies_list = [
                {"movieId": 1, "title": "Toy Story (1995)", "genres": ["Adventure", "Animation", "Children", "Comedy", "Fantasy"]},
                {"movieId": 2, "title": "Jumanji (1995)", "genres": ["Adventure", "Children", "Fantasy"]},
                {"movieId": 3, "title": "Grumpier Old Men (1995)", "genres": ["Comedy", "Romance"]}
            ]
    else:
        # Mock data when no database available
        movies_list = [
            {"movieId": 1, "title": "Toy Story (1995)", "genres": ["Adventure", "Animation", "Children", "Comedy", "Fantasy"]},
            {"movieId": 2, "title": "Jumanji (1995)", "genres": ["Adventure", "Children", "Fantasy"]},
            {"movieId": 3, "title": "Grumpier Old Men (1995)", "genres": ["Comedy", "Romance"]}
        ]
    
    handler._send_json_response({
        "movies": movies_list,
        "count": len(movies_list),
        "database_used": MONGODB_AVAILABLE
    })

def handle_recommendations(handler):
    """Handler for movie recommendations (/recommendations)"""
    # In a real implementation, this would look at the user's history
    # and recommend movies based on collaborative filtering
    
    # For now, just return some static recommendations
    recommendations = [
        {"movieId": 260, "title": "Star Wars: Episode IV - A New Hope (1977)", "score": 0.95},
        {"movieId": 1196, "title": "Star Wars: Episode V - The Empire Strikes Back (1980)", "score": 0.94},
        {"movieId": 1210, "title": "Star Wars: Episode VI - Return of the Jedi (1983)", "score": 0.93},
        {"movieId": 2571, "title": "Matrix, The (1999)", "score": 0.92},
        {"movieId": 296, "title": "Pulp Fiction (1994)", "score": 0.91}
    ]
    
    handler._send_json_response({
        "recommendations": recommendations,
        "count": len(recommendations)
    })

# Register routes
router.add_get_route("/", handle_root)
router.add_get_route("", handle_root)  # Also handle empty path
router.add_get_route("/health", handle_health)

# Authentication endpoints
router.add_post_route("/auth/register", handle_register)
router.add_post_route("/auth/login", handle_login)

# Movie endpoints
router.add_get_route("/movies", handle_movies)
router.add_get_route("/recommendations", handle_recommendations)

# Run the HTTP server
def run_server():
    """Start the HTTP server"""
    server = HTTPServer((HOST, PORT), EnhancedHandler)
    print(f"Server running at http://{HOST}:{PORT}/")
    print("Available endpoints:")
    print("  GET  / - Welcome message")
    print("  GET  /health - Service health check")
    print("  POST /auth/register - User registration")
    print("  POST /auth/login - User authentication")
    print("  GET  /movies - Get movie list")
    print("  GET  /recommendations - Get movie recommendations")
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Server stopping...")
    finally:
        if mongodb_client:
            print("Closing database connection...")
            mongodb_client.close()
        server.server_close()
        print("Server stopped.")

if __name__ == "__main__":
    run_server() 