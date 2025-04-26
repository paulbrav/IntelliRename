"""Central configuration settings for the PDF Renamer tool."""

import os
from typing import Final, Optional

# --- AI Enhancement Settings ---

# Confidence threshold for metadata quality (0.0-1.0)
# Lower values will trigger AI enhancement more frequently
CONFIDENCE_THRESHOLD: Final[float] = 0.7

# Maximum API retries on failure
MAX_RETRIES: Final[int] = 3

# --- API Request Parameters ---

# Perplexity API model temperature (controls randomness, lower is more deterministic)
TEMPERATURE: Final[float] = 0.1

# Maximum number of tokens to generate in API response
MAX_TOKENS: Final[int] = 500

# --- Cache Settings ---

# Whether to use caching for API responses
USE_CACHE: Final[bool] = True

# Default directory for caching API responses
# Uses ~/.book_renamer/cache if not overridden
DEFAULT_CACHE_DIR: Final[str] = os.path.expanduser("~/.book_renamer/cache")

# --- API Keys (Loaded from environment) ---

# Load the Perplexity API key from the .env file or environment variables
# Ensure you have a .env file in the project root with PERPLEXITY_API_KEY=...
# or set the environment variable directly.
# NOTE: The .env file should NOT be committed to version control.
PERPLEXITY_API_KEY: Final[Optional[str]] = os.getenv("PERPLEXITY_API_KEY")
