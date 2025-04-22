# backend/app/models/movie.py

from typing import List, Optional, Any
from pydantic import BaseModel, Field, HttpUrl

# --- Base Model ---
class MovieBase(BaseModel):
    """Common attributes for a movie, often used as a base for other models."""
    movieId_ml: Optional[int] = Field(None, description="Original MovieLens ID (ml-latest-small).")
    title: Optional[str] = Field(None, description="Movie title, often includes year.")
    genres: List[str] = Field(default_factory=list, description="List of genres associated with the movie.")
    year: Optional[int] = Field(None, description="Year of release, potentially extracted from title.")

    # Optional enriched fields (add if you populate these during data processing)
    imdbId: Optional[str] = Field(None, description="IMDb ID (from links.csv).")
    tmdbId: Optional[str] = Field(None, description="TMDb ID (from links.csv).")
    overview: Optional[str] = Field(None, description="Movie synopsis/overview (potentially from TMDb).")
    posterUrl: Optional[HttpUrl] = Field(None, description="URL to the movie poster image (potentially from TMDb).")

# --- Models for API Responses ---
class MovieReadSummary(MovieBase):
    """Model for representing a movie summary in list responses (e.g., GET /api/movies)."""
    id: str = Field(..., description="Internal database ID (e.g., MongoDB ObjectId as string).")
    # Exclude fields not needed in summary view if necessary,
    # but inheriting all from MovieBase is often fine.

class MovieReadDetail(MovieBase):
    """Model for representing detailed movie information (e.g., GET /api/movies/{id})."""
    id: str = Field(..., description="Internal database ID.")
    # Includes all fields from MovieBase. Add any other detail-specific fields here.
    # CRUCIALLY, does NOT include the 'embedding' field for API responses.

# --- Model for Internal Use (includes embedding) ---
class MovieInDB(MovieBase):
    """
    Model representing a movie document as stored in the database,
    including the high-dimensional embedding. Used internally by services.
    """
    # Use 'id' if your service layer maps _id to id, or use '_id' directly if needed
    id: str = Field(..., alias="_id", description="Internal database ID (MongoDB ObjectId).")
    embedding: Optional[List[float]] = Field(None, description="High-dimensional content embedding vector.")

    class Config:
        # Pydantic V1: allow_population_by_field_name = True
        # Pydantic V2: populate_by_name = True
        populate_by_name = True # Allows using '_id' field name during population
        from_attributes = True # Allows creating from ORM objects/dicts easily


# --- Model for Paginated API Responses ---
class PaginationData(BaseModel):
    """Metadata for paginated responses."""
    total_items: int
    total_pages: int
    current_page: int
    page_size: int

class PaginatedMovieResponse(BaseModel):
    """Response structure for paginated movie lists."""
    pagination: PaginationData
    items: List[MovieReadSummary]