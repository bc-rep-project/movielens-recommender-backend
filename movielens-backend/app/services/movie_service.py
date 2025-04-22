# backend/app/services/movie_service.py

import logging
from typing import List, Optional, Dict, Any

from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.errors import PyMongoError
from bson import ObjectId # Import ObjectId for query validation

# Assume models are defined like this:
from app.models.movie import MovieReadSummary, MovieReadDetail, PaginatedMovieResponse, PaginationData

logger = logging.getLogger(__name__)

class MovieNotFoundError(Exception):
    """Custom exception when a movie is not found."""
    pass

class MovieService:
    def __init__(self, db: AsyncIOMotorDatabase):
        """
        Initializes the Movie Service.

        Args:
            db: An instance of AsyncIOMotorDatabase (Motor client).
        """
        self.db = db
        self.collection = db["movies"] # Use the 'movies' collection

    async def _build_movie_query(self, search: Optional[str], genre: Optional[str]) -> Dict[str, Any]:
        """Helper to build the MongoDB query filter."""
        query: Dict[str, Any] = {}
        if search:
            # Case-insensitive search on the title field
            query["title"] = {"$regex": search, "$options": "i"}
        if genre:
            # Case-insensitive match within the genres array
            query["genres"] = {"$regex": f"^{genre}$", "$options": "i"} # Exact match in array, case-insensitive
            # Alternative: partial match: query["genres"] = {"$regex": genre, "$options": "i"}
        return query

    async def get_movies(
        self,
        search: Optional[str] = None,
        genre: Optional[str] = None,
        page: int = 1,
        limit: int = 20
    ) -> PaginatedMovieResponse:
        """
        Retrieves a paginated list of movies, optionally filtered.

        Args:
            search: Optional search term for movie titles.
            genre: Optional genre to filter by.
            page: Page number (1-based).
            limit: Number of items per page.

        Returns:
            A PaginatedMovieResponse object.

        Raises:
            PyMongoError: If a database error occurs.
        """
        query = await self._build_movie_query(search, genre)
        skip = (page - 1) * limit

        try:
            total_items_cursor = self.collection.count_documents(query)
            movies_cursor = self.collection.find(query).skip(skip).limit(limit)

            # Execute queries concurrently
            total_items = await total_items_cursor
            movies_list_raw = await movies_cursor.to_list(length=limit)

            # Convert MongoDB docs to Pydantic models, mapping _id to id
            movie_summaries = [
                MovieReadSummary(id=str(doc["_id"]), **doc) for doc in movies_list_raw
            ]

            total_pages = (total_items + limit - 1) // limit
            pagination = PaginationData(
                total_items=total_items,
                total_pages=total_pages,
                current_page=page,
                page_size=limit
            )

            logger.info(f"Fetched {len(movie_summaries)} movies (page {page}/{total_pages}, total {total_items}) with query: {query}")
            return PaginatedMovieResponse(pagination=pagination, items=movie_summaries)

        except PyMongoError as e:
            logger.error(f"Database error while fetching movies: {e}", exc_info=True)
            raise # Re-raise the exception for the endpoint handler

    async def get_movie_by_id(self, movie_id: str) -> MovieReadDetail:
        """
        Retrieves detailed information for a single movie by its internal DB ID.

        Args:
            movie_id: The MongoDB ObjectId string of the movie.

        Returns:
            A MovieReadDetail object.

        Raises:
            MovieNotFoundError: If the movie with the given ID is not found or ID is invalid.
            PyMongoError: If a database error occurs.
        """
        if not ObjectId.is_valid(movie_id):
            logger.warning(f"Attempted to fetch movie with invalid ID format: {movie_id}")
            raise MovieNotFoundError(f"Invalid movie ID format: {movie_id}")

        try:
            movie_doc = await self.collection.find_one({"_id": ObjectId(movie_id)})

            if movie_doc:
                logger.debug(f"Found movie with ID: {movie_id}")
                # Map _id to id for the Pydantic model
                return MovieReadDetail(id=str(movie_doc["_id"]), **movie_doc)
            else:
                logger.warning(f"Movie with ID {movie_id} not found in database.")
                raise MovieNotFoundError(f"Movie with ID '{movie_id}' not found.")

        except PyMongoError as e:
            logger.error(f"Database error while fetching movie {movie_id}: {e}", exc_info=True)
            raise

    async def get_movies_by_ids(self, movie_ids: List[str]) -> List[MovieReadSummary]:
        """
        Retrieves movie summaries for a list of movie IDs.
        Used primarily to populate recommendation responses.

        Args:
            movie_ids: A list of MongoDB ObjectId strings.

        Returns:
            A list of MovieReadSummary objects. Returns empty list if input is empty
            or no movies are found. Invalid IDs in the list are ignored.
        """
        if not movie_ids:
            return []

        # Validate ObjectIds and filter out invalid ones
        valid_object_ids = []
        for mid in movie_ids:
            if ObjectId.is_valid(mid):
                valid_object_ids.append(ObjectId(mid))
            else:
                logger.warning(f"Invalid movie ID format encountered in list: {mid}")

        if not valid_object_ids:
            return []

        try:
            cursor = self.collection.find({"_id": {"$in": valid_object_ids}})
            movies_list_raw = await cursor.to_list(length=len(valid_object_ids))

            # Convert to Pydantic models
            movie_summaries = [
                MovieReadSummary(id=str(doc["_id"]), **doc) for doc in movies_list_raw
            ]
            logger.debug(f"Fetched {len(movie_summaries)} movies for {len(movie_ids)} requested IDs.")
            return movie_summaries

        except PyMongoError as e:
            logger.error(f"Database error while fetching movies by IDs: {e}", exc_info=True)
            raise # Re-raise for endpoint handler

    async def get_movie_title(self, movie_id: str) -> Optional[str]:
         """Helper to quickly get just the title for a movie ID."""
         if not ObjectId.is_valid(movie_id):
             return None
         try:
             movie_doc = await self.collection.find_one(
                 {"_id": ObjectId(movie_id)},
                 {"title": 1} # Project only title
             )
             return movie_doc.get("title") if movie_doc else None
         except PyMongoError:
             # Log error but might return None to avoid breaking interaction list retrieval
             logger.error(f"Database error fetching title for movie {movie_id}", exc_info=True)
             return None