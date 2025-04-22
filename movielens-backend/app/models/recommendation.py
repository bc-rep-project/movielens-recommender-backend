# backend/app/models/recommendation.py

from typing import List, Optional

from pydantic import BaseModel, Field

# Import the movie summary model to represent recommended items
from .movie import MovieReadSummary

class RecommendationResponse(BaseModel):
    """
    Standard response structure for recommendation endpoints
    (e.g., GET /api/recommendations/user/me, GET /api/recommendations/item/{id}).
    """
    # Optional metadata about the request/response
    request_id: Optional[str] = Field(None, description="Unique identifier for the request (optional).")
    type: Optional[str] = Field(None, description="Type of recommendation generated (e.g., 'user_content', 'item_similar').")
    user_id: Optional[str] = Field(None, description="User ID for personalized recommendations.")
    source_movie_id: Optional[str] = Field(None, description="Source movie ID for item-based similarity.")

    # The core list of recommended movies
    recommendations: List[MovieReadSummary] = Field(
        default_factory=list,
        description="List of recommended movies, ordered by relevance."
    )