"""
Main entry point for the MovieLens Recommender API - Cloud Run Compatible Version.
This version is specifically designed to work with Cloud Run's default Gunicorn setup.
"""
import os
import json
import datetime
from typing import List, Dict, Any, Optional

from fastapi import FastAPI, Query, Path, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Sample data for testing
SAMPLE_MOVIES = [
    {"id": "tt0111161", "title": "The Shawshank Redemption", "year": 1994, "genres": ["Drama"]},
    {"id": "tt0068646", "title": "The Godfather", "year": 1972, "genres": ["Crime", "Drama"]},
    {"id": "tt0468569", "title": "The Dark Knight", "year": 2008, "genres": ["Action", "Crime", "Drama"]},
    {"id": "tt0071562", "title": "The Godfather: Part II", "year": 1974, "genres": ["Crime", "Drama"]},
    {"id": "tt0050083", "title": "12 Angry Men", "year": 1957, "genres": ["Crime", "Drama"]},
]

# Create application
app = FastAPI(
    title="MovieLens Recommender API",
    version="1.1.0",
    description="MovieLens Recommender API for Cloud Run",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models
class Movie(BaseModel):
    id: str
    title: str
    year: int
    genres: List[str]

class MovieList(BaseModel):
    items: List[Movie]
    total: int
    page: int
    page_size: int

class HealthResponse(BaseModel):
    status: str = "ok"
    timestamp: str = datetime.datetime.now().isoformat()

@app.get("/")
async def root():
    """Root endpoint for basic health check"""
    return {"message": "Welcome to MovieLens Recommender API", "status": "running"}

@app.get("/health")
async def health():
    """Health check endpoint"""
    return HealthResponse()

@app.get("/api/v1/health/health", response_model=HealthResponse)
async def api_health():
    """API health check endpoint"""
    return HealthResponse()

@app.get("/api/v1/movies", response_model=MovieList)
async def list_movies(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(10, ge=1, le=50, description="Results per page"),
    genre: Optional[str] = Query(None, description="Filter by genre")
):
    """List movies with pagination and optional genre filter"""
    filtered_movies = SAMPLE_MOVIES
    
    # Apply genre filter if provided
    if genre:
        filtered_movies = [m for m in filtered_movies if genre in m["genres"]]
    
    # Apply pagination
    start_idx = (page - 1) * limit
    end_idx = start_idx + limit
    paginated_movies = filtered_movies[start_idx:end_idx]
    
    return {
        "items": paginated_movies,
        "total": len(filtered_movies),
        "page": page,
        "page_size": limit
    }

@app.get("/api/v1/movies/{movie_id}", response_model=Movie)
async def get_movie(
    movie_id: str = Path(..., description="The ID of the movie to retrieve")
):
    """Get details for a specific movie"""
    for movie in SAMPLE_MOVIES:
        if movie["id"] == movie_id:
            return movie
    
    raise HTTPException(status_code=404, detail=f"Movie with ID {movie_id} not found")

@app.get("/api/v1/recommendations/item/{movie_id}")
async def get_similar_movies(
    movie_id: str = Path(..., description="The ID of the movie to get recommendations for"),
    limit: int = Query(5, ge=1, le=20, description="Number of recommendations to return")
):
    """Get movies similar to a specified movie"""
    # Check if movie exists
    movie_exists = any(m["id"] == movie_id for m in SAMPLE_MOVIES)
    if not movie_exists:
        raise HTTPException(status_code=404, detail=f"Movie with ID {movie_id} not found")
    
    # Return some sample movies (excluding the requested one)
    recommendations = [m for m in SAMPLE_MOVIES if m["id"] != movie_id][:limit]
    
    return {"recommendations": recommendations}

@app.get("/debug")
async def debug():
    """Debug endpoint that returns various information about the environment"""
    try:
        return {
            "environment": dict(os.environ),
            "current_directory": os.getcwd(),
            "directory_contents": os.listdir(),
            "timestamp": datetime.datetime.now().isoformat()
        }
    except Exception as e:
        return {"error": str(e)}

# For WSGI servers (like Gunicorn's default)
# This is needed for Cloud Run's default startup
wsgi_app = app