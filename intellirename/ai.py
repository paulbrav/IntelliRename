"""
AI-powered metadata enhancement for book and paper files.

This module provides functions to extract, clean, and enhance metadata for books and papers
using the Perplexity API, which provides both web search and AI capabilities.
"""

import asyncio
import json
import logging
import re
from datetime import datetime
from typing import Dict, Optional, Tuple

import aiohttp

# Import cache utilities
try:
    from intellirename.utils.cache import get_cache_key, get_from_cache, save_to_cache

    CACHE_AVAILABLE = True
except ImportError:
    CACHE_AVAILABLE = False

# Import configuration
from intellirename.config import (
    DEFAULT_CONFIDENCE_THRESHOLD,
    MAX_RETRIES,
    MAX_TOKENS,
    PERPLEXITY_API_KEY,
    TEMPERATURE,
    USE_CACHE,
)

# Import custom exceptions
from intellirename.exceptions import (
    AICommunicationError,
    AIProcessingError,
    ConfigurationError,
)

# Configure logging
log = logging.getLogger("intellirename.ai")

# Perform API key check here if desired, using the imported PERPLEXITY_API_KEY
if PERPLEXITY_API_KEY:
    if not PERPLEXITY_API_KEY.startswith("pplx-"):
        log.warning(
            "Perplexity API key loaded from config appears invalid (should start with 'pplx-')"
        )
    else:
        log.info(
            f"Perplexity API key loaded from config. First 5 chars: {PERPLEXITY_API_KEY[:5]}..."
        )
else:
    log.warning("No Perplexity API key found in configuration.")


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
        bool: True if the API key is valid.

    Raises:
        ConfigurationError: If the API key is missing or invalid.
    """
    if not PERPLEXITY_API_KEY:
        raise ConfigurationError("Perplexity API key (PERPLEXITY_API_KEY) is not set.")

    # Check format
    if not PERPLEXITY_API_KEY.startswith("pplx-"):
        raise ConfigurationError(
            "Invalid Perplexity API key format. Keys should start with 'pplx-'."
        )

    return True  # Return True if validation passes


async def query_perplexity_async(
    metadata: Dict[str, str], filename: str
) -> Dict[str, str]:
    """
    Query Perplexity API asynchronously to enhance and correct metadata.

    Args:
        metadata: The metadata to enhance.
        filename: Original filename.

    Returns:
        Enhanced metadata dictionary.

    Raises:
        ConfigurationError: If the API key is invalid (checked before call).
        AICommunicationError: If there are network issues or API errors (e.g., 4xx, 5xx).
        AIProcessingError: If the API response cannot be parsed or lacks expected data.
    """
    # API key validation should happen before calling this async function
    log.debug(f"Starting AI metadata enhancement query for file: {filename}")
    log.debug(f"Original metadata: {metadata}")

    # Check cache first if available (remains synchronous for now)
    if CACHE_AVAILABLE and USE_CACHE:
        cache_key = get_cache_key(metadata, filename)
        log.debug(f"Generated cache key: {cache_key}")
        cached_data = get_from_cache(cache_key)
        if cached_data:
            log.info(f"Using cached metadata enhancement results for {filename}")
            return cached_data

    prompt = construct_prompt(metadata, filename)
    log.debug(f"Generated Perplexity prompt: {prompt}")

    # API call with retry logic using aiohttp
    last_exception: Optional[Exception] = None
    api_url = "https://api.perplexity.ai/chat/completions"
    headers = {
        "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "sonar",  # Consider making model configurable
        "messages": [{"role": "user", "content": prompt}],
        "temperature": TEMPERATURE,
        "max_tokens": MAX_TOKENS,
    }
    # Consider making timeout configurable via config.py
    timeout = aiohttp.ClientTimeout(total=60)

    async with aiohttp.ClientSession(timeout=timeout) as session:
        for attempt in range(MAX_RETRIES):
            try:
                log.info(
                    f"Querying Perplexity API (attempt {attempt + 1}/{MAX_RETRIES}) for: {filename}"
                )
                async with session.post(
                    api_url, headers=headers, json=payload
                ) as response:
                    # Check for non-retryable errors first
                    if response.status == 401:
                        log.error(
                            "401 Unauthorized: Invalid Perplexity API key or insufficient credits."
                        )
                        raise AICommunicationError(
                            "Perplexity API key is invalid or lacks funds."
                        )
                    elif response.status == 429:  # Rate limited
                        log.warning(
                            "429 Rate Limited: Too many requests. Backing off..."
                        )
                        # Implement exponential backoff if needed, for now just retry after delay
                        await asyncio.sleep(2**attempt)  # Simple exponential backoff
                        continue  # Retry
                    elif response.status == 400:  # Bad request (e.g., bad prompt)
                        log.error(
                            f"400 Bad Request: Check prompt or payload. Response: {await response.text()}"
                        )
                        raise AIProcessingError(
                            "Perplexity API rejected the request (400)."
                        )

                    # Raise exceptions for other client/server errors (4xx, 5xx) that might be retryable
                    response.raise_for_status()  # Raises ClientResponseError for non-2xx status

                    # Process successful response
                    raw_response_text = await response.text()
                    log.debug(f"Raw Perplexity response: {raw_response_text}")

                    try:
                        data = await response.json()  # Use built-in json decoder
                    except aiohttp.ContentTypeError:
                        log.error(
                            f"Failed to decode JSON response: {raw_response_text}"
                        )
                        raise AIProcessingError(
                            "Failed to decode JSON response from Perplexity."
                        )
                    except json.JSONDecodeError:
                        log.error(f"Invalid JSON received: {raw_response_text}")
                        raise AIProcessingError(
                            "Invalid JSON received from Perplexity."
                        )

                    # Extract content
                    try:
                        content = data["choices"][0]["message"]["content"]
                        log.debug(f"Extracted content: {content}")
                    except (KeyError, IndexError, TypeError) as e:
                        log.error(
                            f"Could not find expected content in Perplexity response: {data}. Error: {e}"
                        )
                        raise AIProcessingError(
                            "Perplexity response format unexpected."
                        )

                    # Extract JSON part from the response
                    try:
                        # Attempt to find JSON block assuming it's well-formed within the content
                        json_match = re.search(
                            r"```json\s*(\{.*?\})\s*```", content, re.DOTALL
                        )
                        if not json_match:
                            # Fallback: try finding a dict-like structure directly
                            json_match = re.search(r"(\{.*?\})", content, re.DOTALL)

                        if json_match:
                            json_str = json_match.group(1)
                            ai_metadata = json.loads(json_str)
                            log.info(
                                f"Successfully parsed metadata from AI for {filename}"
                            )
                            log.debug(f"Parsed AI metadata: {ai_metadata}")

                            # Ensure all required keys are present for type safety
                            for key in ["author", "title", "year"]:
                                if key not in ai_metadata or not ai_metadata[key]:
                                    ai_metadata[key] = "Unknown"

                            # Clean up extracted values (e.g., strip whitespace)
                            ai_metadata = {
                                k: str(v).strip() if v else "Unknown"
                                for k, v in ai_metadata.items()
                            }

                            # Guarantee type: Dict[str, str] for mypy/ruff compliance
                            result: Dict[str, str] = {
                                "author": ai_metadata.get("author", "Unknown"),
                                "title": ai_metadata.get("title", "Unknown"),
                                "year": ai_metadata.get("year", "Unknown"),
                            }

                            # Cache the successful result if enabled
                            if CACHE_AVAILABLE and USE_CACHE:
                                save_to_cache(cache_key, result)
                                log.debug(
                                    f"Saved AI result to cache for key: {cache_key}"
                                )

                            return result
                        else:
                            log.warning(
                                f"No JSON block found in Perplexity response for {filename}. Content: {content}"
                            )
                            raise AIProcessingError(
                                "No JSON block found in Perplexity response."
                            )

                    except json.JSONDecodeError as e:
                        log.error(
                            f"Failed to parse JSON from extracted content: {json_str}. Error: {e}"
                        )
                        raise AIProcessingError(
                            f"Failed to parse JSON from AI response: {e}"
                        )
                    except Exception as e:  # Catch unexpected errors during parsing
                        log.exception(
                            f"Unexpected error parsing AI response content: {e}"
                        )
                        raise AIProcessingError(
                            f"Unexpected error parsing AI response: {e}"
                        )

            except (
                aiohttp.ClientResponseError
            ) as e:  # Errors raised by raise_for_status()
                log.warning(
                    f"Perplexity API request failed (Status: {e.status}, Attempt: {attempt + 1}/{MAX_RETRIES}): {e.message}"
                )
                last_exception = AICommunicationError(
                    f"API request failed: {e.message} (Status: {e.status})"
                )
                if attempt == MAX_RETRIES - 1:
                    log.error(
                        f"Perplexity API query failed after {MAX_RETRIES} attempts for {filename}."
                    )
                    raise last_exception
                await asyncio.sleep(1 * (attempt + 1))  # Simple linear backoff

            except aiohttp.ClientConnectionError as e:  # Network errors
                log.warning(
                    f"Network error connecting to Perplexity (Attempt {attempt + 1}/{MAX_RETRIES}): {e}"
                )
                last_exception = AICommunicationError(
                    f"Network error connecting to Perplexity: {e}"
                )
                if attempt == MAX_RETRIES - 1:
                    log.error(
                        f"Perplexity API query failed after {MAX_RETRIES} attempts for {filename} due to network errors."
                    )
                    raise last_exception
                await asyncio.sleep(1 * (attempt + 1))

            except asyncio.TimeoutError:
                log.warning(
                    f"Perplexity API request timed out (Attempt {attempt + 1}/{MAX_RETRIES}) for {filename}"
                )
                last_exception = AICommunicationError(
                    "Perplexity API request timed out."
                )
                if attempt == MAX_RETRIES - 1:
                    log.error(
                        f"Perplexity API query failed after {MAX_RETRIES} attempts for {filename} due to timeouts."
                    )
                    raise last_exception
                # No need to sleep here, retry immediately or use backoff

            except AIProcessingError as e:  # Non-retryable processing errors
                log.error(f"AI processing error for {filename}: {e}")
                raise e  # Propagate immediately

            except (
                Exception
            ) as e:  # Catch any other unexpected errors during the request phase
                log.exception(
                    f"Unexpected error during Perplexity API call for {filename} (Attempt {attempt + 1}/{MAX_RETRIES}): {e}"
                )
                last_exception = AICommunicationError(
                    f"Unexpected error during API call: {e}"
                )
                if attempt == MAX_RETRIES - 1:
                    log.error(
                        f"Perplexity API query failed after {MAX_RETRIES} attempts for {filename} due to unexpected errors."
                    )
                    raise last_exception
                await asyncio.sleep(1 * (attempt + 1))

    # Should not be reachable if MAX_RETRIES > 0, but added for safety
    log.error(
        f"Perplexity API query ultimately failed for {filename} after exhausting retries."
    )
    raise (
        last_exception
        if last_exception
        else AICommunicationError("AI query failed after retries.")
    )


# Keep the synchronous wrapper for now if needed by other parts, or remove if fully async
def query_perplexity(metadata: Dict[str, str], filename: str) -> Dict[str, str]:
    """Synchronous wrapper for query_perplexity_async. Deprecated."""
    log.warning(
        "Using synchronous wrapper for query_perplexity. Consider updating caller."
    )
    # This will block. Need an event loop running elsewhere or create one temporarily.
    # This is generally bad practice to mix like this long-term.
    try:
        asyncio.get_running_loop()
        # If a loop is running (e.g., called from within another async func managed by asyncio.run),
        # we can't just run_until_complete. We need a better pattern or make the caller async.
        # For now, raise an error or use a more complex approach if this is a real use case.
        log.error(
            "Cannot run synchronous wrapper from within an existing event loop easily."
        )
        raise RuntimeError("Synchronous wrapper called from within async context.")
    except RuntimeError:  # No running event loop
        # Create a new event loop to run the async function - simple but potentially inefficient
        return asyncio.run(query_perplexity_async(metadata, filename))


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


async def enhance_metadata(
    metadata: Dict[str, str],
    filename: str,
    unknown_markers: Dict[str, str],
    confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
) -> Dict[str, str]:
    """
    Enhance metadata using AI if quality is below threshold. Now asynchronous.

    Args:
        metadata: The initial metadata dictionary.
        filename: The original filename.
        unknown_markers: Dictionary defining unknown value markers.
        confidence_threshold: The minimum confidence score to skip AI enhancement.

    Returns:
        The original or AI-enhanced metadata dictionary.

    Raises:
        ConfigurationError: If the Perplexity API key is invalid.
        AICommunicationError: If communication with the AI API fails.
        AIProcessingError: If the AI response processing fails.
    """
    log.info(f"Evaluating metadata quality for {filename}...")
    confidence, field_scores = evaluate_metadata_quality(metadata, unknown_markers)
    log.info(
        f"Metadata confidence score for {filename}: {confidence:.2f} (Threshold: {confidence_threshold})"
    )
    log.debug(f"Field scores: {field_scores}")

    if confidence >= confidence_threshold:
        log.info(
            f"Confidence score meets threshold. Skipping AI enhancement for {filename}."
        )
        return metadata
    else:
        log.info(
            f"Confidence score below threshold. Attempting AI enhancement for {filename}."
        )

        # Validate API key before making the call
        try:
            validate_perplexity_api_key()  # Check config before async call
        except ConfigurationError as e:
            log.error(f"Cannot enhance metadata: {e}")
            raise  # Propagate configuration errors

        # Call the asynchronous query function
        try:
            enhanced_metadata = await query_perplexity_async(
                metadata, filename
            )  # Await the async call
            log.info(f"Successfully enhanced metadata using AI for {filename}.")
            log.debug(f"Enhanced metadata: {enhanced_metadata}")
            return enhanced_metadata
        except (AICommunicationError, AIProcessingError) as e:
            # Log the error but return original metadata? Or re-raise?
            # Re-raising allows the caller (main loop) to decide how to handle failed AI enhancement
            log.error(f"AI enhancement failed for {filename}: {e}")
            raise  # Re-raise the specific AI error
        except Exception as e:
            log.exception(f"Unexpected error during AI enhancement for {filename}: {e}")
            # Re-raise as a generic AI error or let it propagate? Re-raise specific for now.
            raise AIProcessingError(
                f"Unexpected error during AI enhancement: {e}"
            ) from e
