# backend/app/services/recommendation_service.py

import json
import logging
import time
from typing import List, Optional, Dict, Tuple, Any

import numpy as np
from motor.motor_asyncio import AsyncIOMotorDatabase
from redis.asyncio import Redis
from redis.exceptions import RedisError
from pymongo.errors import PyMongoError
from scipy.spatial.distance import cosine as cosine_distance # Note: distance = 1 - similarity
from bson import ObjectId # Import ObjectId for queries

# Assume models are defined elsewhere (e.g., app.models)
# from app.models.interaction import InteractionRead
# from app.models.movie import MovieRead # Assuming a model for movie data

logger = logging.getLogger(__name__)

# --- Constants ---
DEFAULT_TOP_N = 10
MIN_RATING_FOR_POSITIVE_INTERACTION = 4.0 # Minimum rating to consider as 'liked'
CANDIDATE_POOL_SAMPLE_SIZE = 500 # How many candidates to fetch for similarity calculation
USER_REC_CACHE_TTL_SECONDS = 3600 # 1 hour
ITEM_REC_CACHE_TTL_SECONDS = 86400 # 24 hours
USER_REC_CACHE_PREFIX = "rec:user:"
ITEM_REC_CACHE_PREFIX = "rec:item:"

class RecommendationServiceError(Exception):
    """Custom exception for recommendation service errors."""
    pass

class RecommendationService:
    def __init__(self, db: AsyncIOMotorDatabase, cache: Redis):
        """
        Initializes the Recommendation Service.

        Args:
            db: An instance of AsyncIOMotorDatabase (Motor client).
            cache: An instance of Redis client (redis-py async).
        """
        self.db = db
        self.cache = cache
        self.movies_collection = db["movies"]
        self.interactions_collection = db["interactions"]

    # --- Helper Methods ---

    def _calculate_cosine_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """Calculates cosine similarity between two numpy vectors."""
        # Ensure vectors are numpy arrays
        vec1 = np.asarray(vec1, dtype=np.float32)
        vec2 = np.asarray(vec2, dtype=np.float32)

        if vec1.shape != vec2.shape or vec1.ndim != 1:
            logger.warning(f"Attempting to compare vectors with incompatible shapes: {vec1.shape} vs {vec2.shape}")
            return 0.0

        # Handle potential zero vectors to avoid division by zero and NaN results
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        if norm1 == 0 or norm2 == 0:
            return 0.0

        # Calculate cosine similarity: dot(v1, v2) / (norm(v1) * norm(v2))
        similarity = np.dot(vec1, vec2) / (norm1 * norm2)

        # Clamp similarity to [0, 1] due to potential floating point inaccuracies
        # and ensure we don't return slightly negative values
        return max(0.0, min(1.0, similarity))


    async def _get_user_positive_interactions(self, user_id: str) -> List[str]:
        """Fetches movie IDs the user interacted positively with (e.g., rated highly)."""
        try:
            # Find interactions matching criteria
            cursor = self.interactions_collection.find(
                {
                    "userId": user_id,
                    "type": "rate", # Assuming 'rate' is the primary interaction type for profile
                    "value": {"$gte": MIN_RATING_FOR_POSITIVE_INTERACTION}
                },
                {"movieId": 1, "_id": 0} # Project only movieId
            ).sort("timestamp", -1).limit(50) # Limit history size for profile generation

            # Extract movie IDs, ensuring they are valid ObjectIds if needed elsewhere, but here just strings
            liked_movie_ids = [doc["movieId"] for doc in await cursor.to_list(length=50) if "movieId" in doc]

            # Return unique IDs
            unique_liked_ids = list(set(liked_movie_ids))
            logger.debug(f"Found {len(unique_liked_ids)} unique positive interaction movie IDs for user {user_id}.")
            return unique_liked_ids
        except PyMongoError as e:
            logger.error(f"Database error fetching positive interactions for user {user_id}: {e}", exc_info=True)
            return [] # Return empty list on error

    async def _get_user_all_interacted_ids(self, user_id: str) -> List[str]:
        """Fetches all movie IDs the user has interacted with (for filtering recommendations)."""
        try:
            cursor = self.interactions_collection.find(
                {"userId": user_id},
                {"movieId": 1, "_id": 0} # Project only movieId
            )
            # Increase length limit if users might have many interactions
            interacted_ids = [doc["movieId"] for doc in await cursor.to_list(length=1000) if "movieId" in doc]
            unique_interacted_ids = list(set(interacted_ids))
            logger.debug(f"Found {len(unique_interacted_ids)} unique interacted movie IDs for user {user_id}.")
            return unique_interacted_ids
        except PyMongoError as e:
            logger.error(f"Database error fetching all interacted IDs for user {user_id}: {e}", exc_info=True)
            return []

    async def _get_movie_embeddings(self, movie_ids: List[str]) -> Dict[str, Optional[np.ndarray]]:
        """Fetches embeddings for a list of movie IDs."""
        if not movie_ids:
            return {}

        # Validate ObjectIds and filter out invalid ones before querying
        valid_object_ids_map = {} # Store original string ID -> ObjectId
        for mid in movie_ids:
            if ObjectId.is_valid(mid):
                valid_object_ids_map[mid] = ObjectId(mid)
            else:
                logger.warning(f"Invalid movie ID format in embedding request: {mid}")

        if not valid_object_ids_map:
            return {mid: None for mid in movie_ids} # Return None for all if no valid IDs

        embeddings_map: Dict[str, Optional[np.ndarray]] = {mid: None for mid in movie_ids} # Initialize with None

        try:
            cursor = self.movies_collection.find(
                {"_id": {"$in": list(valid_object_ids_map.values())}},
                {"_id": 1, "embedding": 1} # Project ID and embedding
            )
            async for doc in cursor:
                # Map ObjectId back to original string ID
                original_id = None
                doc_object_id = doc["_id"]
                for str_id, obj_id in valid_object_ids_map.items():
                    if obj_id == doc_object_id:
                        original_id = str_id
                        break

                if original_id is None: continue # Should not happen if logic is correct

                embedding_list = doc.get("embedding")
                if embedding_list and isinstance(embedding_list, list) and len(embedding_list) > 0:
                    try:
                        embeddings_map[original_id] = np.array(embedding_list, dtype=np.float32)
                    except ValueError as ve:
                         logger.warning(f"Could not convert embedding to numpy array for movie ID: {original_id}. Error: {ve}")
                else:
                    logger.warning(f"Missing, empty, or invalid embedding list for movie ID: {original_id}")

            found_count = sum(1 for emb in embeddings_map.values() if emb is not None)
            logger.debug(f"Fetched {found_count} valid embeddings for {len(movie_ids)} requested IDs.")
            return embeddings_map
        except PyMongoError as e:
            logger.error(f"Database error fetching embeddings for movie IDs {movie_ids}: {e}", exc_info=True)
            # Return map with None for all requested IDs on error
            return {mid: None for mid in movie_ids}


    async def _get_candidate_movie_embeddings(
        self, exclude_ids: List[str] = [], sample_size: int = CANDIDATE_POOL_SAMPLE_SIZE
    ) -> Dict[str, np.ndarray]:
        """Fetches embeddings for a sample of candidate movies, excluding specified IDs."""
        candidate_embeddings: Dict[str, np.ndarray] = {}

        # Convert exclude_ids to ObjectIds, filtering invalid ones
        exclude_object_ids = []
        for mid in exclude_ids:
            if ObjectId.is_valid(mid):
                exclude_object_ids.append(ObjectId(mid))

        try:
            # MongoDB aggregation pipeline to get a random sample
            pipeline = [
                # Match only movies that *have* a valid embedding field
                {"$match": {
                    "_id": {"$nin": exclude_object_ids}, # Exclude specified IDs
                    "embedding": {"$exists": True, "$ne": None, "$not": {"$size": 0}} # Ensure embedding exists and is not empty
                }},
                {"$sample": {"size": sample_size}}, # Get a random sample
                {"$project": {"_id": 1, "embedding": 1}} # Project only needed fields
            ]
            cursor = self.movies_collection.aggregate(pipeline)

            async for doc in cursor:
                movie_id = str(doc["_id"]) # Convert ObjectId to string
                embedding_list = doc.get("embedding")
                # We already matched for valid embeddings, but double-check type
                if embedding_list and isinstance(embedding_list, list):
                    try:
                        candidate_embeddings[movie_id] = np.array(embedding_list, dtype=np.float32)
                    except ValueError as ve:
                        logger.warning(f"Could not convert candidate embedding for movie ID: {movie_id}. Error: {ve}")
                # else case should not happen due to $match stage

            logger.info(f"Fetched {len(candidate_embeddings)} valid candidate embeddings (requested sample: {sample_size}).")
            return candidate_embeddings
        except PyMongoError as e:
            logger.error(f"Database error fetching candidate embeddings: {e}", exc_info=True)
            return {} # Return empty dict on error

    # --- Public Service Methods ---

    async def get_content_recommendations_for_user(
        self, user_id: str, top_n: int = DEFAULT_TOP_N
    ) -> List[str]:
        """
        Generates content-based recommendations for a user based on their positive interactions.
        Returns a list of recommended movie IDs.
        """
        start_time = time.monotonic()
        cache_key = f"{USER_REC_CACHE_PREFIX}{user_id}"
        log_context = {"userId": user_id, "topN": top_n, "function": "get_content_recommendations_for_user"}

        # 1. Check cache
        try:
            cached_result = await self.cache.get(cache_key)
            if cached_result:
                # Deserialize from JSON string
                recommendations = json.loads(cached_result)
                if isinstance(recommendations, list):
                    duration = (time.monotonic() - start_time) * 1000
                    logger.info({**log_context, "message": "User recommendations cache hit.", "durationMs": duration, "cacheStatus": "hit", "count": len(recommendations)})
                    return recommendations
                else:
                    logger.warning({**log_context, "message": "Invalid data format in user rec cache.", "cacheValue": cached_result[:100]})
                    # Proceed to recalculate if cache data is bad
        except RedisError as e:
            logger.warning({**log_context, "message": "Cache read error.", "error": str(e)}, exc_info=True)
        except json.JSONDecodeError as e:
             logger.warning({**log_context, "message": "Cache JSON decode error.", "error": str(e)}, exc_info=True)

        logger.info({**log_context, "message": "User recommendations cache miss. Calculating...", "cacheStatus": "miss"})

        # 2. Fetch user history (positive interactions)
        liked_movie_ids = await self._get_user_positive_interactions(user_id)
        if not liked_movie_ids:
            logger.warning({**log_context, "message": "No positive interactions found for user. Cannot generate content recommendations."})
            # Consider fallback to popular items here if desired
            return []
        log_context["likedItemsCount"] = len(liked_movie_ids)

        # 3. Fetch liked item embeddings
        liked_embeddings_map = await self._get_movie_embeddings(liked_movie_ids)
        valid_liked_embeddings = [emb for emb in liked_embeddings_map.values() if emb is not None]

        if not valid_liked_embeddings:
            logger.error({**log_context, "message": "Could not retrieve valid embeddings for any liked items."})
            return [] # Cannot proceed without profile

        # 4. Calculate user profile vector (average embedding)
        # Ensure embeddings are numpy arrays before averaging
        user_profile_vector = np.mean(np.array(valid_liked_embeddings), axis=0)
        logger.debug({**log_context, "message": f"Calculated user profile vector from {len(valid_liked_embeddings)} embeddings."})


        # 5. Fetch candidate embeddings (excluding *all* interacted items)
        all_interacted_ids = await self._get_user_all_interacted_ids(user_id)
        candidate_embeddings_map = await self._get_candidate_movie_embeddings(
            exclude_ids=all_interacted_ids,
            sample_size=CANDIDATE_POOL_SAMPLE_SIZE
        )

        if not candidate_embeddings_map:
             logger.warning({**log_context, "message": "No candidate embeddings found after filtering."})
             return []

        # 6. Calculate similarity between user profile and candidates
        recommendations_scored: List[Tuple[str, float]] = []
        for movie_id, candidate_embedding in candidate_embeddings_map.items():
            similarity = self._calculate_cosine_similarity(user_profile_vector, candidate_embedding)
            # Set a minimum similarity threshold? Optional.
            # if similarity > 0.1:
            recommendations_scored.append((movie_id, similarity))

        # 7. Rank and select top N
        recommendations_scored.sort(key=lambda x: x[1], reverse=True)
        final_recommendations = [movie_id for movie_id, score in recommendations_scored[:top_n]]

        # 8. Store in cache
        if final_recommendations: # Only cache if we have results
            try:
                # Serialize list to JSON string
                await self.cache.set(cache_key, json.dumps(final_recommendations), ex=USER_REC_CACHE_TTL_SECONDS)
                log_context["cacheStatus"] = "stored"
            except RedisError as e:
                logger.warning({**log_context, "message": "Cache write error.", "error": str(e)}, exc_info=True)
                log_context["cacheStatus"] = "write_failed"
            except Exception as e:
                 logger.error({**log_context, "message": "Unexpected error during cache write.", "error": str(e)}, exc_info=True)
                 log_context["cacheStatus"] = "write_failed"
        else:
             log_context["cacheStatus"] = "not_stored_empty"


        duration = (time.monotonic() - start_time) * 1000
        logger.info({
            **log_context,
            "message": "Generated user content recommendations.",
            "recommendationsCount": len(final_recommendations),
            "durationMs": duration
        })
        return final_recommendations


    async def get_similar_items(
        self, movie_id: str, top_n: int = DEFAULT_TOP_N
    ) -> List[str]:
        """
        Generates recommendations for items similar to a given item based on content embeddings.
        Returns a list of similar movie IDs.
        """
        start_time = time.monotonic()
        cache_key = f"{ITEM_REC_CACHE_PREFIX}{movie_id}"
        log_context = {"sourceMovieId": movie_id, "topN": top_n, "function": "get_similar_items"}

        # 1. Check cache
        try:
            cached_result = await self.cache.get(cache_key)
            if cached_result:
                recommendations = json.loads(cached_result)
                if isinstance(recommendations, list):
                    duration = (time.monotonic() - start_time) * 1000
                    logger.info({**log_context, "message": "Similar items cache hit.", "durationMs": duration, "cacheStatus": "hit", "count": len(recommendations)})
                    return recommendations
                else:
                     logger.warning({**log_context, "message": "Invalid data format in item rec cache.", "cacheValue": cached_result[:100]})
        except RedisError as e:
            logger.warning({**log_context, "message": "Cache read error.", "error": str(e)}, exc_info=True)
        except json.JSONDecodeError as e:
             logger.warning({**log_context, "message": "Cache JSON decode error.", "error": str(e)}, exc_info=True)

        logger.info({**log_context, "message": "Similar items cache miss. Calculating...", "cacheStatus": "miss"})

        # 2. Fetch target item embedding
        target_embedding_map = await self._get_movie_embeddings([movie_id])
        target_embedding = target_embedding_map.get(movie_id)

        if target_embedding is None:
            logger.error({**log_context, "message": "Target movie not found or embedding missing."})
            # Raise an error that the API layer can catch and turn into a 404
            raise RecommendationServiceError(f"Movie or embedding not found for ID: {movie_id}")

        # 3. Fetch candidate embeddings (excluding target item)
        candidate_embeddings_map = await self._get_candidate_movie_embeddings(
            exclude_ids=[movie_id],
            sample_size=CANDIDATE_POOL_SAMPLE_SIZE
        )

        if not candidate_embeddings_map:
             logger.warning({**log_context, "message": "No candidate embeddings found after filtering."})
             return []

        # 4. Calculate similarity
        recommendations_scored: List[Tuple[str, float]] = []
        for candidate_id, candidate_embedding in candidate_embeddings_map.items():
            similarity = self._calculate_cosine_similarity(target_embedding, candidate_embedding)
            # Optional: Set a minimum similarity threshold?
            # if similarity > 0.5: # Example threshold
            recommendations_scored.append((candidate_id, similarity))

        # 5. Rank and select top N
        recommendations_scored.sort(key=lambda x: x[1], reverse=True)
        final_recommendations = [rec_id for rec_id, score in recommendations_scored[:top_n]]

        # 6. Store in cache
        if final_recommendations:
            try:
                await self.cache.set(cache_key, json.dumps(final_recommendations), ex=ITEM_REC_CACHE_TTL_SECONDS)
                log_context["cacheStatus"] = "stored"
            except RedisError as e:
                logger.warning({**log_context, "message": "Cache write error.", "error": str(e)}, exc_info=True)
                log_context["cacheStatus"] = "write_failed"
            except Exception as e:
                 logger.error({**log_context, "message": "Unexpected error during cache write.", "error": str(e)}, exc_info=True)
                 log_context["cacheStatus"] = "write_failed"
        else:
            log_context["cacheStatus"] = "not_stored_empty"

        duration = (time.monotonic() - start_time) * 1000
        logger.info({
            **log_context,
            "message": "Generated similar items recommendations.",
            "recommendationsCount": len(final_recommendations),
            "durationMs": duration
        })
        return final_recommendations