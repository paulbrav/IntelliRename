"""
AI-powered metadata enhancement for book and paper files.

This module provides functions to extract, clean, and enhance metadata for books and papers
using the Perplexity API, which provides both web search and AI capabilities.
"""

import json
import logging
import os
import re
import time
from datetime import datetime
from typing import Dict, Tuple

import requests

# Import cache utilities
try:
    from intellirename.utils.cache import get_cache_key, get_from_cache, save_to_cache

    CACHE_AVAILABLE = True
except ImportError:
    CACHE_AVAILABLE = False

# Configure logging
log = logging.getLogger("book_renamer.ai_metadata")

# Load environment variables - search in multiple locations
# Try to find the .env file in various possible locations
env_locations = [
    os.path.join(os.getcwd(), ".env"),  # Current working directory
    os.path.join(os.getcwd(), "intellirename", ".env"),  # intellirename subdirectory
    os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env"
    ),  # Project root
    os.path.expanduser("~/.env"),  # User's home directory
]

# First check if the API key is already in environment variables
PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY")

# If not found in environment, try loading from .env files
if not PERPLEXITY_API_KEY:
    for env_path in env_locations:
        if os.path.isfile(env_path):
            log.info(f"Loading .env file from: {env_path}")
            PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY")
            if PERPLEXITY_API_KEY:
                break
    else:
        log.warning("No .env file found in any of the expected locations")

if PERPLEXITY_API_KEY:
    # Validate API key format - Perplexity API keys typically start with 'pplx-'
    if not PERPLEXITY_API_KEY.startswith("pplx-"):
        log.warning(
            "Perplexity API key appears to be in an invalid format. Keys should start with 'pplx-'"
        )
        log.info("Please check your API key at https://www.perplexity.ai/settings/api")
    else:
        log.info(
            f"Perplexity API key found. First 5 chars: {PERPLEXITY_API_KEY[:5]}..."
        )
else:
    log.warning("No Perplexity API key found in environment variables")

# Constants
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
DEFAULT_CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.7"))
TEMPERATURE = float(os.getenv("TEMPERATURE", "0.1"))
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "500"))
USE_CACHE = os.getenv("USE_CACHE", "true").lower() in ("true", "1", "yes")


def evaluate_metadata_quality(
    metadata: Dict[str, str], unknown_markers: Dict[str, str]
) -> Tuple[float, Dict[str, float]]:
    """
    Evaluate the quality of extracted metadata.

    Args:
        metadata: The metadata dictionary to evaluate
        unknown_markers: Dictionary of placeholder values indicating unknown data

    Returns:
        Tuple of (overall_confidence_score, field_confidence_scores)
    """
    field_scores = {}

    # Check author quality
    author = metadata.get("author", unknown_markers["author"])
    if author == unknown_markers["author"]:
        field_scores["author"] = 0.0
    elif "_" in author and (author.startswith("S_") or author.endswith("_al")):
        # Likely garbled (like "S_or_Dargo") or generic ("et_al")
        field_scores["author"] = 0.3
    elif re.search(r"[A-Z][a-z]+_[A-Z][a-z]+", author):
        # Properly formatted FirstName_LastName
        field_scores["author"] = 0.9
    else:
        field_scores["author"] = 0.6

    # Check title quality
    title = metadata.get("title", unknown_markers["title"])
    if title == unknown_markers["title"]:
        field_scores["title"] = 0.0
    elif len(title) < 3 or title.isupper() or title.islower():
        # Likely invalid or improperly formatted
        field_scores["title"] = 0.3
    else:
        field_scores["title"] = 0.8

    # Check year quality
    year = metadata.get("year", unknown_markers["year"])
    if year == unknown_markers["year"]:
        field_scores["year"] = 0.0
    elif year.isdigit() and len(year) == 4 and 1800 <= int(year) <= datetime.now().year:
        field_scores["year"] = 1.0
    else:
        field_scores["year"] = 0.4

    # Calculate overall score as weighted average
    overall_score = (
        field_scores.get("author", 0.0) * 0.4
        + field_scores.get("title", 0.0) * 0.4
        + field_scores.get("year", 0.0) * 0.2
    )

    return overall_score, field_scores


def construct_prompt(metadata: Dict[str, str], filename: str) -> str:
    """
    Construct an effective prompt for Perplexity API.

    Args:
        metadata: The extracted metadata
        filename: Original filename

    Returns:
        Prompt string
    """
    query = (
        "Find the correct bibliographic information for this book or academic paper. "
        "Here's what I know:\n\n"
    )

    # Add the original filename
    query += f"Original filename: {filename}\n"

    # Add extracted metadata, if available
    if metadata.get("author") and metadata["author"] != "Unknown_Author":
        query += f"Extracted author: {metadata['author'].replace('_', ' ')}\n"

    if metadata.get("title") and metadata["title"] != "Untitled":
        query += f"Extracted title: {metadata['title'].replace('_', ' ')}\n"

    if metadata.get("year") and metadata["year"] != "0000":
        query += f"Extracted year: {metadata['year']}\n"

    # Add specific instructions
    query += """
Based on this information and by searching online resources, provide:
1. The correct full author name(s) (format as 'LastName, FirstName' for each author)
2. The complete and accurate title
3. The publication year (4-digit year)

Format your response as a JSON object with keys: "author", "title", and "year".
For multiple authors, separate with '; '.
If you cannot find reliable information, use "Unknown" for that field.

Include at the end a brief explanation of what was fixed, but put this outside the JSON.
"""

    return query


def validate_perplexity_api_key() -> bool:
    """
    Validate the Perplexity API key format and availability.

    Returns:
        bool: True if the API key is valid, False otherwise
    """
    if not PERPLEXITY_API_KEY:
        log.error("No Perplexity API key found in environment variables")
        return False

    # Check format - Perplexity API keys should start with 'pplx-'
    if not PERPLEXITY_API_KEY.startswith("pplx-"):
        log.error("Invalid Perplexity API key format. Keys should start with 'pplx-'")
        return False

    # For further validation, we could make a minimal API call here to verify the key works
    # But for now a format check is sufficient
    return True


def query_perplexity(metadata: Dict[str, str], filename: str) -> Dict[str, str]:
    """
    Query Perplexity API to enhance and correct metadata.

    Args:
        metadata: The metadata to enhance
        filename: Original filename

    Returns:
        Enhanced metadata dictionary
    """
    # First validate API key
    if not validate_perplexity_api_key():
        log.warning("Invalid Perplexity API key. Skipping AI metadata enhancement.")
        return metadata

    log.debug(f"Starting AI metadata enhancement for file: {filename}")
    log.debug(f"Original metadata: {metadata}")

    # Check cache first if available
    if CACHE_AVAILABLE and USE_CACHE:
        cache_key = get_cache_key(metadata, filename)
        log.debug(f"Generated cache key: {cache_key}")
        cached_data = get_from_cache(cache_key)
        if cached_data:
            log.info(f"Using cached metadata enhancement results for {filename}")
            return cached_data

    prompt = construct_prompt(metadata, filename)
    log.debug(f"Generated Perplexity prompt: {prompt}")

    # API call with retry logic
    response_data = None
    for attempt in range(MAX_RETRIES):
        try:
            log.info(
                f"Querying Perplexity API for metadata enhancement (attempt {attempt + 1})"
            )

            # Prepare request payload
            payload = {
                "model": "sonar",  # Model with web search capability
                "messages": [{"role": "user", "content": prompt}],
                "temperature": TEMPERATURE,
                "max_tokens": MAX_TOKENS,
            }
            log.debug(f"API request payload: {json.dumps(payload)}")

            # Make API call
            response = requests.post(
                "https://api.perplexity.ai/chat/completions",
                headers={
                    "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=30,
            )

            # Log response status and headers
            log.debug(f"API response status: {response.status_code}")
            log.debug(f"API response headers: {response.headers}")

            if response.status_code == 401:
                # Handle authentication errors specifically
                log.error(
                    "401 Unauthorized: Invalid or expired API key, or insufficient credits"
                )
                log.error(
                    "Please check your Perplexity API key and account status at https://www.perplexity.ai/settings/api"
                )
                break  # Don't retry on auth errors

            response.raise_for_status()
            response_data = response.json()
            log.debug(f"API response data: {json.dumps(response_data)}")
            break
        except requests.exceptions.RequestException as e:
            log.warning(f"API call attempt {attempt + 1} failed: {str(e)}")
            # If we have a response, log it for debugging
            if "response" in locals() and hasattr(response, "text"):
                log.debug(f"Error response body: {response.text}")

            if response.status_code == 401:
                break  # Don't retry on auth errors

            if attempt < MAX_RETRIES - 1:
                time.sleep(2**attempt)  # Exponential backoff

    if not response_data:
        log.warning(
            "Failed to get response from Perplexity API after multiple attempts"
        )
        return metadata

    # Parse AI response
    try:
        ai_response = response_data["choices"][0]["message"]["content"]
        log.debug(f"Raw content from Perplexity: {ai_response}")

        # Extract JSON from the response
        json_match = re.search(r"({.*})", ai_response, re.DOTALL)
        if json_match:
            log.debug(f"Extracted JSON: {json_match.group(1)}")
            enhanced_data = json.loads(json_match.group(1))

            # Convert author format if needed
            author = enhanced_data.get("author")
            if author and author != "Unknown":
                # Replace semicolons with "_" for multiple authors
                author = author.replace("; ", "_")
                # Remove any commas that might be in LastName, FirstName format
                author = author.replace(", ", "_")
                # Replace spaces with underscores
                author = author.replace(" ", "_")

            # Clean up the title
            title = enhanced_data.get("title")
            if title and title != "Unknown":
                # Replace spaces with underscores
                title = title.replace(" ", "_")

            result = metadata.copy()

            # Update fields only if they were found
            if author and author != "Unknown":
                result["author"] = author
                log.debug(f"Updated author to: {author}")

            if title and title != "Unknown":
                result["title"] = title
                log.debug(f"Updated title to: {title}")

            if enhanced_data.get("year") and enhanced_data["year"] != "Unknown":
                result["year"] = enhanced_data["year"]
                log.debug(f"Updated year to: {enhanced_data['year']}")

            log.info(f"Enhanced metadata: {result}")

            # Cache the result if caching is available
            if CACHE_AVAILABLE and USE_CACHE:
                cache_key = get_cache_key(metadata, filename)
                save_to_cache(cache_key, result)
                log.debug(f"Saved result to cache with key: {cache_key}")

            return result
        else:
            log.warning("Could not extract JSON from Perplexity response")
            log.debug(f"Failed to extract JSON from: {ai_response}")
    except Exception as e:
        log.warning(f"Failed to parse AI response: {str(e)}")
        import traceback

        log.debug(f"Exception traceback: {traceback.format_exc()}")

    return metadata


def clean_garbled_metadata(metadata: Dict[str, str]) -> Dict[str, str]:
    """
    Clean common patterns of garbled metadata.

    Args:
        metadata: The metadata to clean

    Returns:
        Cleaned metadata dictionary
    """
    result = metadata.copy()

    # Fix common author name issues
    if result.get("author"):
        # Fix "S_or_Dargo" type garbling (missing characters)
        result["author"] = re.sub(r"([A-Z])_([a-z]{2})", r"\1and\2", result["author"])

        # Fix multiple underscores
        result["author"] = re.sub(r"_+", "_", result["author"])

    # Fix title issues
    if result.get("title"):
        # Remove common file artifacts like [PDF], (ebook), etc.
        result["title"] = re.sub(
            r"[\[\(](?:PDF|EPUB|ebook|Ebook)[\]\)]", "", result["title"]
        )

        # Fix multiple underscores
        result["title"] = re.sub(r"_+", "_", result["title"])

        # Remove trailing/leading underscores
        result["title"] = result["title"].strip("_")

    return result


def enhance_metadata(
    metadata: Dict[str, str],
    filename: str,
    unknown_markers: Dict[str, str],
    confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
) -> Dict[str, str]:
    """
    Enhance metadata using AI and web search if needed.

    Args:
        metadata: The metadata to enhance
        filename: Original filename
        unknown_markers: Dictionary of placeholder values indicating unknown data
        confidence_threshold: Threshold for using AI enhancement

    Returns:
        Enhanced metadata dictionary
    """
    # Evaluate current metadata quality
    confidence_score, field_scores = evaluate_metadata_quality(
        metadata, unknown_markers
    )

    # If confidence is high enough, just clean and return
    if confidence_score >= confidence_threshold:
        return clean_garbled_metadata(metadata)

    # Otherwise, use Perplexity to enhance
    log.info(
        f"Metadata quality score {confidence_score:.2f} below threshold {confidence_threshold}. Using AI enhancement."
    )
    enhanced_metadata = query_perplexity(metadata, filename)

    # Clean the enhanced metadata
    return clean_garbled_metadata(enhanced_metadata)
