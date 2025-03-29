# Book & Paper Renamer

A Python tool to intelligently rename PDF and EPUB book and academic paper files with accurate metadata.

## Features

- **Smart Metadata Extraction**: Extracts Author, Title, and Year information from filenames and document content
- **AI-Powered Enhancement**: Uses Perplexity API to search the web and correct incomplete or garbled metadata
- **Format Standardization**: Renames files to a consistent format suitable for digital libraries like Calibre
- **Batch Processing**: Processes multiple files at once, with recursive directory support
- **Dry Run Mode**: Preview changes before applying them
- **Flexible Configuration**: Control confidence thresholds and processing options
- **Caching**: Stores API results to minimize redundant web searches

## Installation

### Quick Install

```bash
git clone https://github.com/yourusername/book-renamer.git
cd book-renamer
./install.sh
```

The install script will:
1. Create a virtual environment
2. Install all dependencies
3. Install the package in development mode
4. Create a `.env` file from the example if it doesn't exist

### Manual Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/book-renamer.git
cd book-renamer

# Create and activate a virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Install the package
pip install -e .

# Set up environment file
cp example.env .env
# Edit .env to add your API key
```

## API Keys

This tool uses the Perplexity API for enhanced metadata extraction. You'll need to:

1. Get a Perplexity API key from [https://perplexity.ai](https://perplexity.ai)
2. Add it to your `.env` file:
```
PERPLEXITY_API_KEY=your_api_key_here
```

## Usage

Basic usage:

```bash
book-renamer /path/to/your/books
```

Advanced options:

```bash
book-renamer /path/to/your/books --recursive --enable-ai --confidence-threshold 0.6 --verbose
```

### Command Line Arguments

| Option | Description |
|--------|-------------|
| `directory` | Directory containing files (default: current directory) |
| `--dry-run` | Show what would be renamed without making changes |
| `--recursive`, `-r` | Recursively process subdirectories |
| `--no-advanced` | Disable advanced metadata extraction (faster but less accurate) |
| `--enable-ai` | Enable AI-powered metadata enhancement using Perplexity API |
| `--confidence-threshold` | Confidence threshold for using AI enhancement (0.0-1.0) |
| `--verbose`, `-v` | Enable verbose output |
| `--type` | File types to process: pdf, epub, or all (default: all) |

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
CACHE_DIR=~/.book_renamer/cache
```

## Examples

Fix garbled metadata:
```bash
# Input: "S_or Dargo - Daily C++ Interview.epub"
# Output: "Sandor_Dargo_Daily_C++_Interview_2023.epub"
```

Process a directory with all options:
```bash
book-renamer ~/Documents/Books --recursive --enable-ai --verbose
```

## License

This project is licensed under the MIT License - see the LICENSE file for details. 