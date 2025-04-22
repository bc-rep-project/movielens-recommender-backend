# Functions to interact with GCS
# data_processing/common/storage_client.py

import logging
import os
from typing import Optional

from dotenv import load_dotenv
from google.cloud import storage
from google.cloud.exceptions import NotFound, GoogleCloudError

logger = logging.getLogger(__name__)

# Load environment variables from .env file in the data_processing directory
dotenv_path = os.path.join(os.path.dirname(__file__), '..', '.env')
load_dotenv(dotenv_path=dotenv_path)

_gcs_client = None # Cache the client instance

def get_gcs_client() -> storage.Client:
    """
    Initializes and returns a Google Cloud Storage client.
    Authentication is handled implicitly via Application Default Credentials (ADC).
    Caches the client instance for potential reuse within a script run.

    Returns:
        A google.cloud.storage.Client instance.

    Raises:
        GoogleCloudError: If the client cannot be created (e.g., ADC not configured).
    """
    global _gcs_client
    if _gcs_client:
        return _gcs_client

    logger.info("Initializing Google Cloud Storage client...")
    try:
        # ADC will be used automatically based on the environment
        # (e.g., gcloud auth application-default login, service account key file, metadata server)
        client = storage.Client()
        # Optional: Test connection by listing buckets (requires permissions)
        # client.list_buckets(max_results=1)
        logger.info("GCS client initialized successfully.")
        _gcs_client = client
        return client
    except GoogleCloudError as e:
        logger.critical(f"Failed to initialize GCS client. Ensure Application Default Credentials (ADC) are configured: {e}", exc_info=True)
        raise
    except Exception as e:
        logger.critical(f"An unexpected error occurred initializing GCS client: {e}", exc_info=True)
        raise

def get_gcs_bucket_name() -> str:
    """
    Retrieves the GCS bucket name from environment variables.

    Returns:
        The GCS bucket name.

    Raises:
        ValueError: If GCS_BUCKET_NAME environment variable is not set.
    """
    bucket_name = os.environ.get("GCS_BUCKET_NAME")
    if not bucket_name:
        logger.critical("GCS_BUCKET_NAME environment variable not set.")
        raise ValueError("GCS_BUCKET_NAME environment variable is required.")
    return bucket_name

def check_gcs_file_exists(object_name: str, bucket_name: Optional[str] = None, gcs_client: storage.Client = None) -> bool:
    """
    Checks if a file (object) exists in the specified GCS bucket.

    Args:
        object_name: The full path/name of the object within the bucket (e.g., "datasets/ml-latest-small.zip").
        bucket_name: The GCS bucket name. If None, attempts to get from env var.
        gcs_client: Optional GCS client instance. If None, a new one is created.

    Returns:
        True if the file exists, False otherwise.
    """
    if gcs_client is None:
        gcs_client = get_gcs_client()
    if bucket_name is None:
        bucket_name = get_gcs_bucket_name()

    try:
        bucket = gcs_client.bucket(bucket_name)
        blob = bucket.blob(object_name)
        exists = blob.exists()
        logger.debug(f"Checked GCS object gs://{bucket_name}/{object_name}. Exists: {exists}")
        return exists
    except GoogleCloudError as e:
        logger.error(f"GCS error checking existence of gs://{bucket_name}/{object_name}: {e}", exc_info=True)
        return False # Treat errors as file not existing for safety? Or re-raise?
    except Exception as e:
        logger.error(f"Unexpected error checking GCS file existence: {e}", exc_info=True)
        return False

def download_gcs_file(object_name: str, destination_path: str, bucket_name: Optional[str] = None, gcs_client: storage.Client = None) -> bool:
    """
    Downloads a file from GCS to a local path.

    Args:
        object_name: The full path/name of the object within the bucket.
        destination_path: The local file path to download to.
        bucket_name: The GCS bucket name. If None, attempts to get from env var.
        gcs_client: Optional GCS client instance. If None, a new one is created.

    Returns:
        True if download was successful, False otherwise.
    """
    if gcs_client is None:
        gcs_client = get_gcs_client()
    if bucket_name is None:
        bucket_name = get_gcs_bucket_name()

    try:
        bucket = gcs_client.bucket(bucket_name)
        blob = bucket.blob(object_name)

        # Ensure destination directory exists
        os.makedirs(os.path.dirname(destination_path), exist_ok=True)

        logger.info(f"Downloading gs://{bucket_name}/{object_name} to {destination_path}...")
        blob.download_to_filename(destination_path)
        logger.info(f"Successfully downloaded gs://{bucket_name}/{object_name}")
        return True
    except NotFound:
        logger.error(f"GCS object not found: gs://{bucket_name}/{object_name}")
        return False
    except GoogleCloudError as e:
        logger.error(f"GCS error downloading gs://{bucket_name}/{object_name}: {e}", exc_info=True)
        return False
    except Exception as e:
        logger.error(f"Unexpected error downloading GCS file: {e}", exc_info=True)
        return False

def upload_gcs_file(source_path: str, destination_object_name: str, bucket_name: Optional[str] = None, gcs_client: storage.Client = None) -> bool:
    """
    Uploads a local file to GCS.

    Args:
        source_path: The path to the local file to upload.
        destination_object_name: The full path/name for the object in the GCS bucket.
        bucket_name: The GCS bucket name. If None, attempts to get from env var.
        gcs_client: Optional GCS client instance. If None, a new one is created.

    Returns:
        True if upload was successful, False otherwise.
    """
    if not os.path.exists(source_path):
        logger.error(f"Source file for upload not found: {source_path}")
        return False

    if gcs_client is None:
        gcs_client = get_gcs_client()
    if bucket_name is None:
        bucket_name = get_gcs_bucket_name()

    try:
        bucket = gcs_client.bucket(bucket_name)
        blob = bucket.blob(destination_object_name)

        logger.info(f"Uploading {source_path} to gs://{bucket_name}/{destination_object_name}...")
        blob.upload_from_filename(source_path)
        logger.info(f"Successfully uploaded to gs://{bucket_name}/{destination_object_name}")
        return True
    except GoogleCloudError as e:
        logger.error(f"GCS error uploading {source_path} to gs://{bucket_name}/{destination_object_name}: {e}", exc_info=True)
        return False
    except Exception as e:
        logger.error(f"Unexpected error uploading GCS file: {e}", exc_info=True)
        return False

# Example usage (usually called from scripts)
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    try:
        client = get_gcs_client()
        bucket = get_gcs_bucket_name()
        print(f"GCS Client Initialized. Using bucket: {bucket}")
        # Example check (replace with a real object name if needed)
        # exists = check_gcs_file_exists("datasets/ml-latest-small.zip")
        # print(f"Test object exists: {exists}")
    except (ValueError, GoogleCloudError) as e:
        print(f"Failed to initialize GCS client or get bucket: {e}", file=sys.stderr)
        sys.exit(1)