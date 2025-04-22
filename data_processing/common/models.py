# Data models (might reuse/adapt from backend/app/models)
# data_processing/common/models.py

import sys
import os
from typing import List, Optional

# --- Option 1: Re-export models from the main application ---
# This is generally preferred to avoid duplication and ensure consistency
# between data processing outputs and backend expectations.

# Adjust the path manipulation based on your project structure and how you run scripts.
# This assumes scripts might be run from the root directory or data_processing directory.
# It tries to add the 'backend' directory to the Python path.
_BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))
if _BACKEND_DIR not in sys.path:
    print(f"Adding backend directory to sys.path: {_BACKEND_DIR}")
    sys.path.insert(0, _BACKEND_DIR)

try:
    # Attempt to import the models needed by data processing scripts
    from app.models.movie import MovieInDB # Model representing full movie doc with embedding
    from app.models.interaction import InteractionType # Enum for interaction types

    # You can re-export them for easier access within data_processing modules
    __all__ = [
        "MovieInDB",
        "InteractionType",
    ]
    print("Successfully imported models from backend app.")

except ImportError as e:
    print(f"Warning: Could not import models from backend app: {e}", file=sys.stderr)
    print("Data processing models might need to be defined locally in data_processing/common/models.py if backend models are unavailable.", file=sys.stderr)
    # Define fallback models here if necessary, but try to avoid it.
    # --- Option 2: Define specific models here (if Option 1 fails or is not desired) ---
    # Only define models here if they are truly specific to data processing
    # or if you cannot easily import from the main app models.
    # Keep them minimal.

    # Example fallback (try to avoid this):
    from pydantic import BaseModel, Field
    from enum import Enum

    class InteractionType(str, Enum):
        RATE = "rate"
        VIEW = "view"
        # ... other types

    class MovieInDB(BaseModel):
        id: str = Field(..., alias="_id")
        movieId_ml: Optional[int] = None
        title: Optional[str] = None
        genres: List[str] = Field(default_factory=list)
        year: Optional[int] = None
        embedding: Optional[List[float]] = None

        class Config:
            populate_by_name = True
            from_attributes = True

    __all__ = [
        "MovieInDB",
        "InteractionType",
    ]


# Example usage within a data processing script:
# from data_processing.common.models import MovieInDB
#
# def process_movie(data):
#     # ... processing logic ...
#     movie_doc = MovieInDB(
#         _id=generate_id(), # Need to handle ID generation/mapping
#         movieId_ml=data['movieId_ml'],
#         title=data['title'],
#         genres=data['genres'],
#         embedding=generate_embedding(data['text'])
#     )
#     return movie_doc.model_dump(by_alias=True) # Use model_dump for Pydantic v2