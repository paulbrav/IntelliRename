# IntelliRename: AI-Powered Book & Paper Renamer

A Python tool to intelligently rename PDF and EPUB book and academic paper files with accurate metadata.

## Quick Start

```bash
# Install using uv (tool interface)
uv tool install intellirename

# Process files in a directory (dry-run by default)
intellirename ~/Downloads/papers --recursive

# Enable AI enhancement (requires PERPLEXITY_API_KEY env var)
intellirename ~/Downloads/books --ai

# Actually rename the files
intellirename ~/Downloads/books --recursive --no-dry-run
```

## Features

- **Accurate Metadata Extraction:** Parses author, title, and year from filenames and PDF/EPUB content.
- **Advanced PDF Analysis:** Optionally performs deeper analysis of PDF structure for better metadata (enabled by default, disable with `--no-advanced`).
- **Metadata Cleaning:** Fixes common issues like garbled text or incorrect formatting.
- **AI-Powered Enhancement:** Uses Perplexity AI (if enabled with `--ai`) to find high-quality metadata when local extraction is insufficient or below a confidence threshold (`--confidence`).
- **Standardized Renaming:** Renames files to `Author(s) - Title (Year).ext` format (customizable pattern planned), similar to common [Calibre library conventions](https://manual.calibre-ebook.com/template_lang.html).
- **Format Standardization**: Renames files to a consistent format suitable for digital libraries like Calibre
- **Batch Processing**: Processes multiple files at once, with recursive directory support
- **Concurrent API Calls**: Uses `asyncio` and `aiohttp` for faster processing when AI enhancement is enabled for multiple files
- **Dry Run Mode**: Preview changes before applying them
- **Flexible Configuration**: Control confidence thresholds and processing options
- **Caching**: Stores API results to minimize redundant web searches

## How it Works

IntelliRename follows these steps for each file:

1.  **File Discovery:** Finds PDF and EPUB files in the specified paths (recursively if requested).
2.  **Initial Metadata Extraction:** Extracts Author, Title, and Year from:
    *   The existing filename (using pattern matching).
    *   The file's internal metadata (PDF properties or EPUB metadata).
    *   Optionally, advanced PDF text content analysis (if `--no-advanced` is not used).
3.  **Metadata Merging & Cleaning:** Combines metadata from different sources, prioritizes potentially better sources, and cleans common formatting issues.
4.  **Quality Check:** Calculates a confidence score for the extracted metadata.
5.  **AI Enhancement (Optional):** If the `--ai` flag is enabled and the confidence score is below the `--confidence` threshold, IntelliRename queries the Perplexity API to find more accurate metadata.
6.  **Filename Generation:** Creates a new filename based on the cleaned (and potentially AI-enhanced) metadata, following a standard format (`Author(s) - Title (Year).ext`).
7.  **Sanitization:** Ensures the new filename is valid for the filesystem.
8.  **Renaming:** Renames the file (unless `--dry-run` is active).

## Configuration & API Keys

IntelliRename can be configured via command-line arguments, environment variables, or default values set in the code. The order of precedence is:

1.  **Command-Line Arguments:** Highest priority (e.g., `--ai`, `--confidence`).
2.  **Environment Variables:** Set before running the script (e.g., `export PERPLEXITY_API_KEY="your_key"`).
3.  **Default Values:** Defined in `intellirename/config.py` (around lines 20-60).

### Key Configuration Options:

*   **API Key:**
    *   For AI features (`--ai`), you need a Perplexity API key.
    *   Set the `PERPLEXITY_API_KEY` environment variable.
    *   You can get a key and view API documentation at [Perplexity AI](https://docs.perplexity.ai/).
*   **Caching:**
    *   Caching is used to store results from expensive operations (like AI calls) to speed up subsequent runs and reduce API usage.
    *   Enabled by default (`USE_CACHE=true`). Disable by setting the environment variable `USE_CACHE=false`.
    *   Cache location defaults to a platform-specific cache directory (e.g., `~/.cache/intellirename` on Linux). Override with the `CACHE_DIR` environment variable.
    *   Example:
        ```bash
        export USE_CACHE=true
        export CACHE_DIR=/path/to/custom/cache
        intellirename ...
        ```
*   **Other Defaults:**
    *   Review `intellirename -h` for all options and their corresponding environment variables.
    *   Consult `intellirename/config.py` for the hardcoded default values (e.g., `DEFAULT_CONFIDENCE_THRESHOLD`, `DEFAULT_MIN_VALID_YEAR`).

## Dependencies

<details>
<summary>Click to view runtime and development dependencies</summary>

### Runtime Dependencies

*   Python 3.9+
*   `uv`: Recommended for installation and environment management.
*   `rich`: For pretty terminal output and logging.
*   `PyPDF2`: For reading PDF metadata and content.
*   `python-dotenv`: For loading environment variables (like API keys).
*   `ebooklib`: For reading EPUB metadata.
*   `aiohttp`: For asynchronous HTTP requests to the AI API.
*   `beautifulsoup4`: Used by `ebooklib` and potentially for web scraping (if added later).
*   `lxml`: Used by `ebooklib`.
*   `Naked`: Used by `ebooklib`.
*   `requests`: Used by `ebooklib`.

### Development Dependencies (`dev` extra)

*   `pytest`: For running tests.
*   `pytest-asyncio`: For testing async code.
*   `pytest-cov`: For test coverage reports.
*   `mypy`: For static type checking.
*   `ruff`: For linting and code formatting.
*   `pre-commit`: For running checks before commits.

</details>

## Installation

Requires Python 3.9+ and `uv` (the Rust-based Python package installer and resolver).

### Standard Installation (as CLI Tool)

Use this method to install `intellirename` as a command-line tool available system-wide (requires `~/.local/bin` or equivalent to be in your PATH).

# 1. Clone the repository (if you haven't already)
git clone https://github.com/your-username/intellirename.git
cd intellirename

# 2. Install the tool from the local source
uv tool install .

# (Optional) Install directly from the git repository (builds locally)
# uv tool install git+https://github.com/your-username/intellirename.git

### Development Installation

Clone the repository and install in *editable mode* within a virtual environment. This is ideal for making changes to the code.

```bash
git clone https://github.com/your-username/intellirename.git
cd intellirename

# Create and activate a virtual environment using uv
uv venv
# source .venv/bin/activate  # Manual activation if needed

# Install in editable mode with dev dependencies
uv pip install -e ".[dev]"

# Run tests (using uv run)
uv run pytest
```

Note: `uv venv` automatically detects and uses the `.venv` directory. Subsequent commands prefixed with `uv run` will execute within this environment without needing manual activation.

## Upgrading

If you installed using `uv tool install .` or from git:

```bash
# Reinstall the tool from the local source to get updates
uv tool install . --force
# Or upgrade by name if uv recognizes it (may depend on uv version)
# uv tool upgrade intellirename
```

If you installed using `uv pip install -e .` (Development Installation):

```bash
# Simply pull the latest changes, the editable install reflects them
git pull
# If dependencies changed, re-sync the virtual environment
uv sync
```

## Usage

Basic usage:

```bash
intellirename /path/to/your/books
```

Advanced options:

```bash
intellirename /path/to/your/books --recursive --ai --confidence-threshold 0.6 --verbose
```

### Command Line Arguments

| Option | Description |
|--------|-------------|
| `target` | One or more file paths or directories containing files to process. |
| `--recursive`, `-r` | Recursively search for files in directories. |
| `--dry-run` | Show what would be renamed without actually changing files. |
| `--log-level` | Set the logging level (DEBUG, INFO, WARNING, ERROR). Default: INFO |
| `--ai` | Enable AI-powered metadata enhancement using Perplexity API. |
| `--confidence` | Metadata confidence score threshold (0.0-1.0) below which AI enhancement is triggered. |
| `--no-advanced` | Disable advanced PDF metadata extraction (faster but potentially less accurate). |
| `--min-year` | Minimum valid publication year for metadata cleaning. |
| `--max-year` | Maximum valid publication year for metadata cleaning. |
| `-h`, `--help` | Show this help message and exit.

**Note:** Command-line arguments override environment variables, which in turn override default values set in `intellirename/config.py`. The output of `intellirename -h` provides the most up-to-date list of options and their defaults.

## AI-Powered Metadata Enhancement

When the `--ai` flag is used, the tool will:

1. Evaluate the quality of extracted metadata
2. For files with low-quality or incomplete metadata, query the Perplexity API
3. The API searches the web for accurate bibliographic information
4. Corrected metadata is used to rename the file

The `--confidence-threshold` parameter controls when AI enhancement is triggered:
- Lower values (e.g., 0.5) will use AI more aggressively
- Higher values (e.g., 0.9) will only use AI for very poor metadata

### Caching

The tool caches API results to minimize redundant API calls. You can configure caching in your `.env` file:

```
USE_CACHE=true
CACHE_DIR=~/.intellirename/cache
```

## Examples

Fix garbled metadata:
```bash
# Input: "S_or Dargo - Daily C++ Interview.epub"
# Output: "Sandor_Dargo_Daily_C++_Interview_2023.epub"
```

Process a directory with all options:
```bash
intellirename ~/Documents/Books --recursive --ai --verbose
```

### Enhance Low-Quality Metadata with AI

If a file has poor internal metadata, enable AI enhancement:

```bash
intellirename "My Ambiguous Document.pdf" --ai --no-dry-run --confidence 0.5
# Requires PERPLEXITY_API_KEY to be set
```

## License

This project is licensed under the MIT License - see the LICENSE file for details. 