# Downloads data from URL to GCS (checks existence first)
# data_processing/scripts/01_download_movielens.py

import logging
import os
import sys
import json
import tempfile

import requests
from dotenv import load_dotenv

# Add project root to path to allow importing common modules
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Now import common modules AFTER adjusting path
try:
    from data_processing.common.storage_client import (
        get_gcs_client,
        get_gcs_bucket_name,
        check_gcs_file_exists,
        upload_gcs_file,
    )
except ImportError as e:
    print(f"Error importing common modules: {e}. Make sure PYTHONPATH is set correctly or run from project root.", file=sys.stderr)
    sys.exit(1)


# --- Configuration ---
logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO").upper(),
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load .env file from data_processing directory
dotenv_path = os.path.join(os.path.dirname(__file__), '..', '.env')
load_dotenv(dotenv_path=dotenv_path)

MOVIELENS_URL = os.environ.get("MOVIELENS_URL", "https://files.grouplens.org/datasets/movielens/ml-latest-small.zip")
MOVIELENS_ZIP_FILENAME = os.environ.get("MOVIELENS_ZIP_FILENAME", "ml-latest-small.zip")
GCS_DATASET_PATH = os.environ.get("GCS_DATASET_PATH", "datasets/") # Ensure trailing slash if it's a path


def main():
    """
    Downloads the MovieLens dataset zip file and uploads it to GCS if it doesn't already exist.
    """
    status_data = {"script": os.path.basename(__file__), "status": "STARTED"}
    logger.info(f"Starting script: {status_data['script']}")

    try:
        gcs_client = get_gcs_client()
        bucket_name = get_gcs_bucket_name()
        # Ensure path ends with / if it's meant to be a directory prefix
        gcs_object_name = os.path.join(GCS_DATASET_PATH.strip('/'), MOVIELENS_ZIP_FILENAME)
        status_data["gcs_destination_uri"] = f"gs://{bucket_name}/{gcs_object_name}"
        status_data["source_url"] = MOVIELENS_URL

        logger.info(f"Checking if object exists: {status_data['gcs_destination_uri']}")
        if check_gcs_file_exists(gcs_object_name, bucket_name, gcs_client):
            logger.info("Dataset already exists in GCS. Skipping download.")
            status_data["status"] = "SKIPPED"
            status_data["message"] = "Dataset already exists in GCS."
            print(json.dumps(status_data, indent=2))
            return

        logger.info(f"Dataset not found in GCS. Downloading from {MOVIELENS_URL}...")

        # Download to a temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as temp_file:
            try:
                with requests.get(MOVIELENS_URL, stream=True, timeout=120) as r: # Added timeout
                    r.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
                    total_downloaded = 0
                    for chunk in r.iter_content(chunk_size=8192):
                        temp_file.write(chunk)
                        total_downloaded += len(chunk)
                    logger.info(f"Downloaded {total_downloaded / (1024*1024):.2f} MB to {temp_file.name}")
                temp_file_path = temp_file.name
                status_data["download_size_bytes"] = total_downloaded

                # Upload the temporary file to GCS
                logger.info(f"Uploading {temp_file_path} to {status_data['gcs_destination_uri']}...")
                upload_success = upload_gcs_file(
                    source_path=temp_file_path,
                    destination_object_name=gcs_object_name,
                    bucket_name=bucket_name,
                    gcs_client=gcs_client
                )

                if upload_success:
                    logger.info("Successfully uploaded dataset to GCS.")
                    status_data["status"] = "SUCCESS"
                    status_data["message"] = "Dataset downloaded and uploaded to GCS."
                else:
                    logger.error("Failed to upload dataset to GCS.")
                    status_data["status"] = "FAILURE"
                    status_data["message"] = "Failed during GCS upload phase."
                    status_data["error_details"] = "Upload function returned False."

            except requests.exceptions.RequestException as e:
                logger.error(f"Failed to download dataset from {MOVIELENS_URL}: {e}", exc_info=True)
                status_data["status"] = "FAILURE"
                status_data["message"] = "Failed during download phase."
                status_data["error_details"] = str(e)
            except Exception as e:
                 logger.error(f"An unexpected error occurred: {e}", exc_info=True)
                 status_data["status"] = "FAILURE"
                 status_data["message"] = "An unexpected error occurred."
                 status_data["error_details"] = str(e)
            finally:
                # Clean up the temporary file
                if 'temp_file_path' in locals() and os.path.exists(temp_file_path):
                    os.remove(temp_file_path)
                    logger.info(f"Removed temporary file: {temp_file_path}")

    except Exception as e:
        logger.critical(f"Script failed critically: {e}", exc_info=True)
        status_data["status"] = "CRITICAL_FAILURE"
        status_data["message"] = "Script failed due to an unhandled exception."
        status_data["error_details"] = str(e)

    # Output final status as JSON
    print(json.dumps(status_data, indent=2))
    if "FAILURE" in status_data["status"]:
        sys.exit(1)

if __name__ == "__main__":
    main()