# Redis connection and caching logic
# backend/app/data_access/redis_client.py

import json
import logging
from typing import Optional, Any, List

import redis.asyncio as redis
from redis.exceptions import RedisError

logger = logging.getLogger(__name__)

class CacheRepository:
    """
    Provides structured access to Redis for caching operations.
    Assumes a configured redis.Redis client instance is provided.
    """
    def __init__(self, client: redis.Redis):
        self.client = client
        logger.debug("Initialized CacheRepository.")

    def _check_client(self):
        """Helper to check if Redis client is available."""
        if self.client is None:
            # This should ideally not happen if dependencies are set up correctly
            logger.critical("Redis client not available.")
            raise ConnectionError("Redis client connection not available.")

    async def get(self, key: str) -> Optional[Any]:
        """Gets a value from cache, attempting to deserialize JSON if possible."""
        self._check_client()
        try:
            value = await self.client.get(key)
            if value is None:
                logger.debug(f"Cache miss for key: {key}")
                return None

            logger.debug(f"Cache hit for key: {key}")
            try:
                # Attempt to deserialize if it looks like JSON
                if isinstance(value, str) and value.startswith(('[', '{')):
                    return json.loads(value)
                # Return raw value otherwise (might be simple string, int)
                return value
            except json.JSONDecodeError:
                logger.warning(f"Failed to decode JSON from cache key {key}. Returning raw value.")
                return value # Return raw string if not valid JSON
        except RedisError as e:
            logger.error(f"Redis GET error for key {key}: {e}", exc_info=True)
            # Treat cache error as a cache miss
            return None
        except Exception as e:
            logger.error(f"Unexpected error during cache GET for key {key}: {e}", exc_info=True)
            return None

    async def set(self, key: str, value: Any, ttl_seconds: Optional[int] = None) -> bool:
        """Sets a value in cache, serializing complex types to JSON."""
        self._check_client()
        try:
            # Serialize lists/dicts to JSON strings
            if isinstance(value, (list, dict)):
                value_to_set = json.dumps(value)
            elif isinstance(value, (int, float, bytes)):
                 value_to_set = value # Redis handles these directly
            elif isinstance(value, str):
                 value_to_set = value
            else:
                 # Attempt to convert other types to string, or raise error
                 logger.warning(f"Attempting to cache non-standard type {type(value)} for key {key}. Converting to string.")
                 value_to_set = str(value)

            logger.debug(f"Setting cache for key: {key} with TTL: {ttl_seconds}s")
            await self.client.set(key, value_to_set, ex=ttl_seconds)
            return True
        except RedisError as e:
            logger.error(f"Redis SET error for key {key}: {e}", exc_info=True)
            return False
        except Exception as e:
            logger.error(f"Unexpected error during cache SET for key {key}: {e}", exc_info=True)
            return False

    async def delete(self, key: str) -> bool:
        """Deletes a key from the cache."""
        self._check_client()
        try:
            deleted_count = await self.client.delete(key)
            logger.debug(f"Deleted {deleted_count} keys for pattern: {key}")
            return deleted_count > 0
        except RedisError as e:
            logger.error(f"Redis DELETE error for key {key}: {e}", exc_info=True)
            return False
        except Exception as e:
            logger.error(f"Unexpected error during cache DELETE for key {key}: {e}", exc_info=True)
            return False

    async def delete_by_prefix(self, prefix: str) -> bool:
        """Deletes all keys matching a given prefix (Use with caution!)."""
        self._check_client()
        deleted_count = 0
        try:
            # SCAN is preferred over KEYS in production to avoid blocking
            async for key in self.client.scan_iter(match=f"{prefix}*"):
                await self.client.delete(key)
                deleted_count += 1
            logger.info(f"Deleted {deleted_count} keys matching prefix: {prefix}")
            return deleted_count > 0
        except RedisError as e:
            logger.error(f"Redis error deleting by prefix {prefix}: {e}", exc_info=True)
            return False
        except Exception as e:
            logger.error(f"Unexpected error deleting by prefix {prefix}: {e}", exc_info=True)
            return False