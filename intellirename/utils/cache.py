"""
Cache mechanism for API results to reduce redundant API calls.

This module provides functions to store and retrieve API results from a simple
disk-based cache.
"""

import hashlib
import json
import logging
import os
from typing import Any, Dict, Optional, cast

# Configure logging
log = logging.getLogger("book_renamer.cache")

# Default cache directory
DEFAULT_CACHE_DIR = os.path.expanduser("~/.book_renamer/cache")


def get_cache_key(metadata: Dict[str, str], filename: str) -> str:
    """
    Generate a unique cache key based on metadata and filename.

    Args:
        metadata: The metadata dictionary
        filename: Original filename

    Returns:
        A unique hash string to use as cache key
    """
    # Create a string representation of relevant data
    cache_str = f"{filename}|"

    if metadata.get("author"):
        cache_str += f"author:{metadata['author']}|"

    if metadata.get("title"):
        cache_str += f"title:{metadata['title']}|"

    if metadata.get("year"):
        cache_str += f"year:{metadata['year']}"

    # Generate MD5 hash of the string
    return hashlib.md5(cache_str.encode()).hexdigest()


def get_from_cache(
    cache_key: str, cache_dir: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    Retrieve data from cache if it exists.

    Args:
        cache_key: The unique cache key
        cache_dir: Directory to store cache files (defaults to ~/.book_renamer/cache)

    Returns:
        Cached data or None if not found
    """
    cache_dir = cache_dir or DEFAULT_CACHE_DIR
    cache_file = os.path.join(cache_dir, f"{cache_key}.json")

    try:
        if os.path.exists(cache_file):
            with open(cache_file, "r", encoding="utf-8") as f:
                log.debug(f"Cache hit for key {cache_key}")
                return cast(Dict[str, Any], json.load(f))
    except FileNotFoundError:
        log.debug(f"Cache file not found: {cache_file}")
        return None
    except (json.JSONDecodeError, OSError) as e:
        log.exception(f"Error reading from cache file {cache_file}: {e}")
        return None
    except Exception as e:  # Catch unexpected errors during read
        log.exception(f"Unexpected error reading cache file {cache_file}: {e}")
        return None

    log.debug(f"Cache miss for key {cache_key}")
    return None


def save_to_cache(
    cache_key: str, data: Dict[str, Any], cache_dir: Optional[str] = None
) -> bool:
    """
    Save data to cache.

    Args:
        cache_key: The unique cache key
        data: The data to cache
        cache_dir: Directory to store cache files (defaults to ~/.book_renamer/cache)

    Returns:
        True if successful, False otherwise
    """
    cache_dir = cache_dir or DEFAULT_CACHE_DIR

    try:
        # Ensure cache directory exists
        os.makedirs(cache_dir, exist_ok=True)

        cache_file = os.path.join(cache_dir, f"{cache_key}.json")
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        log.debug(f"Saved data to cache for key {cache_key}")
        return True
    except (TypeError, OSError) as e:
        log.exception(f"Error saving to cache file {cache_file}: {e}")
        return False
    except Exception as e:  # Catch unexpected errors during write
        log.exception(f"Unexpected error saving cache file {cache_file}: {e}")
        return False
