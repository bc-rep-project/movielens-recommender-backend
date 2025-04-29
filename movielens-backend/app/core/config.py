# Settings management (reads env vars/secrets)
# backend/app/core/config.py

import logging
import os
from functools import lru_cache
from typing import List, Optional, Union, Any

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
    # Optional: Specify DB name if not in URI or want to override
    # MONGODB_DB_NAME: str = Field("movielens_db", validation_alias="MONGODB_DB_NAME")

    # --- Cache (Redis) ---
    REDIS_URL: SecretStr = Field(..., validation_alias="REDIS_URL")
    # Optional: Validate as RedisDsn if using pydantic's built-in DSN types
    # REDIS_URL: RedisDsn = Field(..., validation_alias="REDIS_URL")

    # --- Authentication (Supabase) ---
    SUPABASE_URL: AnyHttpUrl = Field(..., validation_alias="SUPABASE_URL")
    # SUPABASE_ANON_KEY: Optional[SecretStr] = Field(None, validation_alias="SUPABASE_ANON_KEY") # Likely not needed backend
    SUPABASE_SERVICE_ROLE_KEY: Optional[SecretStr] = Field(None, validation_alias="SUPABASE_SERVICE_ROLE_KEY") # Needed for admin actions
    SUPABASE_JWT_SECRET: SecretStr = Field(..., validation_alias="SUPABASE_JWT_SECRET") # CRITICAL for verifying user tokens
    JWT_ALGORITHM: str = Field("HS256", validation_alias="JWT_ALGORITHM")
    JWT_AUDIENCE: str = Field("authenticated", validation_alias="JWT_AUDIENCE")
    # Optional: Validate issuer if needed
    # JWT_ISSUER: Optional[str] = Field(None, validation_alias="JWT_ISSUER")

    # --- Embeddings (Hugging Face) ---
    HF_MODEL_NAME: str = Field(
        "sentence-transformers/all-MiniLM-L6-v2",
        validation_alias="HF_MODEL_NAME"
    )
    
    # --- Dataset Settings ---
    SUPPORTED_DATASETS: List[str] = Field(
        default=["ml-latest-small", "ml-25m"],
        validation_alias="SUPPORTED_DATASETS"
    )
    
    # --- Storage (S3/GCS) ---
    GCS_BUCKET_NAME: Optional[str] = Field(None, validation_alias="GCS_BUCKET_NAME")
    STORAGE_ENDPOINT_URL: Optional[str] = Field(
        None, 
        validation_alias="STORAGE_ENDPOINT_URL",
        description="Endpoint for S3-compatible storage. Use None for GCS."
    )
    STORAGE_ACCESS_KEY: Optional[SecretStr] = Field(
        None,
        validation_alias="STORAGE_ACCESS_KEY",
        description="Access key for S3-compatible storage. Use None for GCS with default credentials."
    )
    STORAGE_SECRET_KEY: Optional[SecretStr] = Field(
        None,
        validation_alias="STORAGE_SECRET_KEY",
        description="Secret key for S3-compatible storage. Use None for GCS with default credentials."
    )
    
    # --- Model Training ---
    MAX_TRAINING_TIME_SECONDS: int = Field(
        default=300,  # 5 minutes max for Cloud Run free tier
        validation_alias="MAX_TRAINING_TIME_SECONDS",
        description="Maximum allowed training time in seconds to prevent Cloud Run timeout"
    )
    MAX_MEMORY_USAGE_MB: int = Field(
        default=400,  # 400MB max for 512MB Cloud Run instance
        validation_alias="MAX_MEMORY_USAGE_MB",
        description="Maximum memory usage for training to prevent OOM errors"
    )
    OFFLOAD_LARGE_TASKS: bool = Field(
        default=True,
        validation_alias="OFFLOAD_LARGE_TASKS",
        description="Whether to offload large tasks to external services (Cloud Functions)"
    )
    
    # --- Cache Settings ---
    CACHE_TTL_RECOMMENDATIONS: int = Field(
        default=3600,  # 1 hour
        validation_alias="CACHE_TTL_RECOMMENDATIONS",
        description="Time-to-live for cached recommendations in seconds"
    )
    CACHE_TTL_MODELS: int = Field(
        default=86400,  # 24 hours
        validation_alias="CACHE_TTL_MODELS",
        description="Time-to-live for cached model metadata in seconds"
    )

    # --- CORS ---
    # Expects a comma-separated string in env var like "http://localhost:3000,https://*.example.com"
    BACKEND_CORS_ORIGINS: List[str] = Field(
        default=["*"], # Allows all origins by default - CHANGE FOR PRODUCTION!
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

    @field_validator("SUPPORTED_DATASETS", mode='before')
    @classmethod
    def assemble_supported_datasets(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str) and not v.startswith("["):
            # If it's a string from env var, split by comma and strip whitespace
            return [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, list):
            return v
        return ["ml-latest-small"]  # Default dataset

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