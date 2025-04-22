# backend/app/utils/helpers.py

import logging
import math
import re
from datetime import datetime, timezone
from typing import Optional, Any, Dict

logger = logging.getLogger(__name__)

# --- Text Processing ---

def normalize_text(text: Optional[str]) -> Optional[str]:
    """
    Normalizes a string by converting to lowercase and stripping whitespace.
    Returns None if the input is None.

    Args:
        text: The input string or None.

    Returns:
        The normalized string or None.
    """
    if text is None:
        return None
    return text.lower().strip()

def extract_year_from_title(title: Optional[str]) -> Optional[int]:
    """
    Attempts to extract a 4-digit year enclosed in parentheses from the end of a string.

    Args:
        title: The string potentially containing a year (e.g., "Movie Title (1995)").

    Returns:
        The extracted year as an integer, or None if not found or invalid.
    """
    if not title:
        return None

    # Regex to find "(YYYY)" at the very end of the string
    match = re.search(r'\((\d{4})\)$', title.strip())
    if match:
        year_str = match.group(1)
        try:
            year_int = int(year_str)
            # Optional: Add a sanity check for realistic movie years
            current_year = datetime.now(timezone.utc).year
            if 1880 <= year_int <= current_year + 5: # Allow a bit into the future
                return year_int
            else:
                logger.debug(f"Extracted year {year_int} from '{title}' is outside expected range.")
                return None
        except ValueError:
            logger.warning(f"Could not convert extracted year '{year_str}' to int from title '{title}'.")
            return None
    return None

# --- Pagination Helpers ---

def calculate_skip(page: int, limit: int) -> int:
    """
    Calculates the number of documents to skip for pagination.

    Args:
        page: The current page number (1-based).
        limit: The number of items per page.

    Returns:
        The number of documents to skip.

    Raises:
        ValueError: If page or limit are not positive integers.
    """
    if not isinstance(page, int) or page < 1:
        raise ValueError("Page number must be a positive integer.")
    if not isinstance(limit, int) or limit < 1:
        raise ValueError("Page limit must be a positive integer.")
    return (page - 1) * limit

def calculate_total_pages(total_items: int, limit: int) -> int:
    """
    Calculates the total number of pages required.

    Args:
        total_items: The total number of items.
        limit: The number of items per page.

    Returns:
        The total number of pages.

    Raises:
        ValueError: If limit is not a positive integer.
    """
    if not isinstance(limit, int) or limit < 1:
        raise ValueError("Page limit must be a positive integer.")
    if total_items < 0:
         raise ValueError("Total items cannot be negative.")
    if total_items == 0:
        return 1 # Or 0 depending on desired behavior for empty results

    return math.ceil(total_items / limit)


# --- Data Structure Helpers (Example) ---

def safe_get(data: Optional[Dict[str, Any]], key: str, default: Any = None) -> Any:
    """
    Safely retrieves a value from a dictionary, returning a default if the
    dictionary is None or the key is missing.

    Args:
        data: The dictionary (or None).
        key: The key to retrieve.
        default: The value to return if retrieval fails.

    Returns:
        The value associated with the key, or the default value.
    """
    if data is None:
        return default
    return data.get(key, default)


# --- Example Usage (Illustrative) ---
if __name__ == "__main__":
    # Test year extraction
    print(f"'Movie (1995)': {extract_year_from_title('Movie (1995)')}") # Output: 1995
    print(f"'Movie (199)': {extract_year_from_title('Movie (199)')}")   # Output: None
    print(f"'Movie (ABCD)': {extract_year_from_title('Movie (ABCD)')}") # Output: None
    print(f"'Movie 1995': {extract_year_from_title('Movie 1995')}")     # Output: None
    print(f"'Movie (2025) ': {extract_year_from_title('Movie (2025) ')}") # Output: 2025
    print(f"None title: {extract_year_from_title(None)}")             # Output: None

    # Test normalization
    print(f"Normalize '  Search Term ': {normalize_text('  Search Term ')}") # Output: 'search term'
    print(f"Normalize None: {normalize_text(None)}")                     # Output: None

    # Test pagination
    print(f"Skip for page 3, limit 10: {calculate_skip(3, 10)}")       # Output: 20
    print(f"Total pages for 100 items, limit 10: {calculate_total_pages(100, 10)}") # Output: 10
    print(f"Total pages for 101 items, limit 10: {calculate_total_pages(101, 10)}") # Output: 11
    print(f"Total pages for 0 items, limit 10: {calculate_total_pages(0, 10)}")     # Output: 1

    # Test safe_get
    my_dict = {"a": 1, "b": None}
    print(f"safe_get(my_dict, 'a'): {safe_get(my_dict, 'a')}")         # Output: 1
    print(f"safe_get(my_dict, 'b', 99): {safe_get(my_dict, 'b', 99)}") # Output: None
    print(f"safe_get(my_dict, 'c', 99): {safe_get(my_dict, 'c', 99)}") # Output: 99
    print(f"safe_get(None, 'a', 99): {safe_get(None, 'a', 99)}")       # Output: 99