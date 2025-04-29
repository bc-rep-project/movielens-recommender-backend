from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
import uuid

class ModelInfo(BaseModel):
    """Information about a trained recommendation model"""
    model_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Unique identifier for the model")
    name: str = Field(..., description="Model name")
    type: str = Field(..., description="Model type (e.g., 'content_based', 'collaborative_filtering')")
    description: Optional[str] = Field(None, description="Model description")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="When the model was created")
    updated_at: Optional[datetime] = Field(None, description="When the model was last updated")
    training_job_id: Optional[str] = Field(None, description="ID of the training job that created this model")
    dataset_name: Optional[str] = Field(None, description="Name of the dataset used for training")
    parameters: Optional[Dict[str, Any]] = Field(None, description="Model parameters/hyperparameters")
    metrics: Optional[Dict[str, float]] = Field(None, description="Model performance metrics")
    active: bool = Field(False, description="Whether this is the active production model")
    
    class Config:
        schema_extra = {
            "example": {
                "model_id": "550e8400-e29b-41d4-a716-446655440000",
                "name": "content_based_model_v1",
                "type": "content_based",
                "description": "Content-based model using TF-IDF embeddings on movie genres",
                "created_at": "2023-08-01T12:00:00Z",
                "dataset_name": "ml-latest-small",
                "parameters": {
                    "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
                    "n_recommendations": 10
                },
                "metrics": {
                    "precision": 0.85,
                    "recall": 0.72
                },
                "active": True
            }
        }

class TrainingRequest(BaseModel):
    """Request to train a new model"""
    model_name: str = Field(..., description="Name for the new model")
    model_type: str = Field(..., description="Type of model to train ('content_based', 'collaborative_filtering', 'hybrid')")
    dataset_name: str = Field(..., description="Dataset to use for training")
    description: Optional[str] = Field(None, description="Model description")
    parameters: Optional[Dict[str, Any]] = Field(None, description="Model training parameters")
    
    class Config:
        schema_extra = {
            "example": {
                "model_name": "content_based_model_v1",
                "model_type": "content_based",
                "dataset_name": "ml-latest-small",
                "description": "Content-based model using movie genres and descriptions",
                "parameters": {
                    "max_features": 5000,
                    "n_components": 100,
                    "min_df": 2
                }
            }
        }

class TrainingJob(BaseModel):
    """Status of a model training job"""
    job_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Unique ID for this training job")
    model_name: str = Field(..., description="Name for the model being trained")
    model_type: str = Field(..., description="Type of model being trained")
    dataset_name: str = Field(..., description="Dataset being used for training")
    status: str = Field(..., description="Training job status (PENDING, IN_PROGRESS, COMPLETE, FAILED)")
    message: Optional[str] = Field(None, description="Additional information about the status")
    progress: Optional[float] = Field(None, description="Training progress (0-100%)")
    error: Optional[str] = Field(None, description="Error message if training failed")
    requested_by: str = Field(..., description="ID of the user who requested the training")
    requested_at: datetime = Field(default_factory=datetime.utcnow, description="When training was requested")
    completed_at: Optional[datetime] = Field(None, description="When training completed")
    model_id: Optional[str] = Field(None, description="ID of the resulting model, if successful")
    metrics: Optional[Dict[str, float]] = Field(None, description="Model performance metrics")
    parameters: Optional[Dict[str, Any]] = Field(None, description="Parameters used for training")
    
    class Config:
        schema_extra = {
            "example": {
                "job_id": "550e8400-e29b-41d4-a716-446655440000",
                "model_name": "content_based_model_v1",
                "model_type": "content_based",
                "dataset_name": "ml-latest-small",
                "status": "COMPLETE",
                "message": "Model successfully trained",
                "progress": 100.0,
                "requested_by": "user123",
                "requested_at": "2023-08-01T12:00:00Z",
                "completed_at": "2023-08-01T12:05:00Z",
                "model_id": "661f9500-e29b-41d4-a716-446655441111",
                "metrics": {
                    "precision": 0.85,
                    "recall": 0.72
                }
            }
        } 