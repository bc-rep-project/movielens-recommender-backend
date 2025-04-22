# Loads ratings/interactions to MongoDB
# data_processing/scripts/03_load_interactions.py

import logging
import os
import sys
import json
import zipfile
import io
import time
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

import pandas as pd
from pymongo.errors import BulkWriteError, PyMongoError
from tqdm import tqdm # Optional progress bar
from dotenv import load_dotenv

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Import common modules
try:
    from data_processing.common.storage_client import get_gcs_client, get_gcs_bucket_name
    from data_processing.common.db_connect import get_mongo_database, get_mongo_client
    from data_processing.common.models import InteractionType # Use enum
except ImportError as e:
    print(f"Error importing common modules: {e}. Make sure PYTHONPATH is set correctly or run from project root.", file=sys.stderr)
    sys.exit(1)

# --- Configuration ---
logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO").upper(),
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

dotenv_path = os.path.join(os.path.dirname(__file__), '..', '.env')
load_dotenv(dotenv_path=dotenv_path)

MOVIELENS_ZIP_FILENAME = os.environ.get("MOVIELENS_ZIP_FILENAME", "ml-latest-small.zip")
GCS_DATASET_PATH = os.environ.get("GCS_DATASET_PATH", "datasets/")
MONGO_INTERACTIONS_COLLECTION = "interactions"
MONGO_MOVIES_COLLECTION = "movies" # Needed for ID mapping
INTERACTION_BATCH_SIZE = 5000 # Batch size for MongoDB insertion

# --- Main Function ---
def main():
    """
    Downloads MovieLens zip from GCS, reads ratings.csv, maps movie IDs,
    and uploads interaction data to MongoDB.
    """
    status_data = {"script": os.path.basename(__file__), "status": "STARTED"}
    logger.info(f"Starting script: {status_data['script']}")
    start_time = time.time()

    mongo_client = None # Ensure client is defined for finally block

    try:
        # --- Get Clients ---
        gcs_client = get_gcs_client()
        bucket_name = get_gcs_bucket_name()
        mongo_client = get_mongo_client()
        db = get_mongo_database(client=mongo_client)
        interactions_collection = db[MONGO_INTERACTIONS_COLLECTION]
        movies_collection = db[MONGO_MOVIES_COLLECTION] # For ID lookup

        # --- Download and Read Data ---
        gcs_object_name = os.path.join(GCS_DATASET_PATH.strip('/'), MOVIELENS_ZIP_FILENAME)
        logger.info(f"Attempting to read {gcs_object_name} from GCS bucket {bucket_name}...")

        bucket = gcs_client.bucket(bucket_name)
        blob = bucket.blob(gcs_object_name)
        if not blob.exists():
            logger.critical(f"Dataset zip file not found in GCS: gs://{bucket_name}/{gcs_object_name}")
            raise FileNotFoundError(f"GCS object gs://{bucket_name}/{gcs_object_name} not found.")

        zip_content = blob.download_as_bytes()
        logger.info(f"Downloaded {len(zip_content) / (1024*1024):.2f} MB from GCS.")

        # --- Load Movie ID Map ---
        # This map (movieId_ml -> _id string) should have been created by script 02
        # Alternatively, query the movies collection here (less efficient for large datasets)
        movie_id_map: Dict[int, str] = {}
        map_filename = "movie_id_map.json" # Assumes script 02 saved this
        if os.path.exists(map_filename):
             with open(map_filename, 'r') as f:
                 try:
                    loaded_map = json.load(f)
                    # Ensure keys are integers
                    movie_id_map = {int(k): v for k, v in loaded_map.items()}
                    logger.info(f"Loaded {len(movie_id_map)} entries from {map_filename}")
                 except (json.JSONDecodeError, ValueError) as e:
                     logger.error(f"Error loading or parsing {map_filename}: {e}. Proceeding without map.", exc_info=True)
        else:
            # Fallback: Query MongoDB to build the map (can be slow)
            logger.warning(f"{map_filename} not found. Querying MongoDB to build movie ID map...")
            cursor = movies_collection.find({}, {"_id": 1, "movieId_ml": 1})
            async for doc in cursor: # Note: db_connect uses sync pymongo, adjust if async needed
                if "movieId_ml" in doc and "_id" in doc:
                    movie_id_map[int(doc["movieId_ml"])] = str(doc["_id"])
            logger.info(f"Built map with {len(movie_id_map)} entries from MongoDB.")

        if not movie_id_map:
             logger.error("Movie ID map is empty. Cannot map interactions to internal movie IDs.")
             raise ValueError("Failed to load or build movie ID map.")


        # --- Process ratings.csv ---
        interaction_docs_to_insert = []
        processed_count = 0
        skipped_count = 0

        with zipfile.ZipFile(io.BytesIO(zip_content)) as z:
            ratings_csv_path = None
            for filename in z.namelist():
                if filename.endswith("ratings.csv"):
                    ratings_csv_path = filename
                    break
            if not ratings_csv_path:
                 raise FileNotFoundError("ratings.csv not found within the zip file.")

            logger.info(f"Reading {ratings_csv_path} from zip file...")
            with z.open(ratings_csv_path) as f:
                # Specify dtypes for efficiency and correctness
                ratings_df = pd.read_csv(f, dtype={'userId': int, 'movieId': int, 'rating': float, 'timestamp': int})
                logger.info(f"Loaded {len(ratings_df)} ratings from CSV.")

            # --- Prepare Documents for MongoDB ---
            logger.info("Preparing interaction documents for MongoDB insertion...")
            total_rows = len(ratings_df)
            for idx, row in tqdm(ratings_df.iterrows(), total=total_rows, desc="Preparing Interactions"):
                movie_id_ml = int(row['movieId'])
                internal_movie_id = movie_id_map.get(movie_id_ml)

                if internal_movie_id is None:
                    # logger.debug(f"Skipping rating for unknown movieId_ml: {movie_id_ml}")
                    skipped_count += 1
                    continue # Skip interactions for movies not found in our map

                interaction_doc = {
                    # Generate a new ObjectId for the interaction record itself? Or use composite key?
                    # Let's generate one for simplicity.
                    "_id": ObjectId(),
                    "userId": str(row['userId']), # Convert userId to string if needed by backend schema
                    "movieId": internal_movie_id, # Use the mapped internal MongoDB ID
                    "type": InteractionType.RATE.value, # Set type to 'rate'
                    "value": float(row['rating']),
                    "timestamp": datetime.fromtimestamp(row['timestamp'], tz=timezone.utc) # Convert Unix timestamp
                }
                interaction_docs_to_insert.append(interaction_doc)
                processed_count += 1

                # Insert in batches
                if len(interaction_docs_to_insert) >= INTERACTION_BATCH_SIZE:
                    logger.debug(f"Inserting batch of {len(interaction_docs_to_insert)} interactions...")
                    try:
                        # Use synchronous client here
                        interactions_collection.insert_many(interaction_docs_to_insert, ordered=False)
                    except BulkWriteError as bwe:
                         logger.error(f"MongoDB bulk write error during interaction batch insert: {bwe.details}", exc_info=True)
                         # Decide whether to continue or raise
                    except PyMongoError as e:
                         logger.error(f"MongoDB error during interaction batch insert: {e}", exc_info=True)
                         # Decide whether to continue or raise
                    interaction_docs_to_insert = [] # Clear batch

            # Insert any remaining documents
            if interaction_docs_to_insert:
                logger.debug(f"Inserting final batch of {len(interaction_docs_to_insert)} interactions...")
                try:
                    interactions_collection.insert_many(interaction_docs_to_insert, ordered=False)
                except BulkWriteError as bwe:
                     logger.error(f"MongoDB bulk write error during final interaction batch insert: {bwe.details}", exc_info=True)
                except PyMongoError as e:
                     logger.error(f"MongoDB error during final interaction batch insert: {e}", exc_info=True)

            logger.info(f"Finished processing interactions. Prepared: {processed_count}, Skipped (unknown movie): {skipped_count}")
            status_data["interactions_processed"] = processed_count
            status_data["interactions_skipped"] = skipped_count

            # Optional: Verify count in DB matches processed_count (can be slow)
            # db_count = interactions_collection.count_documents({})
            # logger.info(f"MongoDB collection '{MONGO_INTERACTIONS_COLLECTION}' now contains {db_count} documents.")
            # status_data["mongodb_final_count"] = db_count

            status_data["status"] = "SUCCESS"
            status_data["message"] = "Successfully processed ratings and loaded interactions to MongoDB."

    except FileNotFoundError as e:
        logger.critical(f"Required file not found: {e}")
        status_data["status"] = "FAILURE"
        status_data["message"] = f"File not found: {e}"
        status_data["error_details"] = str(e)
    except Exception as e:
        logger.critical(f"Script failed critically: {e}", exc_info=True)
        status_data["status"] = "CRITICAL_FAILURE"
        status_data["message"] = "Script failed due to an unhandled exception."
        status_data["error_details"] = str(e)
    finally:
        if mongo_client:
            mongo_client.close()
            logger.info("MongoDB connection closed.")

    end_time = time.time()
    status_data["duration_seconds"] = round(end_time - start_time, 2)
    # Output final status as JSON
    print(json.dumps(status_data, indent=2))
    if "FAILURE" in status_data["status"]:
        sys.exit(1)

if __name__ == "__main__":
    main()