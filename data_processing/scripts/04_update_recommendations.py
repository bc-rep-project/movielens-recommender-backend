# (Optional) Periodic task for pre-computing recs
# data_processing/scripts/04_update_recommendations.py

import logging
import os
import sys
import json
import time
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional

from pymongo.errors import PyMongoError
from redis.exceptions import RedisError
from dotenv import load_dotenv

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Import common modules
try:
    from data_processing.common.db_connect import get_mongo_database, get_mongo_client
    # Import Redis client helper if using Redis for caching results
    from data_processing.common.redis_client import CacheRepository # Assuming this helper exists
    import redis # Import base redis library if helper not used or for direct client access
except ImportError as e:
    print(f"Error importing common modules: {e}. Make sure PYTHONPATH is set correctly or run from project root.", file=sys.stderr)
    sys.exit(1)

# --- Configuration ---
logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO").upper(),
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

dotenv_path = os.path.join(os.path.dirname(__file__), '..', '.env')
load_dotenv(dotenv_path=dotenv_path)

MONGO_INTERACTIONS_COLLECTION = "interactions"
MONGO_MOVIES_COLLECTION = "movies" # Needed for ID mapping if results include titles
RECENT_DAYS = int(os.environ.get("POPULARITY_RECENT_DAYS", 7)) # Look at interactions in last N days
MIN_RATING_POPULAR = float(os.environ.get("POPULARITY_MIN_RATING", 4.0)) # Min rating to count towards popularity
TOP_N_POPULAR = int(os.environ.get("POPULARITY_TOP_N", 50)) # How many popular items to store
CACHE_POPULAR_KEY = "rec:fallback:popular" # Redis key for storing popular items
CACHE_POPULAR_TTL_SECONDS = 86400 # Cache popular items for 24 hours

# --- Main Function ---
def main():
    """
    Calculates recently popular movies based on high ratings and stores
    the list in Redis as a fallback recommendation set.
    Kept simple for Free Tier constraints.
    """
    status_data = {"script": os.path.basename(__file__), "status": "STARTED"}
    logger.info(f"Starting script: {status_data['script']}")
    start_time = time.time()

    mongo_client = None
    redis_client = None # Define redis_client for finally block

    try:
        # --- Get Clients ---
        mongo_client = get_mongo_client()
        db = get_mongo_database(client=mongo_client)
        interactions_collection = db[MONGO_INTERACTIONS_COLLECTION]

        # --- Connect to Redis (optional, only if caching results) ---
        redis_url = os.environ.get("REDIS_URL")
        cache_repo = None
        if redis_url:
            try:
                # Use the CacheRepository helper or connect directly
                redis_client = redis.from_url(redis_url, decode_responses=True)
                redis_client.ping() # Verify connection
                cache_repo = CacheRepository(client=redis_client) # Use the helper
                logger.info("Redis connection successful.")
            except RedisError as e:
                logger.error(f"Failed to connect to Redis at {redis_url[:15]}...: {e}. Proceeding without cache.", exc_info=True)
                cache_repo = None # Ensure it's None if connection fails
            except Exception as e:
                 logger.error(f"Unexpected error connecting to Redis: {e}. Proceeding without cache.", exc_info=True)
                 cache_repo = None
        else:
            logger.warning("REDIS_URL not set. Popularity results will not be cached.")

        # --- Calculate Popularity ---
        logger.info(f"Calculating popular movies based on ratings >= {MIN_RATING_POPULAR} in the last {RECENT_DAYS} days.")
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=RECENT_DAYS)

        # Aggregation pipeline to count recent high ratings per movie
        pipeline = [
            {
                "$match": {
                    "type": "rate",
                    "value": {"$gte": MIN_RATING_POPULAR},
                    "timestamp": {"$gte": cutoff_date}
                }
            },
            {
                "$group": {
                    "_id": "$movieId", # Group by internal movie ID
                    "count": {"$sum": 1}
                }
            },
            {
                "$sort": {"count": -1} # Sort by count descending
            },
            {
                "$limit": TOP_N_POPULAR # Limit to top N
            },
            {
                "$project": { # Reshape output slightly if needed
                    "movieId": "$_id",
                    "count": 1,
                    "_id": 0
                }
            }
        ]

        popular_movies_agg = await interactions_collection.aggregate(pipeline).to_list(length=TOP_N_POPULAR) # Use await if using motor, remove if pymongo

        popular_movie_ids = [item["movieId"] for item in popular_movies_agg]
        status_data["popular_movies_found"] = len(popular_movie_ids)
        logger.info(f"Found {len(popular_movie_ids)} popular movies.")
        # logger.debug(f"Popular movie IDs: {popular_movie_ids}")

        # --- Store in Cache (if configured) ---
        if cache_repo and popular_movie_ids:
            logger.info(f"Attempting to store popular movie IDs in Redis cache key '{CACHE_POPULAR_KEY}'...")
            success = await cache_repo.set(
                CACHE_POPULAR_KEY,
                popular_movie_ids, # CacheRepository handles JSON serialization
                ttl_seconds=CACHE_POPULAR_TTL_SECONDS
            )
            if success:
                logger.info("Successfully stored popular movies in cache.")
                status_data["cache_status"] = "STORED"
            else:
                logger.error("Failed to store popular movies in cache.")
                status_data["cache_status"] = "FAILED"
        elif cache_repo:
             logger.info("No popular movies found, cache not updated.")
             status_data["cache_status"] = "NOT_UPDATED_EMPTY"
        else:
             status_data["cache_status"] = "SKIPPED_NO_CLIENT"


        status_data["status"] = "SUCCESS"
        status_data["message"] = "Successfully calculated and potentially cached popular movies."

    except Exception as e:
        logger.critical(f"Script failed critically: {e}", exc_info=True)
        status_data["status"] = "CRITICAL_FAILURE"
        status_data["message"] = "Script failed due to an unhandled exception."
        status_data["error_details"] = str(e)
    finally:
        if mongo_client:
            mongo_client.close()
            logger.info("MongoDB connection closed.")
        if redis_client:
            # Use await if redis client is async, remove if sync
            await redis_client.close() # Close direct client if used
            logger.info("Redis connection closed.")


    end_time = time.time()
    status_data["duration_seconds"] = round(end_time - start_time, 2)
    # Output final status as JSON
    print(json.dumps(status_data, indent=2))
    if "FAILURE" in status_data["status"]:
        sys.exit(1)


if __name__ == "__main__":
    # Note: If using motor (async) for MongoDB aggregation, you'd need asyncio.run()
    # import asyncio
    # asyncio.run(main())
    # If using pymongo (sync), just call main()
    main()