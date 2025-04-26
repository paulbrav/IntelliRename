# IntelliRename

A Python tool to intelligently rename PDF and EPUB book and academic paper files with accurate metadata.

## Features

- **Smart Metadata Extraction**: Extracts Author, Title, and Year information from filenames and document content
- **AI-Powered Enhancement**: Uses Perplexity API to search the web and correct incomplete or garbled metadata
- **Format Standardization**: Renames files to a consistent format suitable for digital libraries like Calibre
- **Batch Processing**: Processes multiple files at once, with recursive directory support
- **Concurrent API Calls**: Uses `asyncio` and `aiohttp` for faster processing when AI enhancement is enabled for multiple files
- **Dry Run Mode**: Preview changes before applying them
- **Flexible Configuration**: Control confidence thresholds and processing options
- **Caching**: Stores API results to minimize redundant web searches

## Configuration

All non-secret configuration options (such as confidence threshold, retries, temperature, max tokens, and cache settings) are now managed in `intellirename/config.py`. You can edit this file to adjust the tool's behavior.

Only the Perplexity API key is set via environment variable. You can set it in your shell:

```bash
export PERPLEXITY_API_KEY=your_api_key_here
```

The tool will automatically load this key at runtime.

## Caching

Caching options (such as `USE_CACHE` and `DEFAULT_CACHE_DIR`) are now set in `intellirename/config.py` or via environment variables:

```bash
export USE_CACHE=true
export CACHE_DIR=~/.intellirename/cache
```

## Dependencies

- Python 3.8+
- `uv` (for installation/environment management)
- `aiohttp`: For asynchronous HTTP requests to the Perplexity API.
- `PyPDF2`: For PDF metadata extraction.
- `python-dateutil`: For robust date parsing.
- `rich`: For enhanced console logging and progress bars.
- `python-dotenv`: For loading environment variables (like API keys).
- `pathvalidate`: For sanitizing filenames.

### Development Dependencies

- `pytest`: For running tests.
- `pytest-asyncio`: For testing asynchronous code.
- `mypy`: For static type checking.
- `types-*`: Type stubs for various libraries.

## Installation

### Install the CLI tool via uv

Clone the repository and install with uv:

```bash
git clone https://github.com/yourusername/intellirename.git
cd intellirename
uv tool install --from git+https://github.com/yourusername/intellirename.git
```

If the package is published on PyPI, you can install directly:

```bash
uv tool install intellirename
```

Now you can run the CLI like any other Unix program:

```bash
intellirename /path/to/your/books
```

Optionally upgrade or manage the tool:

```bash
uv tool upgrade intellirename
```

### Interactive/Development Install with uv

For development or if you prefer managing the environment yourself:

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/yourusername/intellirename.git
    cd intellirename
    ```

2.  **Create a virtual environment and sync dependencies:**
    ```bash
    # Create the virtual environment in .venv
    uv venv

    # Install dependencies (including optional dev dependencies)
    uv pip install -e .[dev]
    ```

3.  **Run the tool:**
    You can run the tool directly using `uv run` or by activating the environment first.

    *   **Using `uv run`:**
        ```bash
        uv run intellirename /path/to/your/books --enable-ai
        ```
    *   **Activate the environment:**
        ```bash
        source .venv/bin/activate
        # Now you can run the command directly
        intellirename /path/to/your/books --enable-ai
        # Deactivate when done
        deactivate
        ```

## API Keys

This tool uses the Perplexity API for enhanced metadata extraction. You'll need to:

1. Get a Perplexity API key from [https://perplexity.ai](https://perplexity.ai)
2. Set the environment variable before running the tool:

```bash
export PERPLEXITY_API_KEY=your_api_key_here
```

## Usage

Basic usage:

```bash
intellirename /path/to/your/books
```

Advanced options:

```bash
intellirename /path/to/your/books --recursive --enable-ai --confidence-threshold 0.6 --verbose
```

### Command Line Arguments

| Option | Description |
|--------|-------------|
| `target` | One or more file paths or directories containing files to process. |
| `--recursive`, `-r` | Recursively search for files in directories. |
| `--dry-run` | Show what would be renamed without actually changing files. |
| `--log-level` | Set the logging level (DEBUG, INFO, WARNING, ERROR). Default: INFO |
| `--use-ai` | Enable AI-powered metadata enhancement using Perplexity API. |
| `--confidence` | Metadata confidence score threshold (0.0-1.0) below which AI enhancement is triggered. |
| `--no-advanced` | Disable advanced PDF metadata extraction (faster but potentially less accurate). |
| `--min-year` | Minimum valid publication year for metadata cleaning. |
| `--max-year` | Maximum valid publication year for metadata cleaning. |

## AI-Powered Metadata Enhancement

When the `--enable-ai` flag is used, the tool will:

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
intellirename ~/Documents/Books --recursive --enable-ai --verbose
```

## License

This project is licensed under the MIT License - see the LICENSE file for details. 