# Cloud Function entry point (imports and calls a script)
# data_processing/cloud_function/main.py

import functions_framework
import logging
import os
import sys
import importlib
import json
import traceback

# --- Path Setup ---
# When deployed, the function's root directory contains this main.py.
# We need to add the 'data_processing' directory (which should be deployed alongside main.py)
# to the Python path so we can import scripts like 'scripts.01_download_movielens'.
# This assumes your deployment zip includes the 'scripts' and 'common' directories
# relative to this main.py file. A common structure might be:
# deployment.zip/
#  |- main.py
#  |- requirements.txt
#  |- scripts/
#  |  |- 01_download_movielens.py
#  |  |- ...
#  |- common/
#  |  |- db_connect.py
#  |  |- ...

# Get the directory containing this main.py file
current_dir = os.path.dirname(os.path.abspath(__file__))
# Construct the path to the parent directory (which should contain 'scripts', 'common')
# If main.py is directly inside data_processing/cloud_function, parent is data_processing
# If main.py is at the root alongside data_processing dir, adjust accordingly.
# Assuming main.py is in data_processing/cloud_function:
data_processing_dir = os.path.dirname(current_dir) # This should be 'data_processing' dir

# Add the data_processing directory to the Python path
if data_processing_dir not in sys.path:
    sys.path.insert(0, data_processing_dir)
    print(f"Added to sys.path: {data_processing_dir}")

# Also add the project root if common utils depend on app models/utils
project_root = os.path.abspath(os.path.join(data_processing_dir, '..'))
if project_root not in sys.path:
     sys.path.insert(0, project_root)
     print(f"Added project root to sys.path: {project_root}")


# --- Logging Configuration ---
# Cloud Functions automatically captures stdout/stderr and standard logging
logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO").upper(),
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    stream=sys.stdout) # Ensure logs go to stdout for Cloud Logging
logger = logging.getLogger("CloudFunctionWrapper")


# --- Allowed Scripts ---
# Define which scripts this function is allowed to run for security
ALLOWED_SCRIPTS = {
    "01_download": "scripts.01_download_movielens",
    "02_embeddings": "scripts.02_generate_embeddings",
    "03_interactions": "scripts.03_load_interactions",
    "04_update_recs": "scripts.04_update_recommendations",
}


@functions_framework.http # Decorator for HTTP triggered functions
def run_data_processing_script(request):
    """
    HTTP Cloud Function entry point to trigger a data processing script.
    Expects a JSON payload with a 'script_key' field specifying which script to run.
    Example Payload: {"script_key": "02_embeddings"}
    """
    start_time = time.time()
    logger.info("Cloud Function triggered.")

    # --- Get Script Key from Request ---
    request_json = request.get_json(silent=True)
    request_args = request.args

    script_key = None
    if request_json and 'script_key' in request_json:
        script_key = request_json['script_key']
    elif request_args and 'script_key' in request_args:
        script_key = request_args['script_key']

    if not script_key:
        logger.error("Missing 'script_key' in request JSON body or query parameters.")
        return ("Missing 'script_key' in request JSON body or query parameters.", 400)

    logger.info(f"Received request to run script with key: '{script_key}'")

    # --- Validate and Import Script ---
    if script_key not in ALLOWED_SCRIPTS:
        logger.error(f"Invalid or disallowed script key provided: '{script_key}'")
        allowed_keys = ", ".join(ALLOWED_SCRIPTS.keys())
        return (f"Invalid script_key. Allowed keys: {allowed_keys}", 400)

    module_path = ALLOWED_SCRIPTS[script_key]

    try:
        logger.info(f"Attempting to import module: {module_path}")
        script_module = importlib.import_module(module_path)
        logger.info(f"Successfully imported module: {module_path}")

        # Check if the module has a 'main' function
        if not hasattr(script_module, 'main') or not callable(script_module.main):
            logger.error(f"Module {module_path} does not have a callable 'main' function.")
            return (f"Target script {module_path} is missing a main() function.", 500)

        # --- Execute Script's Main Function ---
        logger.info(f"Executing main() function of {module_path}...")
        # Note: Environment variables (DB URI, GCS Bucket etc.) should be set
        # in the Cloud Function's configuration, ideally referencing Secret Manager.
        # The scripts themselves use os.environ.get() to read them.
        script_module.main() # Call the main function of the imported script
        logger.info(f"Successfully executed main() function of {module_path}.")

        duration = time.time() - start_time
        response_message = f"Successfully executed script: {module_path}"
        logger.info(f"{response_message} (Duration: {duration:.2f}s)")
        return (response_message, 200)

    except ModuleNotFoundError as e:
        logger.error(f"Could not find module {module_path}. Check deployment package structure and sys.path. Error: {e}", exc_info=True)
        return (f"Internal error: Could not find script module {module_path}.", 500)
    except ImportError as e:
         logger.error(f"Import error within {module_path} or its dependencies. Error: {e}", exc_info=True)
         # Log traceback for debugging import issues within the script
         logger.error(traceback.format_exc())
         return (f"Internal error: Import error within script {module_path}.", 500)
    except Exception as e:
        logger.error(f"Error executing main() function of {module_path}: {e}", exc_info=True)
        # Log traceback for debugging runtime errors within the script
        logger.error(traceback.format_exc())
        return (f"Error executing script {module_path}: {e}", 500)

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