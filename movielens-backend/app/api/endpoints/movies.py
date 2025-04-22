# backend/app/api/endpoints/movies.py

import logging
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from motor.motor_asyncio import AsyncIOMotorDatabase

# Assume models are defined like this:
from app.models.movie import MovieReadSummary, MovieReadDetail, PaginatedMovieResponse
# Assume dependencies are defined:
from app.api.deps import get_db
# Assume service is defined:
from app.services.movie_service import MovieService, MovieNotFoundError

logger = logging.getLogger(__name__)
router = APIRouter()

# --- Dependency to get the service ---
def get_movie_service(db: AsyncIOMotorDatabase = Depends(get_db)) -> MovieService:
    return MovieService(db=db)
# --- ---

@router.get(
    "", # GET /api/movies
    response_model=PaginatedMovieResponse,
    tags=["Movies"],
    summary="List Movies",
    description="Retrieve a paginated list of movies, optionally filtered by genre or search term.",
)
async def list_movies(
    search: Optional[str] = Query(None, description="Search term to filter movies by title."),
    genre: Optional[str] = Query(None, description="Filter movies by genre."),
    page: int = Query(1, ge=1, description="Page number."),
    limit: int = Query(20, ge=1, le=100, description="Number of items per page."),
    movie_service: MovieService = Depends(get_movie_service),
):
    """
    Fetches movies with pagination and optional filtering.
    """
    try:
        paginated_result = await movie_service.get_movies(
            search=search, genre=genre, page=page, limit=limit
        )
        return paginated_result
    except Exception as e:
        logger.error(f"Error listing movies: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while retrieving movies."
        )

@router.get(
    "/{movie_id}", # GET /api/movies/{movie_id}
    response_model=MovieReadDetail,
    tags=["Movies"],
    summary="Get Movie Details",
    description="Retrieve detailed information for a specific movie by its ID.",
    responses={
        404: {"description": "Movie not found"},
    }
)
async def get_movie(
    movie_id: str,
    movie_service: MovieService = Depends(get_movie_service),
):
    """
    Fetches detailed information for a single movie using its database ID.
    """
    try:
        movie = await movie_service.get_movie_by_id(movie_id)
        return movie
    except MovieNotFoundError:
        logger.warning(f"Movie not found attempt: ID {movie_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Movie with ID '{movie_id}' not found."
        )
    except Exception as e:
        logger.error(f"Error getting movie {movie_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while retrieving the movie details."
        )