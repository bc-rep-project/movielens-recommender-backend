# Loads data, generates embeddings, saves to MongoDB
# data_processing/scripts/02_generate_embeddings.py

import logging
import os
import sys
import json
import zipfile
import io
import time
from typing import List, Dict, Any, Optional

import pandas as pd
import numpy as np
from sentence_transformers import SentenceTransformer
from pymongo.errors import BulkWriteError, PyMongoError
from bson import ObjectId # To generate MongoDB IDs
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
    from data_processing.common.models import MovieInDB # Use the model for structure
    from app.utils.helpers import extract_year_from_title # Use helper from main app
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
HF_MODEL_NAME = os.environ.get("HF_MODEL_NAME", "sentence-transformers/all-MiniLM-L6-v2")
HF_DEVICE = os.environ.get("HF_DEVICE", None) # 'cuda', 'cpu', or None for auto
EMBEDDING_BATCH_SIZE = int(os.environ.get("EMBEDDING_BATCH_SIZE", 64))
MONGO_COLLECTION_NAME = "movies"

# --- Helper Functions ---
def prepare_movie_text(title: Optional[str], genres: Optional[List[str]]) -> str:
    """Combines title and genres into a single string for embedding."""
    title_str = str(title) if title else ""
    genre_str = " ".join(genres) if genres else ""
    # Simple concatenation, could be more sophisticated
    text = f"{title_str} Genres: {genre_str}".strip()
    # Basic cleaning
    text = text.replace("  ", " ")
    return text if text else "Unknown Movie" # Return placeholder if empty

def _generate_batch_embeddings(model: SentenceTransformer, texts: List[str], batch_size: int) -> np.ndarray:
    """Generates embeddings for a list of texts using the provided model and batch size."""
    return model.encode(texts, batch_size=batch_size, show_progress_bar=False, device=HF_DEVICE)

# --- Main Function ---
def main():
    """
    Downloads MovieLens zip from GCS, reads movies.csv, generates embeddings,
    and uploads movie data with embeddings to MongoDB.
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
        movies_collection = db[MONGO_COLLECTION_NAME]

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

        # --- Process movies.csv ---
        movie_docs_to_insert = []
        movie_id_map: Dict[int, str] = {} # Map movieId_ml -> MongoDB _id (as string)

        with zipfile.ZipFile(io.BytesIO(zip_content)) as z:
            # Find the movies.csv file within the zip (handle potential directory structure)
            movies_csv_path = None
            for filename in z.namelist():
                if filename.endswith("movies.csv"):
                    movies_csv_path = filename
                    break
            if not movies_csv_path:
                 raise FileNotFoundError("movies.csv not found within the zip file.")

            logger.info(f"Reading {movies_csv_path} from zip file...")
            with z.open(movies_csv_path) as f:
                # Specify dtype for movieId to avoid issues
                movies_df = pd.read_csv(f, dtype={'movieId': int})
                logger.info(f"Loaded {len(movies_df)} movies from CSV.")

            # --- Prepare Data for Embedding ---
            movies_df['genres_list'] = movies_df['genres'].str.split('|')
            movies_df['year'] = movies_df['title'].apply(extract_year_from_title)
            movies_df['text_for_embedding'] = movies_df.apply(
                lambda row: prepare_movie_text(row['title'], row['genres_list']), axis=1
            )

            texts_to_embed = movies_df['text_for_embedding'].tolist()
            movie_ids_ml = movies_df['movieId'].tolist() # Original MovieLens IDs

            # --- Load Embedding Model ---
            logger.info(f"Loading Sentence Transformer model: {HF_MODEL_NAME} (Device: {HF_DEVICE or 'auto'})")
            model = SentenceTransformer(HF_MODEL_NAME, device=HF_DEVICE)
            logger.info("Model loaded.")

            # --- Generate Embeddings in Batches ---
            logger.info(f"Generating embeddings for {len(texts_to_embed)} movies (Batch size: {EMBEDDING_BATCH_SIZE})...")
            all_embeddings = []
            for i in tqdm(range(0, len(texts_to_embed), EMBEDDING_BATCH_SIZE), desc="Generating Embeddings"):
                batch_texts = texts_to_embed[i:i + EMBEDDING_BATCH_SIZE]
                batch_embeddings = _generate_batch_embeddings(model, batch_texts, EMBEDDING_BATCH_SIZE)
                all_embeddings.extend(batch_embeddings.tolist()) # Convert numpy arrays to lists for JSON/Mongo

            logger.info("Embeddings generated.")
            status_data["embeddings_generated"] = len(all_embeddings)

            # --- Prepare Documents for MongoDB ---
            logger.info("Preparing documents for MongoDB insertion...")
            for idx, row in tqdm(movies_df.iterrows(), total=len(movies_df), desc="Preparing Docs"):
                mongo_id = ObjectId() # Generate a new unique ID for MongoDB
                movie_id_ml = int(row['movieId']) # Ensure it's int
                movie_id_map[movie_id_ml] = str(mongo_id) # Store mapping

                movie_data = {
                    "_id": mongo_id, # Use generated ObjectId
                    "movieId_ml": movie_id_ml,
                    "title": row['title'],
                    "genres": row['genres_list'],
                    "year": row.get('year'), # Use .get() for safety if column might be missing
                    "embedding": all_embeddings[idx] if idx < len(all_embeddings) else None,
                    # Add other fields if needed (e.g., from links.csv if joined)
                }
                # Validate with Pydantic model before adding (optional but good practice)
                try:
                    # MovieInDB expects '_id', which we provide
                    _ = MovieInDB.model_validate(movie_data)
                    movie_docs_to_insert.append(movie_data)
                except Exception as pydantic_error:
                     logger.warning(f"Skipping movie due to validation error (movieId_ml: {movie_id_ml}): {pydantic_error}")


            # --- Insert into MongoDB ---
            if movie_docs_to_insert:
                logger.info(f"Attempting to insert {len(movie_docs_to_insert)} movie documents into MongoDB collection '{MONGO_COLLECTION_NAME}'...")
                try:
                    # Consider adding an index on movieId_ml if you query by it often
                    # movies_collection.create_index("movieId_ml", unique=True) # If using movieId_ml as _id

                    # Clear existing collection before inserting? Or handle duplicates?
                    # For simplicity, let's assume we clear it for this script run.
                    logger.warning(f"Clearing existing documents in collection '{MONGO_COLLECTION_NAME}' before insertion.")
                    delete_result = await movies_collection.delete_many({})
                    logger.info(f"Deleted {delete_result.deleted_count} existing documents.")

                    # Insert new documents
                    result = await movies_collection.insert_many(movie_docs_to_insert, ordered=False) # ordered=False might be faster
                    inserted_count = len(result.inserted_ids)
                    logger.info(f"Successfully inserted {inserted_count} movie documents.")
                    status_data["mongodb_inserted_count"] = inserted_count
                    if inserted_count != len(movie_docs_to_insert):
                         logger.warning(f"Mismatch: Prepared {len(movie_docs_to_insert)} docs, inserted {inserted_count}.")

                except BulkWriteError as bwe:
                    logger.error(f"MongoDB bulk write error during movie insertion: {bwe.details}", exc_info=True)
                    status_data["mongodb_inserted_count"] = bwe.details.get('nInserted', 0)
                    status_data["mongodb_write_errors"] = len(bwe.details.get('writeErrors', []))
                    raise # Re-raise to mark script as failed
                except PyMongoError as e:
                    logger.error(f"MongoDB error during movie insertion: {e}", exc_info=True)
                    raise
            else:
                logger.warning("No valid movie documents were prepared for insertion.")
                status_data["mongodb_inserted_count"] = 0

            # --- Save movie ID map (Optional but useful for script 03) ---
            # Could save to a file, another DB collection, or just rely on querying movies later
            map_filename = "movie_id_map.json"
            with open(map_filename, 'w') as f:
                json.dump(movie_id_map, f)
            logger.info(f"Saved movieId_ml -> _id map to {map_filename}")
            status_data["id_map_file"] = map_filename


            status_data["status"] = "SUCCESS"
            status_data["message"] = "Successfully generated embeddings and loaded movies to MongoDB."

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