from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
import uuid

class DatasetInfo(BaseModel):
    """Information about a dataset available for recommendation"""
    name: str = Field(..., description="Unique identifier for the dataset")
    display_name: str = Field(..., description="Human-readable name")
    description: str = Field(..., description="Description of the dataset")
    size_bytes: Optional[int] = Field(None, description="Size of dataset in bytes if available")
    num_items: Optional[int] = Field(None, description="Number of items in dataset")
    num_interactions: Optional[int] = Field(None, description="Number of user-item interactions")
    categories: Optional[List[str]] = Field(None, description="Categories in this dataset")
    source_url: Optional[str] = Field(None, description="Original source URL")
    loaded: bool = Field(False, description="Whether the dataset is loaded and ready to use")
    last_updated: Optional[datetime] = Field(None, description="When the dataset was last updated")
    
    class Config:
        schema_extra = {
            "example": {
                "name": "ml-latest-small",
                "display_name": "MovieLens Small Dataset",
                "description": "100,000 ratings and tags for ~9,000 movies by ~700 users",
                "size_bytes": 1000000,
                "num_items": 9000,
                "num_interactions": 100000,
                "categories": ["movies", "ratings"],
                "source_url": "https://grouplens.org/datasets/movielens/latest/",
                "loaded": True,
                "last_updated": "2023-08-01T12:00:00Z"
            }
        }

class DatasetDownloadStatus(BaseModel):
    """Status of dataset download operation"""
    job_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Unique ID for this download job")
    dataset_name: str = Field(..., description="Name of the dataset being downloaded")
    status: str = Field(..., description="Status of the download (PENDING, IN_PROGRESS, COMPLETE, FAILED, ALREADY_EXISTS)")
    message: Optional[str] = Field(None, description="Additional information about the status")
    progress: Optional[float] = Field(None, description="Download progress (0-100%)")
    error: Optional[str] = Field(None, description="Error message if download failed")
    requested_by: str = Field(..., description="ID of the user who requested the download")
    requested_at: datetime = Field(default_factory=datetime.utcnow, description="When download was requested")
    completed_at: Optional[datetime] = Field(None, description="When download completed")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata about the download")
    
    class Config:
        schema_extra = {
            "example": {
                "job_id": "550e8400-e29b-41d4-a716-446655440000",
                "dataset_name": "ml-latest-small",
                "status": "COMPLETE",
                "message": "Dataset successfully downloaded and processed",
                "progress": 100.0,
                "requested_by": "user123",
                "requested_at": "2023-08-01T12:00:00Z",
                "completed_at": "2023-08-01T12:05:00Z"
            }
        } 