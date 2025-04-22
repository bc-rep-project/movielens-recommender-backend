# backend/app/api/endpoints/recommendations.py

import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from redis.asyncio import Redis

# Assume models are defined like this:
from app.models.recommendation import RecommendationResponse
# Assume dependencies are defined:
from app.api.deps import get_db, get_redis, get_current_active_user_id
# Assume service is defined:
from app.services.recommendation_service import RecommendationService, RecommendationServiceError
from app.services.movie_service import MovieService # Need this to fetch details for response

logger = logging.getLogger(__name__)
router = APIRouter()

# --- Dependencies to get services ---
# Re-use movie service getter from movies.py or define here
def get_movie_service(db: AsyncIOMotorDatabase = Depends(get_db)) -> MovieService:
    return MovieService(db=db)

def get_recommendation_service(
    db: AsyncIOMotorDatabase = Depends(get_db),
    cache: Redis = Depends(get_redis)
) -> RecommendationService:
    return RecommendationService(db=db, cache=cache)
# --- ---

@router.get(
    "/user/me", # GET /api/recommendations/user/me
    response_model=RecommendationResponse,
    tags=["Recommendations"],
    summary="Get Personalized Recommendations",
    description="Retrieves personalized movie recommendations for the authenticated user based on their interaction history.",
)
async def get_recommendations_for_me(
    limit: int = Query(10, ge=1, le=50, description="Number of recommendations to return."),
    current_user_id: str = Depends(get_current_active_user_id),
    recommendation_service: RecommendationService = Depends(get_recommendation_service),
    movie_service: MovieService = Depends(get_movie_service), # Need movie details for response
):
    """
    Generates content-based recommendations tailored to the authenticated user.
    Requires authentication.
    """
    try:
        # 1. Get recommended movie IDs from the service
        recommended_ids = await recommendation_service.get_content_recommendations_for_user(
            user_id=current_user_id,
            top_n=limit
        )

        if not recommended_ids:
            return RecommendationResponse(recommendations=[]) # Return empty list if no recs

        # 2. Fetch movie details for the recommended IDs to build the response
        # Use the MovieService to get summaries (or details if needed)
        movie_summaries = await movie_service.get_movies_by_ids(recommended_ids)

        # Ensure order is maintained if needed (though ranking is done in service)
        # A simple dict lookup is usually fine here
        movie_map = {str(m.id): m for m in movie_summaries}
        ordered_recommendations = [movie_map[rec_id] for rec_id in recommended_ids if rec_id in movie_map]

        return RecommendationResponse(recommendations=ordered_recommendations)

    except Exception as e:
        logger.error(f"Error generating recommendations for user {current_user_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while generating recommendations."
        )


@router.get(
    "/item/{movie_id}", # GET /api/recommendations/item/{movie_id}
    response_model=RecommendationResponse,
    tags=["Recommendations"],
    summary="Get Similar Movies",
    description="Retrieves movies similar to the specified movie based on content embeddings.",
     responses={
        404: {"description": "Source movie not found"},
    }
)
async def get_similar_movies(
    movie_id: str,
    limit: int = Query(10, ge=1, le=50, description="Number of similar movies to return."),
    recommendation_service: RecommendationService = Depends(get_recommendation_service),
    movie_service: MovieService = Depends(get_movie_service), # Need movie details for response
):
    """
    Generates item-to-item recommendations based on content similarity
    to the provided `movie_id`.
    """
    try:
        # 1. Get similar movie IDs from the service
        similar_ids = await recommendation_service.get_similar_items(
            movie_id=movie_id,
            top_n=limit
        )

        if not similar_ids:
             return RecommendationResponse(recommendations=[])

        # 2. Fetch movie details for the similar IDs
        movie_summaries = await movie_service.get_movies_by_ids(similar_ids)

        # Ensure order is maintained if needed
        movie_map = {str(m.id): m for m in movie_summaries}
        ordered_recommendations = [movie_map[rec_id] for rec_id in similar_ids if rec_id in movie_map]

        return RecommendationResponse(recommendations=ordered_recommendations)

    except RecommendationServiceError as e:
         # Catch specific error if source movie/embedding wasn't found
         logger.warning(f"Cannot get similar items: {e}")
         raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Error generating similar items for movie {movie_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while generating similar items."
        )