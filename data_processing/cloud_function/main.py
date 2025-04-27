# Cloud Function entry point (imports and calls a script)
# data_processing/cloud_function/main.py

import functions_framework
import logging
import os
import sys
import importlib
import json
import traceback
import time
import base64

# --- Path Setup (Ensure this works for your deployment structure) ---
current_dir = os.path.dirname(os.path.abspath(__file__))
data_processing_dir = os.path.dirname(current_dir)
if data_processing_dir not in sys.path:
    sys.path.insert(0, data_processing_dir)
    print(f"Added to sys.path: {data_processing_dir}")
project_root = os.path.abspath(os.path.join(data_processing_dir, '..'))
if project_root not in sys.path:
     sys.path.insert(0, project_root)
     print(f"Added project root to sys.path: {project_root}")

# --- Import common modules AFTER path setup ---
try:
    from data_processing.common.storage_client import get_gcs_client, get_gcs_bucket_name, check_gcs_file_exists
    from data_processing.common.db_connect import get_mongo_database, get_mongo_client
except ImportError as e:
    print(f"Error importing common modules: {e}. Check deployment structure.", file=sys.stderr)
    # Function might still work if only specific scripts are called, but log the error
    pass  # Allow function to load, but script execution might fail later

# --- Logging Configuration ---
logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO").upper(),
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    stream=sys.stdout)
logger = logging.getLogger("PipelineCloudFunction")

# --- Environment Variables (Expected to be set in CF config) ---
GCS_BUCKET_NAME_ENV = "GCS_BUCKET_NAME"
MONGO_DB_NAME_ENV = "MONGODB_DB_NAME"  # Optional, if needed
MONGO_MOVIES_COLLECTION_ENV = "MONGO_MOVIES_COLLECTION"
# Add others needed by the scripts
MOVIELENS_ZIP_FILENAME = os.environ.get("MOVIELENS_ZIP_FILENAME", "ml-latest-small.zip")
GCS_DATASET_PATH = os.environ.get("GCS_DATASET_PATH", "datasets/")

# --- Script Modules to Run (in order) ---
PIPELINE_SCRIPTS = [
    "scripts.01_download_movielens",
    "scripts.02_generate_embeddings",
    "scripts.03_load_interactions",
]

def check_if_pipeline_completed() -> bool:
    """
    Checks if the initial data pipeline seems to be completed.
    This is a simple check, could be made more robust.
    Checks if the movies collection exists and has documents.
    """
    mongo_client = None
    try:
        # Check GCS file first (quick check)
        gcs_client = get_gcs_client()
        bucket_name = get_gcs_bucket_name()  # Reads from env var
        gcs_object_name = os.path.join(GCS_DATASET_PATH.strip('/'), MOVIELENS_ZIP_FILENAME)
        if not check_gcs_file_exists(gcs_object_name, bucket_name, gcs_client):
             logger.info("Pipeline check: GCS dataset zip file not found. Pipeline likely not run.")
             return False

        # Check MongoDB movies collection
        mongo_client = get_mongo_client()
        db = get_mongo_database(client=mongo_client)  # Reads from env var or URI
        movies_collection_name = os.environ.get(MONGO_MOVIES_COLLECTION_ENV, "movies")

        # Check if collection exists and has documents efficiently
        # count_documents is faster than checking list_collection_names + find_one
        count = db[movies_collection_name].count_documents({}, limit=1)

        if count > 0:
            logger.info(f"Pipeline check: Found documents in MongoDB collection '{movies_collection_name}'. Assuming pipeline completed.")
            return True
        else:
            logger.info(f"Pipeline check: MongoDB collection '{movies_collection_name}' is empty or doesn't exist. Pipeline likely not run or failed.")
            return False
    except Exception as e:
        logger.error(f"Error during pipeline completion check: {e}", exc_info=True)
        # Be cautious: if check fails, assume pipeline needs running to be safe
        return False
    finally:
        if mongo_client:
            mongo_client.close()


@functions_framework.cloud_event
def run_movielens_pipeline(cloud_event):
    """
    Pub/Sub triggered Cloud Function to run the initial MovieLens data pipeline.
    Checks if the pipeline has already run before executing.
    """
    start_time = time.time()
    # Decode message data if needed
    try:
        if cloud_event.data and "message" in cloud_event.data and "data" in cloud_event.data["message"]:
            message_data_str = base64.b64decode(cloud_event.data["message"]["data"]).decode('utf-8')
            message_data_json = json.loads(message_data_str)
            logger.info(f"Received trigger message: {message_data_json}")
        else:
            logger.info("Received trigger event without detailed message data.")
    except Exception as e:
        logger.warning(f"Could not decode Pub/Sub message data: {e}")

    logger.info("Checking if data pipeline needs to be executed...")

    # --- Idempotency Check ---
    if check_if_pipeline_completed():
        logger.info("Pipeline already completed. Exiting function.")
        return  # Success, nothing to do

    logger.info("Pipeline not completed. Starting execution...")

    # --- Execute Pipeline Scripts Sequentially ---
    overall_success = True
    for module_path in PIPELINE_SCRIPTS:
        script_start_time = time.time()
        logger.info(f"--- Running script: {module_path} ---")
        try:
            script_module = importlib.import_module(module_path)
            if not hasattr(script_module, 'main') or not callable(script_module.main):
                logger.error(f"Module {module_path} does not have a callable 'main' function. Skipping.")
                overall_success = False
                break  # Stop pipeline if a script is invalid

            # Execute the script's main function
            # The script's main should handle its own logging and status reporting
            script_module.main()
            
            script_duration = time.time() - script_start_time
            logger.info(f"--- Finished script: {module_path} (Duration: {script_duration:.2f}s) ---")

        except Exception as e:
            script_duration = time.time() - script_start_time
            logger.error(f"--- FAILED script: {module_path} (Duration: {script_duration:.2f}s) ---")
            logger.error(f"Error executing main() function of {module_path}: {e}", exc_info=True)
            logger.error(traceback.format_exc())
            overall_success = False
            break  # Stop pipeline execution on first failure

    # --- Final Status ---
    total_duration = time.time() - start_time
    if overall_success:
        logger.info(f"Successfully completed full data pipeline execution. (Total Duration: {total_duration:.2f}s)")
    else:
        logger.error(f"Data pipeline execution failed. (Total Duration: {total_duration:.2f}s)")
        # Let the function fail by raising an exception to signal error for potential retries
        raise RuntimeError("Data pipeline execution failed.")

# --- Example for Pub/Sub Trigger (Alternative) ---
# import base64
#
# @functions_framework.cloud_event
# def run_data_processing_pubsub(cloud_event):
#     """
#     Pub/Sub triggered Cloud Function.
#     Expects message attributes or data to specify the script_key.
#     Example Attribute: {'script_key': '02_embeddings'}
#     Example Data (Base64): base64.b64encode(b'{"script_key":"02_embeddings"}').decode()
#     """
#     logger.info("Pub/Sub Cloud Function triggered.")
#     script_key = None
#
#     # Check attributes first
#     if cloud_event.data and "message" in cloud_event.data and "attributes" in cloud_event.data["message"]:
#         script_key = cloud_event.data["message"]["attributes"].get("script_key")
#
#     # Check data field if not in attributes
#     if not script_key and cloud_event.data and "message" in cloud_event.data and "data" in cloud_event.data["message"]:
#         try:
#             message_data_str = base64.b64decode(cloud_event.data["message"]["data"]).decode('utf-8')
#             message_data_json = json.loads(message_data_str)
#             script_key = message_data_json.get("script_key")
#         except (json.JSONDecodeError, ValueError, TypeError) as e:
#             logger.warning(f"Could not decode Pub/Sub message data as JSON: {e}")
#
#     if not script_key:
#         logger.error("Missing 'script_key' in Pub/Sub message attributes or data.")
#         # No return value needed for background functions, just log error
#         return
#
#     logger.info(f"Received request to run script with key: '{script_key}'")
#
#     # --- Validate and Import Script (Same as HTTP version) ---
#     if script_key not in ALLOWED_SCRIPTS:
#         logger.error(f"Invalid or disallowed script key provided: '{script_key}'")
#         return
#
#     module_path = ALLOWED_SCRIPTS[script_key]
#
#     try:
#         logger.info(f"Attempting to import module: {module_path}")
#         script_module = importlib.import_module(module_path)
#         logger.info(f"Successfully imported module: {module_path}")
#
#         if not hasattr(script_module, 'main') or not callable(script_module.main):
#             logger.error(f"Module {module_path} does not have a callable 'main' function.")
#             return
#
#         # --- Execute Script's Main Function ---
#         logger.info(f"Executing main() function of {module_path}...")
#         script_module.main()
#         logger.info(f"Successfully executed main() function of {module_path}.")
#
#     except Exception as e:
#         logger.error(f"Error executing main() function of {module_path}: {e}", exc_info=True)
#         logger.error(traceback.format_exc())
#         # Let the function fail to signal error to Cloud Functions/PubSub for potential retries
#         raise e