# Settings management (reads env vars/secrets)
# backend/app/core/config.py

import logging
import os
from functools import lru_cache
from typing import List, Optional, Union, Any, Dict

from pydantic import (
    AnyHttpUrl,
    Field,
    PostgresDsn,
    RedisDsn,
    SecretStr,
    ValidationInfo,
    field_validator,
    AnyUrl
)
from pydantic_settings import BaseSettings, SettingsConfigDict

# Set up basic logging configuration early
# In a real app, you might configure logging more elaborately elsewhere
logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO").upper())
logger = logging.getLogger(__name__)

class Settings(BaseSettings):
    """
    Application configuration settings loaded from environment variables or .env file.
    """
    # --- Project Info ---
    PROJECT_NAME: str = Field("MovieLens Recommender API", validation_alias="PROJECT_NAME")
    API_V1_STR: str = Field("/api", validation_alias="API_V1_STR") # Base path for API endpoints
    VERSION: str = Field("1.1.0", validation_alias="APP_VERSION") # Match project version

    # --- Logging ---
    LOG_LEVEL: str = Field("INFO", validation_alias="LOG_LEVEL")

    # --- Database (MongoDB) ---
    # Use SecretStr to prevent accidental logging of the URI
    MONGODB_URI: SecretStr = Field(..., validation_alias="MONGODB_URI")
    MONGODB_DB_NAME: str = Field("movielens", validation_alias="MONGODB_DB_NAME")

    # --- Cache (Redis) ---
    REDIS_URL: Optional[SecretStr] = Field(None, validation_alias="REDIS_URL")
    # Optional: Validate as RedisDsn if using pydantic's built-in DSN types
    # REDIS_URL: RedisDsn = Field(..., validation_alias="REDIS_URL")

    # --- Authentication (Supabase) ---
    SUPABASE_URL: AnyHttpUrl = Field(..., validation_alias="SUPABASE_URL")
    SUPABASE_ANON_KEY: SecretStr = Field(..., validation_alias="SUPABASE_ANON_KEY")
    SUPABASE_SERVICE_ROLE_KEY: Optional[SecretStr] = Field(None, validation_alias="SUPABASE_SERVICE_ROLE_KEY")
    SUPABASE_JWT_SECRET: SecretStr = Field(..., validation_alias="SUPABASE_JWT_SECRET")
    JWT_ALGORITHM: str = Field("HS256", validation_alias="JWT_ALGORITHM")
    JWT_AUDIENCE: str = Field("authenticated", validation_alias="JWT_AUDIENCE")
    # Optional: Validate issuer if needed
    # JWT_ISSUER: Optional[str] = Field(None, validation_alias="JWT_ISSUER")

    # --- NEW: Pub/Sub for Triggering Pipeline ---
    GCP_PROJECT_ID: Optional[str] = Field(None, validation_alias="GCP_PROJECT_ID")
    PIPELINE_TRIGGER_TOPIC_ID: Optional[str] = Field(None, validation_alias="PIPELINE_TRIGGER_TOPIC_ID")

    # --- Embeddings (Hugging Face) ---
    HF_MODEL_NAME: str = Field(
        "sentence-transformers/all-MiniLM-L6-v2",
        validation_alias="HF_MODEL_NAME"
    )

    # --- Storage (GCS) ---
    GCS_BUCKET_NAME: str = Field(..., validation_alias="GCS_BUCKET_NAME")

    # --- CORS ---
    # Expects a comma-separated string in env var like "http://localhost:3000,https://*.example.com"
    BACKEND_CORS_ORIGINS: List[str] = Field(
        ["*"],  # Default to allow all for development
        validation_alias="BACKEND_CORS_ORIGINS"
    )

    @field_validator("BACKEND_CORS_ORIGINS", mode='before')
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> Union[List[str], str]:
        if isinstance(v, str) and not v.startswith("["):
            # If it's a string from env var, split by comma and strip whitespace
            return [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, list):
            return v
        # Allow '*' or handle other cases if necessary
        if v == "*":
            return ["*"]
        raise ValueError(f"Invalid BACKEND_CORS_ORIGINS format: {v}")

    # Pydantic V2 uses model_config dictionary
    model_config = SettingsConfigDict(
        # Load .env file if it exists (useful for local development)
        env_file=".env",
        env_file_encoding='utf-8',
        # Make field names case-insensitive when reading from env
        case_sensitive=False,
        # Allow extra fields from env/dotenv to be ignored
        extra='ignore'
    )

# Use lru_cache to create a singleton instance of the settings
# This ensures settings are loaded only once
@lru_cache()
def get_settings() -> Settings:
    """Returns the application settings instance."""
    logger.info("Attempting to load application settings...")
    try:
        settings_instance = Settings()
        # Log some non-sensitive settings for verification
        logger.info(f"Settings loaded successfully for Project: {settings_instance.PROJECT_NAME}")
        logger.info(f"Log Level: {settings_instance.LOG_LEVEL}")
        logger.info(f"CORS Origins: {settings_instance.BACKEND_CORS_ORIGINS}")
        logger.info(f"HF Model: {settings_instance.HF_MODEL_NAME}")
        logger.info(f"Supabase URL: {settings_instance.SUPABASE_URL}")
        logger.info(f"GCS Bucket: {settings_instance.GCS_BUCKET_NAME or 'Not Set'}")
        # DO NOT log SecretStr values directly in production logs!
        # logger.debug(f"MongoDB URI Loaded: {bool(settings_instance.MONGODB_URI)}")
        # logger.debug(f"Redis URL Loaded: {bool(settings_instance.REDIS_URL)}")
        # logger.debug(f"Supabase JWT Secret Loaded: {bool(settings_instance.SUPABASE_JWT_SECRET)}")
        return settings_instance
    except Exception as e:
        logger.critical(f"CRITICAL ERROR: Failed to load application settings: {e}", exc_info=True)
        # Depending on the severity, you might want to exit or raise a critical error
        raise RuntimeError(f"Could not load settings: {e}")


# Create a single settings instance to be imported by other modules
settings: Settings = get_settings()