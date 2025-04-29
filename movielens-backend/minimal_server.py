#!/usr/bin/env python3
"""
Minimal web server using Python's built-in http.server.
Now with authentication endpoints (register/login), MongoDB integration,
and protected routes requiring authentication.
"""
import os
import sys
import json
import uuid
import hashlib
import time
from http.server import HTTPServer, BaseHTTPRequestHandler

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

print(f"Starting server on {HOST}:{PORT}")

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
        
        # Create indexes for users collection
        if "users" in db.list_collection_names():
            # Ensure email is unique
            db.users.create_index([("email", pymongo.ASCENDING)], unique=True)
        
        print(f"Successfully connected to MongoDB, using database '{DB_NAME}'")
    except Exception as e:
        print(f"Failed to connect to MongoDB: {e}")
        MONGODB_AVAILABLE = False
        mongodb_client = None
        db = None

# Fallback to in-memory storage if MongoDB is not available
users_db = {}  # email -> user_record
sessions_db = {}  # user_id -> session_info
favorites_db = {}  # user_id -> list of movie_ids

# Authentication middleware
def authenticate_request(handler):
    """Middleware to authenticate a request using token from Authorization header"""
    auth_header = handler.headers.get('Authorization', '')
    
    # Check if Authorization header exists and has the right format
    if not auth_header or not auth_header.startswith('Bearer '):
        return None, "Missing or invalid Authorization header"
    
    # Extract the token
    token = auth_header.split(' ')[1]
    if not token:
        return None, "Empty token"
    
    # Validate the token
    if MONGODB_AVAILABLE:
        try:
            # Find session with this token
            session = db.sessions.find_one({
                "access_token": token,
                "expires_at": {"$gt": int(time.time())}  # Not expired
            })
            
            if not session:
                return None, "Invalid or expired token"
            
            # Get the user
            user = db.users.find_one({"user_id": session["user_id"]})
            if not user:
                return None, "User not found"
            
            # Return the authenticated user
            return user, None
        
        except Exception as e:
            print(f"Error validating token: {e}")
            return None, "Server error during authentication"
    else:
        # In-memory token validation
        for user_id, session in sessions_db.items():
            if session.get("token") == token:
                user = None
                # Find the user by user_id
                for email, u in users_db.items():
                    if u["user_id"] == user_id:
                        user = u
                        break
                
                if user:
                    return user, None
        
        return None, "Invalid token"

# Simple router to map endpoints to handler functions
class Router:
    def __init__(self):
        # Initialize route maps for different HTTP methods
        self.get_routes = {}
        self.post_routes = {}
        self.protected_get_routes = {}
        self.protected_post_routes = {}
    
    def add_get_route(self, path, handler):
        """Register a GET route handler"""
        self.get_routes[path] = handler
    
    def add_post_route(self, path, handler):
        """Register a POST route handler"""
        self.post_routes[path] = handler
    
    def add_protected_get_route(self, path, handler):
        """Register a protected GET route handler requiring authentication"""
        self.protected_get_routes[path] = handler
    
    def add_protected_post_route(self, path, handler):
        """Register a protected POST route handler requiring authentication"""
        self.protected_post_routes[path] = handler
    
    def get_handler(self, method, path):
        """Get the appropriate handler for a method and path"""
        if method == "GET":
            return self.get_routes.get(path)
        elif method == "POST":
            return self.post_routes.get(path)
        return None
    
    def get_protected_handler(self, method, path):
        """Get the appropriate protected handler for a method and path"""
        if method == "GET":
            return self.protected_get_routes.get(path)
        elif method == "POST":
            return self.protected_post_routes.get(path)
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
        
        # Check if this is a protected route
        protected_handler = router.get_protected_handler("GET", path)
        if protected_handler:
            # Authenticate the request
            user, error = authenticate_request(self)
            if error:
                self._send_json_response({
                    "detail": error
                }, status=401)
                return
            
            # Call the protected handler with the authenticated user
            try:
                protected_handler(self, user)
            except Exception as e:
                print(f"Error in protected handler {protected_handler.__name__}: {e}")
                self._send_json_response({
                    "error": "Internal server error",
                    "message": str(e)
                }, status=500)
            return
        
        # Not a protected route, try regular routes
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
        
        path = self.path.split('?')[0]  # Remove query parameters
        
        # Check if this is a protected route
        protected_handler = router.get_protected_handler("POST", path)
        if protected_handler:
            # Authenticate the request
            user, error = authenticate_request(self)
            if error:
                self._send_json_response({
                    "detail": error
                }, status=401)
                return
            
            # Call the protected handler with the authenticated user and request body
            try:
                protected_handler(self, user, body)
            except Exception as e:
                print(f"Error in protected handler {protected_handler.__name__}: {e}")
                self._send_json_response({
                    "error": "Internal server error",
                    "message": str(e)
                }, status=500)
            return
        
        # Not a protected route, try regular routes
        handler = router.get_handler("POST", path)
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
                "path": path
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

# Email validation
def is_valid_email(email):
    """Simple email validation"""
    # This is a very basic check, in production use a proper regex
    return '@' in email and '.' in email.split('@')[1]

# Password validation
def is_valid_password(password):
    """Check if password meets requirements"""
    # In a real app, enforce stronger requirements
    return len(password) >= 6

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
    # Input validation
    if not body.get('email') or not body.get('password'):
        handler._send_json_response({
            "detail": "Email and password are required"
        }, status=422)
        return
    
    email = body.get('email')
    password = body.get('password')
    
    # Validate email format
    if not is_valid_email(email):
        handler._send_json_response({
            "detail": [
                {
                    "loc": ["body", "email"],
                    "msg": "value is not a valid email address",
                    "type": "value_error.email"
                }
            ]
        }, status=422)
        return
    
    # Validate password requirements
    if not is_valid_password(password):
        handler._send_json_response({
            "detail": [
                {
                    "loc": ["body", "password"],
                    "msg": "Password must be at least 6 characters",
                    "type": "value_error"
                }
            ]
        }, status=422)
        return
    
    # Hash the password
    password_data = hash_password(password)
    
    # Create user record
    user_id = str(uuid.uuid4())
    user = {
        "user_id": user_id,
        "email": email,
        "password_hash": password_data["hash"],
        "password_salt": password_data["salt"],
        "created_at": int(time.time()),
        "updated_at": int(time.time())
    }
    
    if MONGODB_AVAILABLE:
        try:
            # Check if user already exists
            existing_user = db.users.find_one({"email": email})
            if existing_user:
                handler._send_json_response({
                    "detail": f"User with email {email} already exists."
                }, status=409)
                return
            
            # Insert user into database
            result = db.users.insert_one(user)
            
            # Return success response
            handler._send_json_response({
                "message": "Registration successful. Please check your email for verification.",
                "user_id": user_id,
                "email": email
            }, status=201)
        except pymongo.errors.DuplicateKeyError:
            # Handle race condition where user might be created between check and insert
            handler._send_json_response({
                "detail": f"User with email {email} already exists."
            }, status=409)
        except Exception as e:
            print(f"Database error during registration: {e}")
            handler._send_json_response({
                "error": "Internal server error",
                "message": "Unable to complete registration"
            }, status=500)
    else:
        # Fallback to in-memory storage
        if email in users_db:
            handler._send_json_response({
                "detail": f"User with email {email} already exists."
            }, status=409)
            return
        
        # Store user in our in-memory database
        users_db[email] = user
        
        # Return success response (mock mode)
        handler._send_json_response({
            "message": "User registered successfully (mock)",
            "user_id": user_id,
            "email": email
        }, status=201)

def handle_login(handler, body):
    """Handler for user login endpoint (/auth/login)"""
    # Input validation
    if not body.get('email') or not body.get('password'):
        handler._send_json_response({
            "detail": "Email and password are required"
        }, status=422)
        return
    
    email = body.get('email')
    password = body.get('password')
    
    if MONGODB_AVAILABLE:
        try:
            # Find user by email
            user = db.users.find_one({"email": email})
            if not user:
                handler._send_json_response({
                    "detail": "Invalid email or password."
                }, status=401)
                return
            
            # Verify password
            if not verify_password(password, user["password_hash"], user["password_salt"]):
                handler._send_json_response({
                    "detail": "Invalid email or password."
                }, status=401)
                return
            
            # Generate a simple token
            access_token = str(uuid.uuid4())
            refresh_token = str(uuid.uuid4())
            
            # Store session in database
            session = {
                "user_id": user["user_id"],
                "access_token": access_token,
                "refresh_token": refresh_token,
                "created_at": int(time.time()),
                "expires_at": int(time.time()) + 3600  # 1 hour
            }
            
            # Store session in database
            db.sessions.update_one(
                {"user_id": user["user_id"]},
                {"$set": session},
                upsert=True
            )
            
            # Return success response
            handler._send_json_response({
                "session": {
                    "access_token": access_token,
                    "refresh_token": refresh_token,
                    "token_type": "bearer",
                    "expires_in": 3600  # 1 hour
                },
                "user": {
                    "id": user["user_id"],
                    "email": user["email"],
                    "full_name": user.get("full_name"),
                    "avatar_url": user.get("avatar_url"),
                    "roles": ["authenticated"]
                }
            })
        except Exception as e:
            print(f"Database error during login: {e}")
            handler._send_json_response({
                "error": "Internal server error",
                "message": "Unable to process login"
            }, status=500)
    else:
        # Fallback to in-memory storage
        user = users_db.get(email)
        if not user:
            handler._send_json_response({
                "detail": "Invalid email or password."
            }, status=401)
            return
        
        # Verify password
        if not verify_password(password, user["password_hash"], user["password_salt"]):
            handler._send_json_response({
                "detail": "Invalid email or password."
            }, status=401)
            return
        
        # Generate token
        token = str(uuid.uuid4())
        
        # Store session in memory
        sessions_db[user["user_id"]] = {
            "token": token,
            "created_at": int(time.time())
        }
        
        # Return success response (mock mode)
        handler._send_json_response({
            "message": "Login successful (mock)",
            "token": token,
            "user": {
                "id": user["user_id"],
                "email": user["email"]
            }
        })

# Protected endpoint handlers
def handle_profile(handler, user):
    """Protected handler to get the authenticated user's profile (/profile)"""
    # Return the user's profile information (exclude sensitive data)
    profile = {
        "id": user["user_id"],
        "email": user["email"],
        "full_name": user.get("full_name"),
        "avatar_url": user.get("avatar_url"),
        "created_at": user.get("created_at")
    }
    
    handler._send_json_response({
        "profile": profile
    })

def handle_update_profile(handler, user, body):
    """Protected handler to update user profile (/profile)"""
    # Fields that can be updated
    updateable_fields = ["full_name", "avatar_url"]
    
    # Create update object with only allowed fields
    updates = {}
    for field in updateable_fields:
        if field in body:
            updates[field] = body[field]
    
    # Add updated_at timestamp
    updates["updated_at"] = int(time.time())
    
    if not updates:
        handler._send_json_response({
            "detail": "No valid fields to update"
        }, status=400)
        return
    
    if MONGODB_AVAILABLE:
        try:
            # Update user in database
            result = db.users.update_one(
                {"user_id": user["user_id"]},
                {"$set": updates}
            )
            
            # Get updated user
            updated_user = db.users.find_one({"user_id": user["user_id"]})
            
            # Return success response
            handler._send_json_response({
                "message": "Profile updated successfully",
                "profile": {
                    "id": updated_user["user_id"],
                    "email": updated_user["email"],
                    "full_name": updated_user.get("full_name"),
                    "avatar_url": updated_user.get("avatar_url"),
                    "updated_at": updated_user.get("updated_at")
                }
            })
        except Exception as e:
            print(f"Database error updating profile: {e}")
            handler._send_json_response({
                "error": "Internal server error",
                "message": "Unable to update profile"
            }, status=500)
    else:
        # In-memory update
        for field, value in updates.items():
            users_db[user["email"]][field] = value
        
        users_db[user["email"]]["updated_at"] = updates["updated_at"]
        
        # Return updated profile
        updated_user = users_db[user["email"]]
        handler._send_json_response({
            "message": "Profile updated successfully",
            "profile": {
                "id": updated_user["user_id"],
                "email": updated_user["email"],
                "full_name": updated_user.get("full_name"),
                "avatar_url": updated_user.get("avatar_url"),
                "updated_at": updated_user.get("updated_at")
            }
        })

def handle_favorites(handler, user):
    """Protected handler to get user's favorite movies (/favorites)"""
    if MONGODB_AVAILABLE:
        try:
            # Get user's favorites from database
            favorites = db.favorites.find_one({"user_id": user["user_id"]})
            
            if not favorites or "movie_ids" not in favorites:
                # User has no favorites yet
                handler._send_json_response({
                    "favorites": [],
                    "count": 0
                })
                return
            
            # Get details for each favorited movie
            movie_ids = favorites["movie_ids"]
            if len(movie_ids) > 0:
                movies = list(db.movies.find({
                    "movieId": {"$in": movie_ids}
                }, {
                    "_id": 0,
                    "movieId": 1,
                    "title": 1,
                    "genres": 1
                }))
                
                # Sort movies in the same order as movie_ids
                movie_dict = {movie["movieId"]: movie for movie in movies}
                sorted_movies = [movie_dict.get(movie_id) for movie_id in movie_ids if movie_id in movie_dict]
                
                handler._send_json_response({
                    "favorites": sorted_movies,
                    "count": len(sorted_movies)
                })
            else:
                handler._send_json_response({
                    "favorites": [],
                    "count": 0
                })
        except Exception as e:
            print(f"Database error getting favorites: {e}")
            handler._send_json_response({
                "error": "Internal server error",
                "message": "Unable to retrieve favorites"
            }, status=500)
    else:
        # In-memory favorites
        user_id = user["user_id"]
        favorites_list = favorites_db.get(user_id, [])
        
        # Mock movie data (in a real app, you'd look these up in a movie database)
        mock_movies = [
            {"movieId": 1, "title": "Toy Story (1995)", "genres": ["Adventure", "Animation", "Children"]},
            {"movieId": 2, "title": "Jumanji (1995)", "genres": ["Adventure", "Children", "Fantasy"]},
            {"movieId": 3, "title": "Grumpier Old Men (1995)", "genres": ["Comedy", "Romance"]}
        ]
        
        # Filter to only include favorited movies
        favorites = [movie for movie in mock_movies if movie["movieId"] in favorites_list]
        
        handler._send_json_response({
            "favorites": favorites,
            "count": len(favorites)
        })

def handle_add_favorite(handler, user, body):
    """Protected handler to add a movie to favorites (/favorites)"""
    # Validate input
    if "movie_id" not in body:
        handler._send_json_response({
            "detail": "movie_id is required"
        }, status=400)
        return
    
    movie_id = body["movie_id"]
    user_id = user["user_id"]
    
    if MONGODB_AVAILABLE:
        try:
            # Check if movie exists
            movie = db.movies.find_one({"movieId": movie_id})
            if not movie:
                handler._send_json_response({
                    "detail": f"Movie with id {movie_id} not found"
                }, status=404)
                return
            
            # Add to favorites using $addToSet to avoid duplicates
            db.favorites.update_one(
                {"user_id": user_id},
                {"$addToSet": {"movie_ids": movie_id}},
                upsert=True
            )
            
            handler._send_json_response({
                "message": "Movie added to favorites",
                "movie_id": movie_id
            })
        except Exception as e:
            print(f"Database error adding favorite: {e}")
            handler._send_json_response({
                "error": "Internal server error",
                "message": "Unable to add favorite"
            }, status=500)
    else:
        # In-memory favorites
        if user_id not in favorites_db:
            favorites_db[user_id] = []
        
        if movie_id not in favorites_db[user_id]:
            favorites_db[user_id].append(movie_id)
        
        handler._send_json_response({
            "message": "Movie added to favorites",
            "movie_id": movie_id
        })

def handle_remove_favorite(handler, user, body):
    """Protected handler to remove a movie from favorites (/favorites/remove)"""
    # Validate input
    if "movie_id" not in body:
        handler._send_json_response({
            "detail": "movie_id is required"
        }, status=400)
        return
    
    movie_id = body["movie_id"]
    user_id = user["user_id"]
    
    if MONGODB_AVAILABLE:
        try:
            # Remove from favorites
            db.favorites.update_one(
                {"user_id": user_id},
                {"$pull": {"movie_ids": movie_id}}
            )
            
            handler._send_json_response({
                "message": "Movie removed from favorites",
                "movie_id": movie_id
            })
        except Exception as e:
            print(f"Database error removing favorite: {e}")
            handler._send_json_response({
                "error": "Internal server error",
                "message": "Unable to remove favorite"
            }, status=500)
    else:
        # In-memory favorites
        if user_id in favorites_db and movie_id in favorites_db[user_id]:
            favorites_db[user_id].remove(movie_id)
        
        handler._send_json_response({
            "message": "Movie removed from favorites",
            "movie_id": movie_id
        })

# Register public routes
router.add_get_route("/", handle_root)
router.add_get_route("", handle_root)  # Also handle empty path
router.add_get_route("/health", handle_health)

# Register authentication endpoints
router.add_post_route("/auth/register", handle_register)
router.add_post_route("/auth/login", handle_login)

# Register protected routes
router.add_protected_get_route("/profile", handle_profile)
router.add_protected_post_route("/profile", handle_update_profile)
router.add_protected_get_route("/favorites", handle_favorites)
router.add_protected_post_route("/favorites", handle_add_favorite)
router.add_protected_post_route("/favorites/remove", handle_remove_favorite)

# Run the HTTP server
server = HTTPServer((HOST, PORT), EnhancedHandler)
print("Server is running...")
print("Available endpoints:")
print("  GET  / - Welcome message")
print("  GET  /health - Service health check")
print("  POST /auth/register - User registration")
print("  POST /auth/login - User authentication")
print("Protected endpoints (require authentication):")
print("  GET  /profile - Get user profile")
print("  POST /profile - Update user profile")
print("  GET  /favorites - Get favorite movies")
print("  POST /favorites - Add a movie to favorites")
print("  POST /favorites/remove - Remove a movie from favorites")

try:
    server.serve_forever()
except KeyboardInterrupt:
    print("Server stopping...")
finally:
    # Close MongoDB connection when server stops
    if mongodb_client:
        print("Closing database connection...")
        mongodb_client.close()
    server.server_close()
    print("Server stopped.")
