# Functions to connect to MongoDB
# data_processing/common/db_connect.py

import logging
import os
import sys

from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.database import Database
from pymongo.errors import ConfigurationError, ConnectionFailure

logger = logging.getLogger(__name__)

# Load environment variables from .env file in the data_processing directory
# Adjust path if your script execution context is different
dotenv_path = os.path.join(os.path.dirname(__file__), '..', '.env')
load_dotenv(dotenv_path=dotenv_path)

_mongo_client = None # Cache the client instance

def get_mongo_client() -> MongoClient:
    """
    Establishes and returns a pymongo MongoClient instance.
    Caches the client instance for potential reuse within a script run.

    Returns:
        A MongoClient instance.

    Raises:
        ConnectionFailure: If the connection to MongoDB fails.
        ConfigurationError: If the URI is invalid.
        ValueError: If MONGODB_URI environment variable is not set.
    """
    global _mongo_client
    if _mongo_client:
        # Optional: Check if client is still alive? Might be overkill for scripts.
        # try:
        #     _mongo_client.admin.command('ping')
        #     return _mongo_client
        # except ConnectionFailure:
        #     logger.warning("Cached MongoDB client connection lost. Reconnecting.")
        #     _mongo_client = None # Force reconnect
        # else:
             return _mongo_client # Return cached client

    mongodb_uri = os.environ.get("MONGODB_URI")
    if not mongodb_uri:
        logger.critical("MONGODB_URI environment variable not set.")
        raise ValueError("MONGODB_URI environment variable is required.")

    logger.info(f"Connecting to MongoDB at {mongodb_uri[:15]}...") # Log partial URI safely
    try:
        client = MongoClient(mongodb_uri, serverSelectionTimeoutMS=5000) # Add timeout
        # The ismaster command is cheap and does not require auth.
        client.admin.command('ismaster')
        logger.info("MongoDB connection successful.")
        _mongo_client = client # Cache the client
        return client
    except ConfigurationError as e:
        logger.critical(f"MongoDB configuration error: {e}", exc_info=True)
        raise
    except ConnectionFailure as e:
        logger.critical(f"MongoDB connection failed: {e}", exc_info=True)
        raise
    except Exception as e:
        logger.critical(f"An unexpected error occurred during MongoDB connection: {e}", exc_info=True)
        raise

def get_mongo_database(client: MongoClient = None, db_name: str = None) -> Database:
    """
    Returns a pymongo Database instance.

    Args:
        client: Optional MongoClient instance. If None, a new one is created.
        db_name: Optional database name. If None, attempts to get from URI or uses fallback.

    Returns:
        A pymongo Database instance.

    Raises:
        ValueError: If database name cannot be determined.
    """
    if client is None:
        client = get_mongo_client() # Get potentially cached client

    if db_name:
        logger.debug(f"Using provided database name: {db_name}")
        return client[db_name]
    else:
        # Attempt to get DB name from the connection string URI
        default_db = client.get_database() # Gets DB from URI or raises if ambiguous
        if default_db:
             logger.debug(f"Using database name from URI: {default_db.name}")
             return default_db
        else:
            # Fallback if DB name isn't in the URI (should generally be avoided)
            fallback_db_name = "movielens_db"
            logger.warning(f"Database name not found in URI, using fallback: {fallback_db_name}")
            return client[fallback_db_name]

# Example usage (usually called from scripts)
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    try:
        mongo_client = get_mongo_client()
        db = get_mongo_database(client=mongo_client)
        print(f"Successfully connected to database: {db.name}")
        print(f"Collections: {db.list_collection_names()}")
        mongo_client.close() # Close connection when done in script
    except (ValueError, ConnectionFailure, ConfigurationError) as e:
        print(f"Failed to connect to MongoDB: {e}", file=sys.stderr)
        sys.exit(1)