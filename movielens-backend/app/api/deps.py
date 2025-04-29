# FastAPI dependencies (e.g., get_db, get_current_user)
# backend/app/api/deps.py

import logging
from typing import AsyncGenerator, Optional

import redis.asyncio as redis
from fastapi import Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from redis.exceptions import RedisError
from pymongo.errors import ConnectionFailure

# Import settings (assuming it's initialized in config.py)
# This assumes your config file defines settings like MONGODB_URI, REDIS_URL etc.
from app.core.config import settings

# Import the actual user-fetching dependency from security module
# This promotes better organization - keep auth logic in security.py
from app.core.security import get_current_user_id

logger = logging.getLogger(__name__)

# --- Global Clients (Initialized once) ---
# It's generally better practice to manage client lifecycles using FastAPI's
# lifespan events (startup/shutdown), especially for testing.
# However, initializing globally is simpler for this example.

mongo_client: Optional[AsyncIOMotorClient] = None
db_instance: Optional[AsyncIOMotorDatabase] = None
redis_client: Optional[redis.Redis] = None

async def initialize_connections():
    """
    Initializes MongoDB and Redis connections.
    Call this during FastAPI startup using lifespan events.
    """
    global mongo_client, db_instance, redis_client
    logger.info("Initializing external connections...")

    # --- MongoDB Initialization ---
    try:
        logger.info(f"Attempting to connect to MongoDB: {settings.MONGODB_URI.get_secret_value()[:15]}...") # Log partial URI safely
        mongo_client = AsyncIOMotorClient(
            settings.MONGODB_URI.get_secret_value(),
            # Add other options like timeouts if needed
            # serverSelectionTimeoutMS=5000
        )
        # Ping the server to verify connection early
        await mongo_client.admin.command('ping')

        # Determine DB name - either from URI or settings
        db_name_from_uri = mongo_client.get_default_database()
        db_name = db_name_from_uri.name if db_name_from_uri else "movielens_db" # Fallback name
        db_instance = mongo_client[db_name]
        logger.info(f"MongoDB client initialized successfully. Using database: '{db_name}'")

    except ConnectionFailure as e:
        logger.error(f"MongoDB connection failed during initialization: {e}", exc_info=True)
        mongo_client = None
        db_instance = None
        # Decide if startup should fail - raising here will stop FastAPI startup
        # raise RuntimeError(f"Failed to connect to MongoDB: {e}")
    except Exception as e:
        logger.error(f"Unexpected error initializing MongoDB client: {e}", exc_info=True)
        mongo_client = None
        db_instance = None
        # raise RuntimeError(f"Unexpected error initializing MongoDB: {e}")


    # --- Redis Initialization ---
    try:
        logger.info(f"Attempting to connect to Redis: {settings.REDIS_URL.get_secret_value()[:15]}...") # Log partial URL safely
        # Use decode_responses=True to get strings back from Redis directly
        redis_client = redis.from_url(
            settings.REDIS_URL.get_secret_value(),
            encoding="utf-8",
            decode_responses=True,
            # Add other options like health_check_interval
            # health_check_interval=30
        )
        # Ping to verify connection
        await redis_client.ping()
        logger.info("Redis client initialized successfully.")

    except RedisError as e:
        logger.error(f"Redis connection failed during initialization: {e}", exc_info=True)
        redis_client = None
        # raise RuntimeError(f"Failed to connect to Redis: {e}")
    except Exception as e:
        logger.error(f"Unexpected error initializing Redis client: {e}", exc_info=True)
        redis_client = None
        # raise RuntimeError(f"Unexpected error initializing Redis: {e}")

async def close_connections():
    """
    Closes MongoDB and Redis connections.
    Call this during FastAPI shutdown using lifespan events.
    """
    global mongo_client, redis_client
    logger.info("Closing external connections...")
    if mongo_client:
        mongo_client.close()
        logger.info("MongoDB client closed.")
    if redis_client:
        await redis_client.close()
        logger.info("Redis client closed.")


# --- Database Dependency ---

async def get_db() -> AsyncGenerator[AsyncIOMotorDatabase, None]:
    """
    FastAPI dependency that yields the application's MongoDB database instance.

    Raises:
        HTTPException 503: If the database instance is not available.
    """
    if db_instance is None:
        logger.critical("MongoDB database instance is not available. Check initialization.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service not available.",
        )
    # Motor manages connection pooling internally. Yielding the db instance is sufficient.
    yield db_instance


# --- Cache Dependency ---

async def get_redis() -> AsyncGenerator[redis.Redis, None]:
    """
    FastAPI dependency that yields an async Redis client instance.

    Raises:
        HTTPException 503: If the Redis client instance is not available.
    """
    if redis_client is None:
        logger.critical("Redis client instance is not available. Check initialization.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Cache service not available.",
        )
    # Yield the client instance connected to the pool
    yield redis_client


# --- Authentication Dependency ---

# Re-export the dependency from security.py for convenience and potentially add checks
async def get_current_active_user_id(
    # Depends on the function from security.py which handles JWT verification
    user_id: str = Depends(get_current_user_id)
) -> str:
    """
    Dependency that ensures the user is authenticated via JWT and returns their ID.

    This primarily relies on the implementation in `app.core.security.get_current_user_id`.
    You could add checks here if needed (e.g., check if user is marked 'active' in DB),
    but for simple JWT verification, relying on the security module is often sufficient.

    Args:
        user_id (str): The user ID extracted from the validated JWT token.

    Returns:
        str: The authenticated user's ID.

    Raises:
        HTTPException: If the underlying security dependency raises an exception
                      (e.g., 401 Unauthorized for invalid/expired token).
    """
    # --- Optional: Add check for user status in your database ---
    # Example:
    # try:
    #     db: AsyncIOMotorDatabase = await anext(get_db()) # Get DB instance within dependency
    #     user = await db["users"].find_one({"_id": user_id}, {"is_active": 1}) # Assuming user ID is the _id
    #     if not user:
    #         logger.warning(f"Authenticated user ID {user_id} not found in database.")
    #         raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    #     if not user.get("is_active", True): # Check an 'is_active' flag (default to True if missing)
    #         logger.warning(f"Authenticated user ID {user_id} is inactive.")
    #         raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Inactive user")
    # except HTTPException:
    #     raise # Re-raise HTTP exceptions
    # except Exception as e:
    #     logger.error(f"Error checking active status for user {user_id}: {e}", exc_info=True)
    #     raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error verifying user status")
    # --- End Optional Check ---

    # If no extra checks are needed, just return the ID from the security dependency
    return user_id


# --- Service Dependencies ---

async def get_dataset_service():
    """
    FastAPI dependency that provides a DatasetService instance.
    
    This service manages dataset downloads, storage, and processing.
    """
    from app.services.dataset_service import DatasetService
    
    # Get required dependencies
    db = await anext(get_db())
    redis_instance = await anext(get_redis()) if redis_client else None
    
    # Create and return the service
    return DatasetService(mongodb_client=db.client, redis_client=redis_instance)

async def get_model_service():
    """
    FastAPI dependency that provides a ModelService instance.
    
    This service manages model training, storage, and activation.
    """
    from app.services.model_service import ModelService
    
    # Get required dependencies
    db = await anext(get_db())
    redis_instance = await anext(get_redis()) if redis_client else None
    
    # Create and return the service
    return ModelService(mongodb_client=db.client, redis_client=redis_instance)


# --- How to use lifespan events in main.py ---
#
# from contextlib import asynccontextmanager
# from fastapi import FastAPI
# from app.api.deps import initialize_connections, close_connections
#
# @asynccontextmanager
# async def lifespan(app: FastAPI):
#     # Code to run on startup
#     await initialize_connections()
#     yield
#     # Code to run on shutdown
#     await close_connections()
#
# app = FastAPI(lifespan=lifespan, ...)
#
# --- ---