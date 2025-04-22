# backend/app/api/endpoints/interactions.py

import logging
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from redis.asyncio import Redis # Import Redis if needed for cache invalidation

# Assume models are defined like this:
from app.models.interaction import (
    InteractionCreate,
    InteractionRead,
    InteractionReadWithMovie,
    PaginatedInteractionsResponse,
    InteractionType
)
# Assume dependencies are defined:
from app.api.deps import get_db, get_redis, get_current_active_user_id
# Assume service is defined:
from app.services.interaction_service import InteractionService
from app.services.movie_service import MovieNotFoundError # If service checks movie exists

logger = logging.getLogger(__name__)
router = APIRouter()

# --- Dependency to get the service ---
def get_interaction_service(
    db: AsyncIOMotorDatabase = Depends(get_db),
    cache: Redis = Depends(get_redis) # Inject cache if service invalidates it
) -> InteractionService:
    # Pass cache to service if it needs it
    return InteractionService(db=db, cache=cache)
# --- ---

@router.post(
    "", # POST /api/interactions
    response_model=InteractionRead,
    status_code=status.HTTP_201_CREATED,
    tags=["Interactions"],
    summary="Record User Interaction",
    description="Records an interaction (like rating or viewing) the authenticated user has with a movie.",
    responses={
        404: {"description": "Movie specified in interaction not found"},
        422: {"description": "Validation Error (e.g., invalid rating value)"}
    }
)
async def create_interaction(
    interaction_data: InteractionCreate,
    current_user_id: str = Depends(get_current_active_user_id),
    interaction_service: InteractionService = Depends(get_interaction_service),
):
    """
    Records a new interaction between the authenticated user and a movie.

    Requires authentication. User ID is derived from the token.
    """
    try:
        created_interaction = await interaction_service.create_interaction(
            user_id=current_user_id,
            interaction_data=interaction_data
        )
        return created_interaction
    except MovieNotFoundError as e:
        # If the service raises this specific error when movie doesn't exist
        logger.warning(f"Interaction creation failed: Movie not found - {e}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e: # Catch potential validation errors from service/model
        logger.warning(f"Interaction creation validation error: {e}", exc_info=True)
        # FastAPI might handle Pydantic validation errors automatically with 422,
        # but catch others that might bubble up.
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating interaction for user {current_user_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while recording the interaction."
        )

@router.get(
    "/me", # GET /api/interactions/me
    response_model=PaginatedInteractionsResponse,
    tags=["Interactions"],
    summary="Get My Interactions",
    description="Retrieves the interaction history for the currently authenticated user, ordered by most recent first.",
)
async def get_my_interactions(
    interaction_type: Optional[InteractionType] = Query(None, alias="type", description="Filter by interaction type."),
    page: int = Query(1, ge=1, description="Page number."),
    limit: int = Query(20, ge=1, le=100, description="Number of interactions per page."),
    current_user_id: str = Depends(get_current_active_user_id),
    interaction_service: InteractionService = Depends(get_interaction_service),
):
    """
    Fetches a paginated list of the authenticated user's interactions.
    Requires authentication.
    """
    try:
        interactions_page = await interaction_service.get_interactions_by_user(
            user_id=current_user_id,
            interaction_type=interaction_type,
            page=page,
            limit=limit
        )
        return interactions_page
    except Exception as e:
        logger.error(f"Error retrieving interactions for user {current_user_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while retrieving interactions."
        )