# backend/app/models/interaction.py

import logging
from datetime import datetime
from enum import Enum
from typing import List, Optional, Any

from pydantic import BaseModel, Field, field_validator, ValidationInfo

logger = logging.getLogger(__name__)

# --- Interaction Type Enum ---
class InteractionType(str, Enum):
    """Defines the allowed types of user interactions."""
    RATE = "rate"
    VIEW = "view"
    LIKE = "like"
    SKIP = "skip"
    BOOKMARK = "bookmark"
    # Add other relevant interaction types

# --- Base Model ---
class InteractionBase(BaseModel):
    """Common attributes for an interaction."""
    movieId: str = Field(..., description="The internal DB ID of the movie being interacted with.")
    type: InteractionType = Field(..., description="The type of interaction performed.")
    value: Optional[float] = Field(None, description="Numerical value associated with the interaction (e.g., rating 0.5-5.0).")

# --- Model for Creating Interactions (API Request Body) ---
class InteractionCreate(InteractionBase):
    """Model used for validating the request body when creating a new interaction."""

    @field_validator('value')
    @classmethod
    def check_value_based_on_type(cls, v: Optional[float], info: ValidationInfo) -> Optional[float]:
        """Validate the 'value' field based on the interaction 'type'."""
        # info.data contains the partially validated data of the model instance being created
        interaction_type = info.data.get('type')

        if interaction_type == InteractionType.RATE:
            if v is None:
                raise ValueError("Interaction value is required for type 'rate'.")
            # Example rating range validation
            if not (0.5 <= v <= 5.0):
                raise ValueError("Rating value must be between 0.5 and 5.0.")
            # Optional: Check for valid increments (e.g., 0.5 steps)
            if v * 2 != int(v * 2):
                 raise ValueError("Rating value must be in 0.5 increments.")
        elif v is not None:
            # For types other than 'rate', value should ideally be null/omitted.
            # Log a warning and enforce null, or raise ValueError for stricter validation.
            logger.warning(f"Value '{v}' provided for non-rate interaction type '{interaction_type}', will be set to null.")
            return None
            # raise ValueError(f"Value should only be provided for type '{InteractionType.RATE.value}'.")
        return v

# --- Models for API Responses ---
class InteractionRead(InteractionBase):
    """Model representing a recorded interaction, including server-generated fields."""
    id: str = Field(..., description="Unique ID of the interaction record.")
    userId: str = Field(..., description="ID of the user who performed the interaction (from JWT).")
    timestamp: datetime = Field(..., description="UTC timestamp when the interaction was recorded.")

    class Config:
        from_attributes = True # Pydantic V2 (was orm_mode = True in V1)

class InteractionReadWithMovie(InteractionRead):
    """Optional response model including basic movie info along with the interaction."""
    # You might use MovieReadSummary here, but often just the title is enough
    movieTitle: Optional[str] = Field(None, description="Title of the interacted movie (denormalized).")

# --- Model for Paginated API Responses ---
# Re-use PaginationData from movie.py or define here if kept separate
# from .movie import PaginationData # Example import

class PaginatedInteractionsResponse(BaseModel):
    """Response structure for paginated interaction lists."""
    pagination: Any # Use PaginationData model here
    items: List[InteractionReadWithMovie] # Use the enriched model for better frontend display