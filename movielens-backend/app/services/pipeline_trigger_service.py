import logging
import json
from datetime import datetime, timezone
from google.cloud import pubsub_v1
from google.api_core.exceptions import GoogleAPICallError

from app.core.config import settings

logger = logging.getLogger(__name__)

class PipelineTriggerService:
    def __init__(self):
        self.project_id = settings.GCP_PROJECT_ID
        self.topic_id = settings.PIPELINE_TRIGGER_TOPIC_ID
        self.publisher = None
        self.topic_path = None

        if self.project_id and self.topic_id:
            try:
                self.publisher = pubsub_v1.PublisherClient()
                self.topic_path = self.publisher.topic_path(self.project_id, self.topic_id)
                logger.info(f"Pub/Sub Publisher initialized for topic: {self.topic_path}")
            except Exception as e:
                logger.error(f"Failed to initialize Pub/Sub publisher: {e}", exc_info=True)
                self.publisher = None  # Ensure it's None if init fails
        else:
            logger.warning("GCP_PROJECT_ID or PIPELINE_TRIGGER_TOPIC_ID not configured. Pipeline trigger disabled.")

    async def trigger_pipeline_if_needed(self, user_id: str, email: str) -> bool:
        """
        Publishes a message to trigger the data pipeline check.
        The actual check for whether the pipeline *needs* to run happens
        in the subscriber (Cloud Function).
        """
        if not self.publisher or not self.topic_path:
            logger.warning("Pub/Sub publisher not available. Skipping pipeline trigger.")
            return False

        message_data = {
            "message": "New user registered, check if data pipeline needs execution.",
            "userId": user_id,
            "email": email,
            "trigger_timestamp": datetime.now(timezone.utc).isoformat()
        }
        message_bytes = json.dumps(message_data).encode("utf-8")

        try:
            logger.info(f"Publishing pipeline trigger message for user {user_id} to {self.topic_path}...")
            # Publish the message
            future = self.publisher.publish(self.topic_path, message_bytes)
            message_id = future.result(timeout=10)  # Wait for publish confirmation (adjust timeout)
            logger.info(f"Successfully published message {message_id} for user {user_id}.")
            return True
        except GoogleAPICallError as e:
            logger.error(f"Pub/Sub API error publishing trigger message: {e}", exc_info=True)
            return False
        except TimeoutError:
            logger.error(f"Timeout waiting for Pub/Sub publish confirmation for user {user_id}.")
            return False
        except Exception as e:
            logger.error(f"Unexpected error publishing trigger message: {e}", exc_info=True)
            return False 