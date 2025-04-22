# backend/app/services/interaction_service.py

import logging
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any

from motor.motor_asyncio import AsyncIOMotorDatabase
from redis.asyncio import Redis
from redis.exceptions import RedisError
from pymongo.errors import PyMongoError
from bson import ObjectId

# Assume models are defined like this:
from app.models.interaction import (
    InteractionCreate,
    InteractionRead,
    InteractionReadWithMovie,
    PaginatedInteractionsResponse,
    InteractionType
)
# Re-use PaginationData model
from app.models.movie import PaginationData
# Import MovieService error for checking movie existence
from app.services.movie_service import MovieService, MovieNotFoundError # Import service itself if needed

# Import cache key prefix if defined centrally
# from app.core.config import settings # If cache prefixes are in settings
USER_REC_CACHE_PREFIX = "rec:user:" # Define here or import

logger = logging.getLogger(__name__)

class InteractionService:
    def __init__(self, db: AsyncIOMotorDatabase, cache: Redis):
        """
        Initializes the Interaction Service.

        Args:
            db: An instance of AsyncIOMotorDatabase (Motor client).
            cache: An instance of Redis client (redis-py async) for cache invalidation.
        """
        self.db = db
        self.cache = cache
        self.collection = db["interactions"]
        # We need MovieService to validate movie IDs and get titles
        self.movie_service = MovieService(db=db) # Instantiate MovieService

    async def _invalidate_user_rec_cache(self, user_id: str):
        """Invalidates the recommendation cache for a given user."""
        cache_key = f"{USER_REC_CACHE_PREFIX}{user_id}"
        try:
            deleted_count = await self.cache.delete(cache_key)
            if deleted_count > 0:
                logger.info(f"Invalidated recommendation cache for user {user_id} (key: {cache_key}).")
            else:
                 logger.debug(f"No recommendation cache found to invalidate for user {user_id} (key: {cache_key}).")
        except RedisError as e:
            logger.error(f"Redis error invalidating cache for user {user_id}: {e}", exc_info=True)
        except Exception as e:
            logger.error(f"Unexpected error invalidating cache for user {user_id}: {e}", exc_info=True)


    async def create_interaction(self, user_id: str, interaction_data: InteractionCreate) -> InteractionRead:
        """
        Creates a new interaction record for a user and movie.

        Args:
            user_id: The ID of the user performing the interaction.
            interaction_data: Pydantic model containing interaction details (movieId, type, value).

        Returns:
            The created InteractionRead object.

        Raises:
            MovieNotFoundError: If the specified movieId does not exist.
            PyMongoError: If a database error occurs during insertion.
            RedisError: If cache invalidation fails (logged, but doesn't fail the operation).
            ValueError: If interaction data is invalid (e.g., rating value for non-rate type).
        """
        # 1. Validate Movie Existence using MovieService
        try:
            # Fetching the movie also validates the ObjectId format implicitly
            await self.movie_service.get_movie_by_id(interaction_data.movieId)
        except MovieNotFoundError:
            logger.warning(f"Interaction creation failed: Movie ID {interaction_data.movieId} not found.")
            raise # Re-raise the specific error for the endpoint

        # 2. Prepare interaction document
        interaction_doc = interaction_data.model_dump() # Use model_dump in Pydantic v2
        interaction_doc["userId"] = user_id
        interaction_doc["timestamp"] = datetime.now(timezone.utc)
        # Ensure type is stored as string value
        interaction_doc["type"] = interaction_data.type.value

        # Optional: Upsert logic? If a user rates the same movie twice, update or ignore?
        # Current logic inserts a new record each time.
        # For upsert:
        # result = await self.collection.update_one(
        #     {"userId": user_id, "movieId": interaction_data.movieId, "type": interaction_data.type.value},
        #     {"$set": {"value": interaction_data.value, "timestamp": interaction_doc["timestamp"]}},
        #     upsert=True
        # )
        # Need to handle getting the ID back if upserting.

        # 3. Insert into Database
        try:
            insert_result = await self.collection.insert_one(interaction_doc)
            created_id = str(insert_result.inserted_id)
            logger.info(f"Interaction recorded: User {user_id}, Movie {interaction_data.movieId}, Type {interaction_data.type}, ID {created_id}")

            # 4. Invalidate User Recommendation Cache (fire-and-forget or await)
            # A new interaction might change the user's recommendations
            await self._invalidate_user_rec_cache(user_id)

            # 5. Return the created interaction as a Pydantic model
            # Add the generated ID to the document before creating the model
            interaction_doc["id"] = created_id
            return InteractionRead(**interaction_doc)

        except PyMongoError as e:
            logger.error(f"Database error creating interaction for user {user_id}: {e}", exc_info=True)
            raise # Re-raise for endpoint handler

    async def get_interactions_by_user(
        self,
        user_id: str,
        interaction_type: Optional[InteractionType] = None,
        page: int = 1,
        limit: int = 20
    ) -> PaginatedInteractionsResponse:
        """
        Retrieves a paginated list of interactions for a specific user.

        Args:
            user_id: The ID of the user whose interactions to fetch.
            interaction_type: Optional filter for the type of interaction.
            page: Page number (1-based).
            limit: Number of items per page.

        Returns:
            A PaginatedInteractionsResponse object containing interactions enriched with movie titles.

        Raises:
            PyMongoError: If a database error occurs.
        """
        query: Dict[str, Any] = {"userId": user_id}
        if interaction_type:
            query["type"] = interaction_type.value

        skip = (page - 1) * limit

        try:
            total_items_cursor = self.collection.count_documents(query)
            # Sort by timestamp descending to get most recent first
            interactions_cursor = self.collection.find(query).sort("timestamp", -1).skip(skip).limit(limit)

            # Execute queries concurrently
            total_items = await total_items_cursor
            interactions_list_raw = await interactions_cursor.to_list(length=limit)

            # Enrich with movie titles (can be slow if fetching many titles individually)
            # Consider optimizing if performance becomes an issue (e.g., $lookup in aggregation)
            enriched_items: List[InteractionReadWithMovie] = []
            for doc in interactions_list_raw:
                movie_title = await self.movie_service.get_movie_title(doc["movieId"])
                # Create the enriched Pydantic model
                enriched_item = InteractionReadWithMovie(
                    id=str(doc["_id"]),
                    movieTitle=movie_title or "Unknown Title", # Handle missing titles gracefully
                    **doc
                )
                enriched_items.append(enriched_item)

            total_pages = (total_items + limit - 1) // limit
            pagination = PaginationData(
                total_items=total_items,
                total_pages=total_pages,
                current_page=page,
                page_size=limit
            )

            logger.info(f"Fetched {len(enriched_items)} interactions for user {user_id} (page {page}/{total_pages}, total {total_items}) with query: {query}")
            return PaginatedInteractionsResponse(pagination=pagination, items=enriched_items)

        except PyMongoError as e:
            logger.error(f"Database error fetching interactions for user {user_id}: {e}", exc_info=True)
            raise # Re-raise for endpoint handler