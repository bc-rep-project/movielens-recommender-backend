import logging
import json
import os
import pickle
import numpy as np
import tempfile
from datetime import datetime
from typing import List, Optional, Dict, Any, Tuple
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import tensorflow as tf
from tensorflow.keras import Model, layers, optimizers, regularizers
from sentence_transformers import SentenceTransformer

from ..core.config import settings
from ..models.model import ModelInfo, TrainingJob
from ..data_access.mongodb import get_collection

logger = logging.getLogger(__name__)

class ModelService:
    def __init__(
        self,
        mongodb_client: AsyncIOMotorClient,
        redis_client = None,
        storage_client = None
    ):
        """Initialize model service with DB connections"""
        self.mongodb_client = mongodb_client
        self.redis_client = redis_client
        self.storage_client = storage_client
        
        # Collection references
        self.models_collection = get_collection(mongodb_client, "models")
        self.training_jobs_collection = get_collection(mongodb_client, "training_jobs")
        self.movies_collection = get_collection(mongodb_client, "movies")
        self.ratings_collection = get_collection(mongodb_client, "ratings")
        self.embeddings_collection = get_collection(mongodb_client, "movie_embeddings")
        
    async def list_models(self) -> List[ModelInfo]:
        """List all available trained models"""
        models = []
        async for doc in self.models_collection.find():
            # Convert MongoDB doc to ModelInfo model
            # Exclude MongoDB _id field
            doc_without_id = {k: v for k, v in doc.items() if k != '_id'}
            models.append(ModelInfo(**doc_without_id))
        return models
    
    async def get_model(self, model_id: str) -> Optional[ModelInfo]:
        """Get details for a specific model"""
        doc = await self.models_collection.find_one({"model_id": model_id})
        if not doc:
            return None
        
        # Convert MongoDB doc to ModelInfo model
        # Exclude MongoDB _id field
        doc_without_id = {k: v for k, v in doc.items() if k != '_id'}
        return ModelInfo(**doc_without_id)
    
    async def get_active_model(self, model_type: Optional[str] = None) -> Optional[ModelInfo]:
        """Get the currently active model of the specified type"""
        query = {"active": True}
        if model_type:
            query["type"] = model_type
            
        doc = await self.models_collection.find_one(query)
        if not doc:
            return None
            
        # Convert MongoDB doc to ModelInfo model
        # Exclude MongoDB _id field
        doc_without_id = {k: v for k, v in doc.items() if k != '_id'}
        return ModelInfo(**doc_without_id)
    
    async def activate_model(self, model_id: str) -> Optional[ModelInfo]:
        """Set a model as the active one for its type"""
        model = await self.get_model(model_id)
        if not model:
            return None
            
        # First, deactivate the current active model of this type
        await self.models_collection.update_many(
            {"type": model.type, "active": True},
            {"$set": {"active": False}}
        )
        
        # Then, activate the requested model
        await self.models_collection.update_one(
            {"model_id": model_id},
            {"$set": {"active": True, "updated_at": datetime.utcnow()}}
        )
        
        # Get the updated model
        return await self.get_model(model_id)
    
    async def get_job_status(self, job_id: str) -> Optional[TrainingJob]:
        """Get the status of a training job"""
        doc = await self.training_jobs_collection.find_one({"job_id": job_id})
        if not doc:
            return None
            
        # Convert MongoDB doc to TrainingJob model
        # Exclude MongoDB _id field
        doc_without_id = {k: v for k, v in doc.items() if k != '_id'}
        return TrainingJob(**doc_without_id)
    
    async def update_job_status(self, job_id: str, updates: Dict[str, Any]) -> None:
        """Update a job's status in the database"""
        await self.training_jobs_collection.update_one(
            {"job_id": job_id},
            {"$set": updates}
        )
    
    async def start_model_training(
        self,
        model_name: str,
        model_type: str,
        dataset_name: str,
        description: Optional[str] = None,
        parameters: Optional[Dict[str, Any]] = None,
        user_id: str = "system"
    ) -> TrainingJob:
        """
        Start a model training job and return the initial status.
        This method is optimized for Cloud Run by:
        1. Creating a job record and returning immediately
        2. Performing actual training in a background task
        3. Breaking up computationally intensive tasks
        4. Using appropriate model sizes
        """
        # Validate model type
        valid_types = ["content_based", "collaborative_filtering", "hybrid"]
        if model_type not in valid_types:
            raise ValueError(f"Invalid model type: {model_type}. Valid options: {', '.join(valid_types)}")
            
        # Ensure parameters is a dict
        if parameters is None:
            parameters = {}
            
        # Set defaults based on model type
        if model_type == "content_based":
            parameters.setdefault("embedding_model", "sentence-transformers/all-MiniLM-L6-v2")
            parameters.setdefault("use_genres", True)
            parameters.setdefault("use_titles", True)
            parameters.setdefault("n_recommendations", 10)
        elif model_type == "collaborative_filtering":
            parameters.setdefault("n_factors", 50)
            parameters.setdefault("n_epochs", 20)
            parameters.setdefault("learning_rate", 0.005)
            parameters.setdefault("regularization", 0.02)
            parameters.setdefault("batch_size", 512)
        elif model_type == "hybrid":
            parameters.setdefault("content_weight", 0.5)
            parameters.setdefault("collaborative_weight", 0.5)
            parameters.setdefault("n_recommendations", 10)
        
        # Create a new job record
        job = TrainingJob(
            model_name=model_name,
            model_type=model_type,
            dataset_name=dataset_name,
            status="PENDING",
            message=f"Training job for {model_name} queued",
            requested_by=user_id,
            progress=0.0,
            parameters=parameters
        )
        
        # Store the job in MongoDB
        await self.training_jobs_collection.insert_one(job.dict())
        
        return job
    
    async def process_model_training(
        self,
        job_id: str
    ) -> None:
        """
        Process a model training job. This is run as a background task.
        
        It's designed to optimize Cloud Run resource usage by:
        - Using lightweight model architectures
        - Processing data in chunks
        - Saving partial results to avoid memory issues
        - Being mindful of computation required
        """
        try:
            # Get the job details
            job_doc = await self.training_jobs_collection.find_one({"job_id": job_id})
            if not job_doc:
                logger.error(f"Training job {job_id} not found")
                return
                
            # Remove MongoDB _id field and convert to TrainingJob object
            job_doc.pop("_id", None)
            job = TrainingJob(**job_doc)
            
            # Update status to in-progress
            await self.update_job_status(job_id, {
                "status": "IN_PROGRESS",
                "message": "Starting model training",
                "progress": 5.0
            })
            
            # Choose the appropriate training method based on model type
            if job.model_type == "content_based":
                model_id = await self._train_content_based_model(job)
            elif job.model_type == "collaborative_filtering":
                model_id = await self._train_collaborative_filtering_model(job)
            elif job.model_type == "hybrid":
                model_id = await self._train_hybrid_model(job)
            else:
                raise ValueError(f"Unsupported model type: {job.model_type}")
                
            # Update the job with the model ID and completed status
            await self.update_job_status(job_id, {
                "status": "COMPLETE",
                "message": "Model training completed successfully",
                "progress": 100.0,
                "completed_at": datetime.utcnow(),
                "model_id": model_id
            })
            
        except Exception as e:
            logger.error(f"Error training model: {str(e)}", exc_info=True)
            
            # Update job status to failed
            await self.update_job_status(job_id, {
                "status": "FAILED",
                "error": str(e),
                "message": f"Training failed: {str(e)}",
                "completed_at": datetime.utcnow()
            })
    
    async def _train_content_based_model(self, job: TrainingJob) -> str:
        """
        Train a content-based recommendation model using movie features and embeddings.
        Optimized for Cloud Run free tier by using pre-computed embeddings where possible.
        
        Returns the model_id of the created model.
        """
        logger.info(f"Training content-based model: {job.model_name}")
        
        # Update status
        await self.update_job_status(job.job_id, {
            "progress": 10.0,
            "message": "Loading movie data"
        })
        
        # Get the parameters
        embedding_model_name = job.parameters.get("embedding_model", "sentence-transformers/all-MiniLM-L6-v2")
        use_genres = job.parameters.get("use_genres", True)
        use_titles = job.parameters.get("use_titles", True)
        
        # First check if movie embeddings already exist
        embedding_count = await self.embeddings_collection.count_documents({
            "model": embedding_model_name
        })
        
        # Get all movies
        movies = []
        async for doc in self.movies_collection.find():
            movies.append(doc)
            
        if not movies:
            raise ValueError("No movies found in the database. Please load a dataset first.")
            
        # Update status
        await self.update_job_status(job.job_id, {
            "progress": 20.0,
            "message": "Preparing movie features"
        })
        
        # Prepare movie features for embedding
        movie_texts = []
        movie_ids = []
        
        for movie in movies:
            # Create text representation of movie
            features = []
            
            if use_titles and "title" in movie:
                features.append(str(movie["title"]))
                
            if use_genres and "genres" in movie and movie["genres"]:
                # Handle both string and list formats
                if isinstance(movie["genres"], list):
                    features.append(" ".join(movie["genres"]))
                elif isinstance(movie["genres"], str):
                    features.append(movie["genres"].replace("|", " "))
                    
            # Skip movies with no features
            if not features:
                continue
                
            movie_text = " ".join(features)
            movie_texts.append(movie_text)
            movie_ids.append(str(movie["movieId"]))
            
        # Check if we need to compute new embeddings
        if embedding_count < len(movie_ids):
            # Update status
            await self.update_job_status(job.job_id, {
                "progress": 30.0,
                "message": f"Computing embeddings using {embedding_model_name}"
            })
            
            # Load the Sentence Transformer model
            # Wrap in a try-catch to use fallbacks if it fails
            try:
                # Try to load the specified model
                model = SentenceTransformer(embedding_model_name)
            except Exception as e:
                logger.warning(f"Failed to load model {embedding_model_name}: {e}")
                logger.info("Falling back to TfidfVectorizer")
                
                # Fallback to TF-IDF if Sentence Transformer fails
                # This is much more memory-efficient and suitable for free tier
                vectorizer = TfidfVectorizer(max_features=1000)
                sparse_embeddings = vectorizer.fit_transform(movie_texts)
                
                # Convert sparse matrix to dense array
                embeddings = sparse_embeddings.toarray()
                
                # Save the vectorizer for future use
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pkl") as f:
                    pickle.dump(vectorizer, f)
                    vectorizer_path = f.name
                    
                embedding_source = "tfidf"
            else:
                # Sentence Transformer loaded successfully
                # Compute embeddings in small batches to avoid memory issues
                batch_size = 32  # Small batch size for Cloud Run
                embeddings = []
                
                for i in range(0, len(movie_texts), batch_size):
                    batch = movie_texts[i:i+batch_size]
                    # Encode without normalization
                    batch_embeddings = model.encode(batch, show_progress_bar=False)
                    embeddings.extend(batch_embeddings)
                    # Force garbage collection
                    tf.keras.backend.clear_session()
                    # Allow other tasks to run
                    await asyncio.sleep(0)
                
                # Convert to numpy array
                embeddings = np.array(embeddings)
                embedding_source = embedding_model_name
                
            # Update status
            await self.update_job_status(job.job_id, {
                "progress": 70.0, 
                "message": "Storing embeddings"
            })
            
            # Store the embeddings in MongoDB (in batches)
            batch_size = 100  # Store in reasonable batches
            
            for i in range(0, len(movie_ids), batch_size):
                batch_ids = movie_ids[i:i+batch_size]
                batch_embeddings = embeddings[i:i+batch_size]
                
                # Prepare documents for insertion
                embedding_docs = []
                
                for j, movie_id in enumerate(batch_ids):
                    embedding_vector = batch_embeddings[j].tolist()
                    
                    embedding_docs.append({
                        "movieId": movie_id,
                        "model": embedding_source,
                        "embedding": embedding_vector,
                        "created_at": datetime.utcnow()
                    })
                
                # Skip empty batches
                if not embedding_docs:
                    continue
                    
                # Insert or update embeddings
                for doc in embedding_docs:
                    await self.embeddings_collection.update_one(
                        {"movieId": doc["movieId"], "model": doc["model"]},
                        {"$set": doc},
                        upsert=True
                    )
                
                # Allow other tasks to run
                await asyncio.sleep(0)
                
            # Create an index on movieId and model
            await self.embeddings_collection.create_index([("movieId", 1), ("model", 1)], unique=True)
        
        # Create the model object
        model_info = ModelInfo(
            name=job.model_name,
            type=job.model_type,
            description=job.description or f"Content-based model using {embedding_source}",
            training_job_id=job.job_id,
            dataset_name=job.dataset_name,
            parameters={
                "embedding_model": embedding_source,
                "use_genres": use_genres,
                "use_titles": use_titles,
                "n_recommendations": job.parameters.get("n_recommendations", 10)
            },
            metrics={
                "embedding_dimension": embeddings[0].shape[0] if len(embeddings) > 0 else 0,
                "num_items": len(movie_ids)
            },
            active=False  # Not active initially
        )
        
        # Store the model in MongoDB
        await self.models_collection.insert_one(model_info.dict())
        
        # If no active model of this type exists, make this one active
        active_model = await self.get_active_model(model_info.type)
        if not active_model:
            await self.activate_model(model_info.model_id)
            
        # Return the model ID
        return model_info.model_id
    
    async def _train_collaborative_filtering_model(self, job: TrainingJob) -> str:
        """
        Train a collaborative filtering model using user-item interactions.
        Optimized for Cloud Run free tier by using smaller model size and batch processing.
        
        Returns the model_id of the created model.
        """
        logger.info(f"Training collaborative filtering model: {job.model_name}")
        
        # Update status
        await self.update_job_status(job.job_id, {
            "progress": 10.0,
            "message": "Loading ratings data"
        })
        
        # Get model parameters
        n_factors = job.parameters.get("n_factors", 50)  # Smaller for free tier
        n_epochs = job.parameters.get("n_epochs", 20)
        learning_rate = job.parameters.get("learning_rate", 0.005)
        regularization = job.parameters.get("regularization", 0.02)
        batch_size = job.parameters.get("batch_size", 512)
        
        # Load ratings data
        ratings = []
        async for doc in self.ratings_collection.find():
            ratings.append({
                "userId": doc["userId"],
                "movieId": doc["movieId"],
                "rating": doc["rating"]
            })
            
        if not ratings:
            raise ValueError("No ratings found in the database. Please load a dataset first.")
            
        # Convert to numpy arrays
        # Get unique user and movie IDs
        user_ids = sorted(list(set(r["userId"] for r in ratings)))
        movie_ids = sorted(list(set(r["movieId"] for r in ratings)))
        
        # Create mappings between IDs and indices
        user_to_idx = {user_id: i for i, user_id in enumerate(user_ids)}
        movie_to_idx = {movie_id: i for i, movie_id in enumerate(movie_ids)}
        idx_to_user = {i: user_id for user_id, i in user_to_idx.items()}
        idx_to_movie = {i: movie_id for movie_id, i in movie_to_idx.items()}
        
        # Update status
        await self.update_job_status(job.job_id, {
            "progress": 20.0,
            "message": "Preparing training data"
        })
        
        # Create training data
        user_indices = np.array([user_to_idx[r["userId"]] for r in ratings])
        movie_indices = np.array([movie_to_idx[r["movieId"]] for r in ratings])
        
        # Normalize ratings to [0, 1] range for better training performance
        # Assuming ratings are in [0.5, 5] range
        rating_values = np.array([r["rating"] for r in ratings])
        normalized_ratings = (rating_values - 0.5) / 4.5  # Normalize to [0, 1]
        
        # Build a simple matrix factorization model using TensorFlow
        # This is much lighter than a full neural network and suitable for free tier
        class MatrixFactorizationModel(Model):
            def __init__(self, num_users, num_items, embedding_dim, **kwargs):
                super().__init__(**kwargs)
                self.user_embedding = layers.Embedding(
                    num_users,
                    embedding_dim,
                    embeddings_initializer="glorot_normal",
                    embeddings_regularizer=regularizers.l2(regularization)
                )
                self.item_embedding = layers.Embedding(
                    num_items,
                    embedding_dim,
                    embeddings_initializer="glorot_normal",
                    embeddings_regularizer=regularizers.l2(regularization)
                )
                self.user_bias = layers.Embedding(num_users, 1)
                self.item_bias = layers.Embedding(num_items, 1)
            
            def call(self, inputs):
                user_vector = self.user_embedding(inputs[:, 0])
                item_vector = self.item_embedding(inputs[:, 1])
                user_bias = self.user_bias(inputs[:, 0])
                item_bias = self.item_bias(inputs[:, 1])
                
                # Dot product of user and item vectors
                dot_product = tf.reduce_sum(tf.multiply(user_vector, item_vector), axis=1)
                
                # Add bias terms
                return tf.nn.sigmoid(dot_product + user_bias[:, 0] + item_bias[:, 0])
        
        # Update status
        await self.update_job_status(job.job_id, {
            "progress": 30.0,
            "message": "Building model"
        })
        
        # Create the model
        model = MatrixFactorizationModel(len(user_ids), len(movie_ids), n_factors)
        
        # Compile the model
        model.compile(
            optimizer=optimizers.Adam(learning_rate=learning_rate),
            loss='mean_squared_error',
            metrics=['mae']
        )
        
        # Prepare input data as user-item pairs
        X = np.column_stack((user_indices, movie_indices))
        y = normalized_ratings
        
        # Update status
        await self.update_job_status(job.job_id, {
            "progress": 40.0,
            "message": "Training model"
        })
        
        # Train the model
        epochs_per_update = max(1, n_epochs // 10)  # Update status every 10% of training
        
        for epoch in range(0, n_epochs, epochs_per_update):
            # Calculate number of epochs for this batch
            n_epochs_batch = min(epochs_per_update, n_epochs - epoch)
            
            # Train for a few epochs
            history = model.fit(
                X, y,
                batch_size=batch_size,
                epochs=n_epochs_batch,
                verbose=0,
                shuffle=True
            )
            
            # Update progress
            progress = 40.0 + (50.0 * (epoch + n_epochs_batch) / n_epochs)
            await self.update_job_status(job.job_id, {
                "progress": progress,
                "message": f"Training epoch {epoch + n_epochs_batch}/{n_epochs}"
            })
            
            # Allow other tasks to run
            await asyncio.sleep(0)
            
            # Force garbage collection
            tf.keras.backend.clear_session()
        
        # Extract embeddings for all users and items
        user_embeddings = model.user_embedding.get_weights()[0]
        movie_embeddings = model.item_embedding.get_weights()[0]
        user_biases = model.user_bias.get_weights()[0]
        movie_biases = model.item_bias.get_weights()[0]
        
        # Save the model to MongoDB for collaborative filtering recommendations
        with tempfile.NamedTemporaryFile(delete=False, suffix=".npz") as f:
            # Save the NumPy arrays instead of the full model
            # This is much more efficient for storage and loading
            np.savez(
                f.name,
                user_embeddings=user_embeddings,
                movie_embeddings=movie_embeddings,
                user_biases=user_biases,
                movie_biases=movie_biases,
                user_to_idx=np.array(list(user_to_idx.items())),
                movie_to_idx=np.array(list(movie_to_idx.items())),
            )
            
            model_file_path = f.name
        
        # Save mappings for recommendation serving
        model_artifacts = {
            "user_to_idx": user_to_idx,
            "movie_to_idx": movie_to_idx,
            "idx_to_user": idx_to_user,
            "idx_to_movie": idx_to_movie,
        }
        
        # Create the model info object
        model_info = ModelInfo(
            name=job.model_name,
            type=job.model_type,
            description=job.description or "Collaborative filtering matrix factorization model",
            training_job_id=job.job_id,
            dataset_name=job.dataset_name,
            parameters={
                "n_factors": n_factors,
                "n_epochs": n_epochs,
                "learning_rate": learning_rate,
                "regularization": regularization,
                "batch_size": batch_size
            },
            metrics={
                "final_loss": float(history.history["loss"][-1]),
                "final_mae": float(history.history["mae"][-1]),
                "num_users": len(user_ids),
                "num_items": len(movie_ids),
                "num_ratings": len(ratings)
            },
            active=False  # Not active initially
        )
        
        # Store the model in MongoDB
        model_doc = model_info.dict()
        
        # Store the model artifacts as JSON
        model_doc["artifacts"] = {
            "mappings": {
                "user_to_idx": {str(k): int(v) for k, v in user_to_idx.items()},
                "movie_to_idx": {str(k): int(v) for k, v in movie_to_idx.items()},
                "idx_to_user": {str(k): int(v) for k, v in idx_to_user.items()},
                "idx_to_movie": {str(k): int(v) for k, v in idx_to_movie.items()},
            }
        }
        
        # Also store a small sample of the embeddings for diagnostic purposes
        sample_size = min(10, len(movie_embeddings))
        sample_indices = np.random.choice(len(movie_embeddings), sample_size, replace=False)
        
        model_doc["artifacts"]["embedding_samples"] = {
            "movie_embeddings": {
                str(idx_to_movie[idx]): movie_embeddings[idx].tolist()
                for idx in sample_indices
            }
        }
        
        # Insert into MongoDB
        await self.models_collection.insert_one(model_doc)
        
        # Store the full embeddings for all movies in the embeddings collection
        batch_size = 100  # Store in reasonable batches
        
        # Update status
        await self.update_job_status(job.job_id, {
            "progress": 90.0,
            "message": "Storing movie embeddings"
        })
        
        # Insert movie embeddings
        for i in range(0, len(movie_ids), batch_size):
            batch_indices = list(range(i, min(i + batch_size, len(movie_ids))))
            
            # Prepare documents for insertion
            embedding_docs = []
            
            for idx in batch_indices:
                movie_id = idx_to_movie[idx]
                embedding_vector = movie_embeddings[idx].tolist()
                
                embedding_docs.append({
                    "movieId": str(movie_id),
                    "model": f"collaborative_{model_info.model_id}",
                    "embedding": embedding_vector,
                    "bias": float(movie_biases[idx][0]),
                    "created_at": datetime.utcnow()
                })
            
            # Insert in batch
            for doc in embedding_docs:
                await self.embeddings_collection.update_one(
                    {"movieId": doc["movieId"], "model": doc["model"]},
                    {"$set": doc},
                    upsert=True
                )
            
            # Allow other tasks to run
            await asyncio.sleep(0)
        
        # Cleanup temporary file
        os.unlink(model_file_path)
        
        # If no active model of this type exists, make this one active
        active_model = await self.get_active_model(model_info.type)
        if not active_model:
            await self.activate_model(model_info.model_id)
            
        # Return the model ID
        return model_info.model_id
    
    async def _train_hybrid_model(self, job: TrainingJob) -> str:
        """
        Train a hybrid recommendation model combining content-based and collaborative filtering.
        This is a lightweight implementation suitable for Cloud Run free tier.
        
        Returns the model_id of the created model.
        """
        logger.info(f"Training hybrid model: {job.model_name}")
        
        # Update status
        await self.update_job_status(job.job_id, {
            "progress": 10.0,
            "message": "Finding underlying models"
        })
        
        # Get active models of each type
        content_model = await self.get_active_model("content_based")
        collaborative_model = await self.get_active_model("collaborative_filtering")
        
        # Ensure both model types exist
        if not content_model:
            raise ValueError("No active content-based model found. Please train one first.")
            
        if not collaborative_model:
            raise ValueError("No active collaborative filtering model found. Please train one first.")
            
        # Get parameters
        content_weight = job.parameters.get("content_weight", 0.5)
        collaborative_weight = job.parameters.get("collaborative_weight", 0.5)
        n_recommendations = job.parameters.get("n_recommendations", 10)
        
        # Create the hybrid model info
        model_info = ModelInfo(
            name=job.model_name,
            type=job.model_type,
            description=job.description or "Hybrid recommendation model combining content-based and collaborative filtering",
            training_job_id=job.job_id,
            dataset_name=job.dataset_name,
            parameters={
                "content_model_id": content_model.model_id,
                "collaborative_model_id": collaborative_model.model_id,
                "content_weight": content_weight,
                "collaborative_weight": collaborative_weight,
                "n_recommendations": n_recommendations
            },
            metrics={
                "num_models_combined": 2
            },
            active=False  # Not active initially
        )
        
        # Update status
        await self.update_job_status(job.job_id, {
            "progress": 90.0,
            "message": "Storing hybrid model"
        })
        
        # Store the model in MongoDB
        await self.models_collection.insert_one(model_info.dict())
        
        # If no active model of this type exists, make this one active
        active_model = await self.get_active_model(model_info.type)
        if not active_model:
            await self.activate_model(model_info.model_id)
            
        # Return the model ID
        return model_info.model_id 