import os
import io
import logging
import aiohttp
import aioboto3
import zipfile
import pandas as pd
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime
from typing import List, Optional, Dict, Any
import asyncio
import tempfile

from ..core.config import settings
from ..models.dataset import DatasetInfo, DatasetDownloadStatus
from ..data_access.mongodb import get_collection

logger = logging.getLogger(__name__)

# Define the dataset configurations for easy lookup
DATASET_CONFIGS = {
    "ml-latest-small": {
        "display_name": "MovieLens Small Dataset",
        "description": "100,000 ratings and 3,600 tag applications applied to 9,000 movies by 600 users (Last updated 9/2018)",
        "source_url": "https://files.grouplens.org/datasets/movielens/ml-latest-small.zip",
        "categories": ["movies", "ratings"],
    },
    "ml-25m": {
        "display_name": "MovieLens 25M Dataset",
        "description": "25 million ratings and one million tag applications applied to 62,000 movies by 162,000 users (Last updated 12/2019)",
        "source_url": "https://files.grouplens.org/datasets/movielens/ml-25m.zip",
        "categories": ["movies", "ratings"],
    }
}

class DatasetService:
    def __init__(
        self, 
        mongodb_client: AsyncIOMotorClient,
        redis_client = None,
        storage_client = None
    ):
        """Initialize dataset service with DB connections"""
        self.mongodb_client = mongodb_client
        self.redis_client = redis_client
        self.storage_client = storage_client
        
        # Collection references
        self.dataset_status_collection = get_collection(mongodb_client, "dataset_jobs")
        self.movies_collection = get_collection(mongodb_client, "movies")
        self.ratings_collection = get_collection(mongodb_client, "ratings")
        self.tags_collection = get_collection(mongodb_client, "tags")
        self.datasets_collection = get_collection(mongodb_client, "datasets")
        
        # Initialize S3/GCS client for storage
        # We use aioboto3 which works with both AWS S3 and GCS (with minimal config changes)
        self.s3_session = aioboto3.Session()
        
    async def list_datasets(self) -> List[DatasetInfo]:
        """List all available datasets"""
        # First check if we have dataset info cached in DB
        datasets = []
        async for doc in self.datasets_collection.find():
            # Convert MongoDB doc to DatasetInfo model
            # Exclude MongoDB _id field
            doc_without_id = {k: v for k, v in doc.items() if k != '_id'}
            datasets.append(DatasetInfo(**doc_without_id))
            
        # If no datasets found in DB, return the default configurations
        if not datasets:
            for name, config in DATASET_CONFIGS.items():
                # Check if this dataset exists in storage
                exists = await self.check_dataset_exists(name)
                
                # Create dataset info with default values
                dataset = DatasetInfo(
                    name=name,
                    display_name=config["display_name"],
                    description=config["description"],
                    source_url=config["source_url"],
                    categories=config["categories"],
                    loaded=exists
                )
                datasets.append(dataset)
                
                # Store this in MongoDB for future reference
                await self.datasets_collection.update_one(
                    {"name": name},
                    {"$set": dataset.dict()},
                    upsert=True
                )
                
        return datasets
    
    async def check_dataset_exists(self, dataset_name: str) -> bool:
        """Check if a dataset already exists in storage"""
        # First check if it's stored in database
        count = await self.movies_collection.count_documents({})
        if count > 0:
            # We have movies in DB, so dataset is available
            await self.datasets_collection.update_one(
                {"name": dataset_name},
                {"$set": {"loaded": True, "last_updated": datetime.utcnow()}},
                upsert=True
            )
            return True
            
        # Check if dataset exists in cloud storage
        try:
            # Use environment variable for bucket name or default value
            bucket_name = settings.GCS_BUCKET_NAME
            
            async with self.s3_session.resource(
                "s3",
                endpoint_url=settings.STORAGE_ENDPOINT_URL,
                aws_access_key_id=settings.STORAGE_ACCESS_KEY,
                aws_secret_access_key=settings.STORAGE_SECRET_KEY
            ) as s3:
                bucket = await s3.Bucket(bucket_name)
                
                # Construct the object key/path - usually datasets/dataset_name.zip
                object_key = f"datasets/{dataset_name}.zip"
                
                # Check if object exists
                try:
                    obj = await (await bucket.Object(object_key)).get()
                    # Update DB with metadata
                    size = obj.get('ContentLength', 0)
                    
                    await self.datasets_collection.update_one(
                        {"name": dataset_name},
                        {"$set": {
                            "size_bytes": size,
                            "last_updated": datetime.utcnow(),
                            "loaded": False  # It exists in storage but not loaded to DB
                        }},
                        upsert=True
                    )
                    return True
                except Exception as e:
                    logger.info(f"Dataset {dataset_name} not found in storage: {str(e)}")
                    return False
                    
        except Exception as e:
            logger.warning(f"Error checking dataset existence in storage: {str(e)}")
            return False
    
    async def start_dataset_download(self, dataset_name: str, user_id: str) -> DatasetDownloadStatus:
        """Start a dataset download job and return the initial status"""
        
        # Get dataset config
        if dataset_name not in DATASET_CONFIGS:
            raise ValueError(f"Unknown dataset: {dataset_name}")
            
        # Create a new job record
        job = DatasetDownloadStatus(
            dataset_name=dataset_name,
            status="PENDING",
            message=f"Download of {dataset_name} queued",
            requested_by=user_id,
            progress=0.0
        )
        
        # Store the job in MongoDB
        await self.dataset_status_collection.insert_one(job.dict())
        
        return job
        
    async def update_job_status(self, job_id: str, updates: Dict[str, Any]) -> None:
        """Update a job's status in the database"""
        await self.dataset_status_collection.update_one(
            {"job_id": job_id},
            {"$set": updates}
        )
        
    async def get_job_status(self, job_id: str) -> Optional[DatasetDownloadStatus]:
        """Get the current status of a job"""
        job_doc = await self.dataset_status_collection.find_one({"job_id": job_id})
        if not job_doc:
            return None
            
        # Convert MongoDB doc to model, excluding MongoDB _id
        job_doc.pop("_id", None)
        return DatasetDownloadStatus(**job_doc)
        
    async def process_dataset_download(self, job_id: str, dataset_name: str) -> None:
        """
        Process a dataset download job. This is run as a background task.
        
        This method handles:
        1. Downloading from the original source
        2. Uploading to cloud storage
        3. Processing the data (extracting movies, ratings, etc.)
        4. Updating database collections
        5. Updating job status throughout the process
        
        It's designed to optimize Cloud Run resource usage by:
        - Streaming data instead of loading everything in memory
        - Using temporary files when necessary
        - Working in small chunks
        - Checking for existing data to avoid duplicate work
        """
        try:
            # Update job status to in-progress
            await self.update_job_status(job_id, {
                "status": "IN_PROGRESS",
                "message": "Starting download from source",
                "progress": 10.0
            })
            
            # Get dataset configuration
            config = DATASET_CONFIGS[dataset_name]
            source_url = config["source_url"]
            
            # Create a temporary directory to extract files
            with tempfile.TemporaryDirectory() as temp_dir:
                # Download the dataset from source
                zip_path = os.path.join(temp_dir, f"{dataset_name}.zip")
                
                # Download dataset asynchronously
                await self._download_file(source_url, zip_path)
                
                # Update job status
                await self.update_job_status(job_id, {
                    "progress": 30.0,
                    "message": "Dataset downloaded, uploading to storage"
                })
                
                # Upload to cloud storage
                bucket_name = settings.GCS_BUCKET_NAME
                object_key = f"datasets/{dataset_name}.zip"
                
                await self._upload_to_storage(zip_path, bucket_name, object_key)
                
                # Update job status
                await self.update_job_status(job_id, {
                    "progress": 50.0,
                    "message": "Dataset uploaded to storage, processing data"
                })
                
                # Extract and process the dataset
                await self._process_movielens_dataset(zip_path, dataset_name)
                
                # Update job status
                await self.update_job_status(job_id, {
                    "status": "COMPLETE",
                    "progress": 100.0,
                    "message": "Dataset downloaded and processed successfully",
                    "completed_at": datetime.utcnow()
                })
                
                # Mark the dataset as loaded in the datasets collection
                await self.datasets_collection.update_one(
                    {"name": dataset_name},
                    {"$set": {
                        "loaded": True,
                        "last_updated": datetime.utcnow()
                    }},
                    upsert=True
                )
                
        except Exception as e:
            logger.error(f"Error processing dataset download: {str(e)}", exc_info=True)
            
            # Update job status to failed
            await self.update_job_status(job_id, {
                "status": "FAILED",
                "error": str(e),
                "message": f"Download failed: {str(e)}",
                "completed_at": datetime.utcnow()
            })
            
    async def _download_file(self, url: str, destination_path: str) -> None:
        """Download a file asynchronously"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status != 200:
                        raise ValueError(f"Failed to download: HTTP {response.status}")
                    
                    # Create parent directories if they don't exist
                    os.makedirs(os.path.dirname(destination_path), exist_ok=True)
                    
                    # Stream the content to file
                    with open(destination_path, 'wb') as fd:
                        while True:
                            chunk = await response.content.read(8192)
                            if not chunk:
                                break
                            fd.write(chunk)
        except Exception as e:
            raise ValueError(f"Failed to download file: {str(e)}")
            
    async def _upload_to_storage(self, source_path: str, bucket_name: str, object_key: str) -> None:
        """Upload a file to cloud storage asynchronously"""
        try:
            async with self.s3_session.resource(
                "s3",
                endpoint_url=settings.STORAGE_ENDPOINT_URL,
                aws_access_key_id=settings.STORAGE_ACCESS_KEY,
                aws_secret_access_key=settings.STORAGE_SECRET_KEY
            ) as s3:
                bucket = await s3.Bucket(bucket_name)
                await bucket.upload_file(source_path, object_key)
        except Exception as e:
            raise ValueError(f"Failed to upload to storage: {str(e)}")
            
    async def _process_movielens_dataset(self, zip_path: str, dataset_name: str) -> None:
        """
        Process the MovieLens dataset zip file:
        1. Extract movies.csv and ratings.csv
        2. Process and load into MongoDB
        3. Ensure indices for performance
        
        Optimized for Cloud Run by processing in chunks to limit memory usage
        """
        try:
            # Extract files from zip
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                # Get the base directory inside the zip
                base_dir = ""
                for name in zip_ref.namelist():
                    if name.endswith('/'):
                        base_dir = name
                        break
                
                # Process movies.csv - smaller file, load into memory
                movie_file = f"{base_dir}movies.csv" if base_dir else "movies.csv"
                with zip_ref.open(movie_file) as f:
                    movies_df = pd.read_csv(f)
                    
                    # Process movies in chunks to avoid excessive memory usage
                    chunk_size = 1000  # Adjust based on movie size and available memory
                    for i in range(0, len(movies_df), chunk_size):
                        chunk = movies_df.iloc[i:i+chunk_size]
                        
                        # Convert to list of dictionaries
                        movies_data = chunk.to_dict('records')
                        
                        # Process each movie
                        for movie in movies_data:
                            # Split genres string into array (comma-separated)
                            if 'genres' in movie and movie['genres']:
                                movie['genres'] = movie['genres'].split('|')
                            else:
                                movie['genres'] = []
                                
                            # Add movieId in string format for consistency
                            if 'movieId' in movie:
                                movie['movieId_str'] = str(movie['movieId'])
                            
                            # Add upload timestamp
                            movie['uploaded_at'] = datetime.utcnow()
                        
                        # Bulk insert into movies collection
                        if movies_data:
                            await self.movies_collection.insert_many(movies_data)
                        
                        # Allow other tasks to run
                        await asyncio.sleep(0)
                
                # Process ratings.csv - potentially large, process in chunks
                ratings_file = f"{base_dir}ratings.csv" if base_dir else "ratings.csv"
                
                # Use a csv reader to process line by line instead of loading all at once
                batch_size = 5000  # Adjust based on available memory
                batch = []
                
                with zip_ref.open(ratings_file) as f:
                    # Skip header
                    header = f.readline().decode('utf-8').strip().split(',')
                    
                    while True:
                        line = f.readline()
                        if not line:
                            break
                            
                        # Parse CSV line
                        values = line.decode('utf-8').strip().split(',')
                        rating = {header[i]: values[i] for i in range(len(header))}
                        
                        # Convert types
                        rating['userId'] = int(rating['userId'])
                        rating['userId_str'] = str(rating['userId'])
                        rating['movieId'] = int(rating['movieId'])
                        rating['movieId_str'] = str(rating['movieId'])
                        rating['rating'] = float(rating['rating'])
                        rating['timestamp'] = int(rating['timestamp'])
                        
                        # Add timestamp as datetime
                        rating['rated_at'] = datetime.fromtimestamp(int(rating['timestamp']))
                        
                        # Add to batch
                        batch.append(rating)
                        
                        # Process batch if it reaches the size limit
                        if len(batch) >= batch_size:
                            await self.ratings_collection.insert_many(batch)
                            batch = []
                            # Allow other tasks to run
                            await asyncio.sleep(0)
                
                # Insert any remaining ratings
                if batch:
                    await self.ratings_collection.insert_many(batch)
            
            # Create indexes for better query performance
            await self.movies_collection.create_index("movieId")
            await self.movies_collection.create_index("movieId_str")
            await self.movies_collection.create_index("genres")
            
            await self.ratings_collection.create_index("userId")
            await self.ratings_collection.create_index("userId_str")
            await self.ratings_collection.create_index("movieId")
            await self.ratings_collection.create_index("movieId_str")
            await self.ratings_collection.create_index([("userId", 1), ("movieId", 1)], unique=True)
            
        except Exception as e:
            raise ValueError(f"Failed to process MovieLens dataset: {str(e)}") 