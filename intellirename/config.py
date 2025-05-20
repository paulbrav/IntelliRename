"""Centralized configuration settings for IntelliRename."""

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, Type, TypeVar, cast

# Import custom exceptions
from intellirename.exceptions import ConfigurationError

log = logging.getLogger("book_renamer.config")

T = TypeVar("T")


def get_env_var(name: str, default: str, target_type: Type[T]) -> T:
    """Get environment variable, cast to type, handle errors."""
    value_str = os.getenv(name, default)
    try:
        if target_type is bool:
            # Handle boolean specifically (case-insensitive true/1/yes)
            return cast(T, value_str.lower() in ("true", "1", "yes"))
        elif target_type is Path:
            # Handle Path object creation
            return cast(T, Path(value_str))
        else:
            # Handle int, float
            return target_type(value_str)  # type: ignore
    except ValueError as e:
        log.exception(
            f"Invalid value for environment variable '{name}': {value_str}. "
            f"Could not cast to {target_type.__name__}. Error: {e}"
        )
        raise ConfigurationError(
            f"Invalid value for environment variable {name}: '{value_str}'. Expected {target_type.__name__}.",
            original_exception=e,
        ) from e
    except Exception as e:
        # Catch any other unexpected error during type conversion
        log.exception(f"Unexpected error processing env var {name} with value '{value_str}'")
        raise ConfigurationError(
            f"Unexpected error processing env var {name}: '{value_str}'",
            original_exception=e,
        ) from e


# --- General Settings ---
# Default confidence threshold for using AI enhancement
DEFAULT_CONFIDENCE_THRESHOLD: float = get_env_var("CONFIDENCE_THRESHOLD", "0.7", float)

# --- Perplexity AI Settings ---
# Load API key - search in multiple locations
PERPLEXITY_API_KEY: Optional[str] = os.getenv("PERPLEXITY_API_KEY")

# If not found in environment, try loading from .env files in standard locations
if not PERPLEXITY_API_KEY:
    env_locations = [
        Path.cwd() / ".env",  # Current working directory
        Path.cwd() / "intellirename" / ".env",  # intellirename subdirectory
        Path(__file__).parent.parent / ".env",  # Project root
        Path.home() / ".env",  # User's home directory
    ]
    # Attempt to load from dotenv if installed
    try:
        from dotenv import load_dotenv

        for env_path in env_locations:
            if env_path.is_file():
                log.debug(f"Loading environment variables from: {env_path}")
                load_dotenv(
                    dotenv_path=env_path, override=False
                )  # Don't override existing env vars
                # Re-check PERPLEXITY_API_KEY after loading
                _key = os.getenv("PERPLEXITY_API_KEY")
                if _key and not PERPLEXITY_API_KEY:
                    PERPLEXITY_API_KEY = _key
                    log.debug(f"Found PERPLEXITY_API_KEY in {env_path}")
                    break  # Stop searching once found
    except ImportError:
        log.debug("python-dotenv not installed, cannot load .env files.")
        pass  # dotenv not installed, proceed without it

MAX_RETRIES: int = get_env_var("MAX_RETRIES", "3", int)
TEMPERATURE: float = get_env_var("TEMPERATURE", "0.1", float)
MAX_TOKENS: int = get_env_var("MAX_TOKENS", "500", int)

# --- Caching Settings ---
USE_CACHE: bool = get_env_var("USE_CACHE", "true", bool)
# Use helper for Path conversion, providing a default string path
_default_cache_str = str(Path.home() / ".intellirename" / "cache")
DEFAULT_CACHE_DIR: Path = get_env_var("CACHE_DIR", _default_cache_str, Path)

# Default valid year range for metadata cleaning
DEFAULT_MIN_VALID_YEAR = 1500
DEFAULT_MAX_VALID_YEAR = datetime.now().year


def load_config() -> None:
    # ... existing code ...
    pass  # Add pass to fix IndentationError
