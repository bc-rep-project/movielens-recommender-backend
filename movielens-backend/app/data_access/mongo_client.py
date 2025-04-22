# MongoDB connection and repository logic
# backend/app/data_access/mongo_client.py

import logging
from typing import List, Optional, Dict, Any

from motor.motor_asyncio import AsyncIOMotorDatabase, AsyncIOMotorCollection
from pymongo.errors import PyMongoError
from bson import ObjectId

# Import relevant Pydantic models used for type hinting and data validation/mapping
# These models define the structure expected from/sent to the DB
from app.models.movie import MovieInDB, MovieReadSummary # Example imports
from app.models.interaction import InteractionRead # Example import

logger = logging.getLogger(__name__)

# --- Base Repository (Optional) ---
class BaseRepository:
    """Optional base class for common repository logic."""
    def __init__(self, db: AsyncIOMotorDatabase, collection_name: str):
        self.db = db
        self.collection: AsyncIOMotorCollection = db[collection_name]
        logger.debug(f"Initialized repository for collection: {collection_name}")

    def _check_db(self):
        """Helper to check if DB instance is available."""
        if self.db is None or self.collection is None:
             # This should ideally not happen if dependencies are set up correctly
             logger.critical(f"Database not available for collection {self.collection.name if self.collection else 'N/A'}")
             raise ConnectionError(f"Database connection not available for {self.collection.name if self.collection else 'N/A'}")

    def _validate_object_id(self, id_str: str) -> Optional[ObjectId]:
        """Validates a string as a MongoDB ObjectId."""
        if ObjectId.is_valid(id_str):
            return ObjectId(id_str)
        logger.warning(f"Invalid ObjectId format: {id_str}")
        return None

# --- Movie Repository ---
class MovieRepository(BaseRepository):
    def __init__(self, db: AsyncIOMotorDatabase):
        super().__init__(db, collection_name="movies")

    async def find_by_id(self, movie_id: str) -> Optional[MovieInDB]:
        """Finds a single movie by its MongoDB ObjectId string."""
        self._check_db()
        obj_id = self._validate_object_id(movie_id)
        if not obj_id:
            return None
        try:
            doc = await self.collection.find_one({"_id": obj_id})
            if doc:
                # Use MovieInDB which expects _id and embedding
                return MovieInDB.model_validate(doc) # Pydantic V2 (v1: parse_obj)
            return None
        except PyMongoError as e:
            logger.error(f"DB error finding movie by ID {movie_id}: {e}", exc_info=True)
            raise # Re-raise for service layer to handle

    async def find_by_ids(self, movie_ids: List[str]) -> List[MovieInDB]:
        """Finds multiple movies by a list of MongoDB ObjectId strings."""
        self._check_db()
        valid_object_ids = [obj_id for mid in movie_ids if (obj_id := self._validate_object_id(mid))]
        if not valid_object_ids:
            return []
        try:
            cursor = self.collection.find({"_id": {"$in": valid_object_ids}})
            docs = await cursor.to_list(length=len(valid_object_ids))
            # Use MovieInDB which expects _id and embedding
            return [MovieInDB.model_validate(doc) for doc in docs]
        except PyMongoError as e:
            logger.error(f"DB error finding movies by IDs {movie_ids}: {e}", exc_info=True)
            raise

    async def find_with_filters(
        self, query: Dict[str, Any], skip: int, limit: int
    ) -> List[MovieInDB]:
        """Finds movies based on a query, with skip and limit for pagination."""
        self._check_db()
        try:
            cursor = self.collection.find(query).skip(skip).limit(limit)
            docs = await cursor.to_list(length=limit)
            # Use MovieInDB as it represents the full DB structure
            return [MovieInDB.model_validate(doc) for doc in docs]
        except PyMongoError as e:
            logger.error(f"DB error finding movies with filters {query}: {e}", exc_info=True)
            raise

    async def count_with_filters(self, query: Dict[str, Any]) -> int:
        """Counts documents matching a query."""
        self._check_db()
        try:
            count = await self.collection.count_documents(query)
            return count
        except PyMongoError as e:
            logger.error(f"DB error counting movies with filters {query}: {e}", exc_info=True)
            raise

    async def get_sample_with_embeddings(
        self, exclude_ids: List[ObjectId], sample_size: int
    ) -> List[MovieInDB]:
        """Gets a random sample of movies with embeddings, excluding certain IDs."""
        self._check_db()
        try:
            pipeline = [
                {"$match": {
                    "_id": {"$nin": exclude_ids},
                    "embedding": {"$exists": True, "$ne": None, "$not": {"$size": 0}}
                }},
                {"$sample": {"size": sample_size}},
                # Project all fields needed by MovieInDB
                # {"$project": {"_id": 1, "embedding": 1, "title": 1, ...}} # Or just let it pass all
            ]
            cursor = self.collection.aggregate(pipeline)
            docs = await cursor.to_list(length=sample_size)
            return [MovieInDB.model_validate(doc) for doc in docs]
        except PyMongoError as e:
            logger.error(f"DB error getting sample movies: {e}", exc_info=True)
            raise

# --- Interaction Repository ---
class InteractionRepository(BaseRepository):
    def __init__(self, db: AsyncIOMotorDatabase):
        super().__init__(db, collection_name="interactions")

    async def insert_one(self, interaction_doc: Dict[str, Any]) -> str:
        """Inserts a single interaction document."""
        self._check_db()
        try:
            result = await self.collection.insert_one(interaction_doc)
            return str(result.inserted_id)
        except PyMongoError as e:
            logger.error(f"DB error inserting interaction: {e}", exc_info=True)
            raise

    async def find_by_user(
        self, user_id: str, query_filter: Dict[str, Any], skip: int, limit: int, sort: List[tuple] = None
    ) -> List[Dict[str, Any]]: # Return raw dicts, service layer converts to Pydantic
        """Finds interactions for a user with optional filters, skip, limit, sort."""
        self._check_db()
        final_query = {"userId": user_id, **query_filter}
        try:
            cursor = self.collection.find(final_query)
            if sort:
                cursor = cursor.sort(sort)
            cursor = cursor.skip(skip).limit(limit)
            docs = await cursor.to_list(length=limit)
            return docs # Return raw dicts
        except PyMongoError as e:
            logger.error(f"DB error finding interactions for user {user_id}: {e}", exc_info=True)
            raise

    async def count_by_user(self, user_id: str, query_filter: Dict[str, Any]) -> int:
        """Counts interactions for a user with optional filters."""
        self._check_db()
        final_query = {"userId": user_id, **query_filter}
        try:
            count = await self.collection.count_documents(final_query)
            return count
        except PyMongoError as e:
            logger.error(f"DB error counting interactions for user {user_id}: {e}", exc_info=True)
            raise

    async def find_user_movie_ids(self, user_id: str, query_filter: Dict[str, Any]) -> List[str]:
        """Finds distinct movie IDs interacted with by a user, matching a filter."""
        self._check_db()
        final_query = {"userId": user_id, **query_filter}
        try:
            # Use distinct for efficiency if only IDs are needed
            distinct_ids = await self.collection.distinct("movieId", final_query)
            # Ensure they are strings
            return [str(mid) for mid in distinct_ids]
        except PyMongoError as e:
            logger.error(f"DB error finding distinct movie IDs for user {user_id}: {e}", exc_info=True)
            raise