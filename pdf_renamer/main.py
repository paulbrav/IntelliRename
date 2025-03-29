#!/usr/bin/env python3
"""
Rename book and paper files (PDF, EPUB) with accurate metadata.

This script processes book and academic paper files, extracts metadata (Author, Title, Year)
from filenames and content, cleans garbled metadata, and renames files to a standardized format.
Uses AI and web search capabilities to enhance metadata quality when needed.
"""

import argparse
import logging
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

import PyPDF2
from dateutil import parser as date_parser
from dotenv import load_dotenv
from rich.console import Console
from rich.logging import RichHandler
from rich.progress import Progress, SpinnerColumn, TextColumn

# Import AI metadata enhancement
try:
    from pdf_renamer.utils.ai_metadata import enhance_metadata, validate_perplexity_api_key
    AI_AVAILABLE = True
except ImportError:
    AI_AVAILABLE = False

# Load environment variables
load_dotenv()

# Configure logging with rich
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(rich_tracebacks=True)]
)
log = logging.getLogger("book_renamer")
console = Console()

# Get configuration from environment
DEFAULT_CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.7"))

# Filename parsing patterns
FILENAME_PATTERNS = [
    # "[Publisher] Author(s) - Title (Year, Publisher).pdf"
    re.compile(r"^\[.*?\]\s*(.+?)\s*-\s*(.+?)\s*\((\d{4}).*?\)\.(pdf|epub)$", re.IGNORECASE),
    # "Author(s) - Title (Year).pdf"
    re.compile(r"^(.+?)\s*-\s*(.+?)\s*\((\d{4}).*?\)\.(pdf|epub)$", re.IGNORECASE),
    # "Title - Author(s) (Year).pdf"
    re.compile(r"^(.+?)\s*-\s*(.+?)\s*\((\d{4}).*?\)\.(pdf|epub)$", re.IGNORECASE),
    # "Title (Year).pdf"
    re.compile(r"^(.+?)\s*\((\d{4}).*?\)\.(pdf|epub)$", re.IGNORECASE),
    # "Author(s) - Title.pdf"
    re.compile(r"^(.+?)\s*-\s*(.+?)\.(pdf|epub)$", re.IGNORECASE),
]

# Placeholder values for missing information
UNKNOWN_AUTHOR = "Unknown_Author"
UNKNOWN_TITLE = "Untitled"
UNKNOWN_YEAR = "0000"

# Illegal filesystem characters to replace
ILLEGAL_CHARS = r'[<>:"/\\|?*]'

# Characters to replace with underscores for computer-friendly names
REPLACE_WITH_UNDERSCORE = r'[ ,;()]'


def extract_from_filename(filename: str) -> Dict[str, str]:
    """
    Extract metadata from the filename using predefined patterns.
    
    Args:
        filename: The filename to parse
        
    Returns:
        Dict containing extracted author, title, and year
    """
    base_filename = os.path.basename(filename)
    
    for pattern in FILENAME_PATTERNS:
        match = pattern.match(base_filename)
        if match:
            groups = match.groups()
            if len(groups) >= 3:  # Author, Title, Year, (Extension)
                return {
                    "author": groups[0].strip(),
                    "title": groups[1].strip(),
                    "year": groups[2].strip(),
                    "extension": groups[3].lower() if len(groups) > 3 else Path(filename).suffix[1:].lower()
                }
            elif len(groups) == 2:
                # Could be Title, Year or Author, Title
                if groups[1].isdigit() and len(groups[1]) == 4:
                    return {
                        "author": UNKNOWN_AUTHOR,
                        "title": groups[0].strip(),
                        "year": groups[1],
                        "extension": Path(filename).suffix[1:].lower()
                    }
                else:
                    return {
                        "author": groups[0].strip(),
                        "title": groups[1].strip(),
                        "year": UNKNOWN_YEAR,
                        "extension": Path(filename).suffix[1:].lower()
                    }
    
    # If no pattern matched, just use the filename as the title
    return {
        "author": UNKNOWN_AUTHOR,
        "title": os.path.splitext(base_filename)[0],
        "year": UNKNOWN_YEAR,
        "extension": Path(filename).suffix[1:].lower()
    }


def extract_from_pdf(pdf_path: str) -> Dict[str, str]:
    """
    Extract metadata from PDF file.
    
    Args:
        pdf_path: Path to the PDF file
        
    Returns:
        Dict containing extracted author, title, and year
    """
    result = {
        "author": UNKNOWN_AUTHOR,
        "title": UNKNOWN_TITLE,
        "year": UNKNOWN_YEAR
    }
    
    if not pdf_path.lower().endswith('.pdf'):
        return result
    
    try:
        with open(pdf_path, "rb") as f:
            pdf = PyPDF2.PdfReader(f)
            info = pdf.metadata
            
            if info and info.author:
                result["author"] = info.author
                
            if info and info.title:
                result["title"] = info.title
                
            # Try to extract year from creation date
            if info and info.creation_date:
                try:
                    # Parse the PDF date format
                    date_str = info.creation_date
                    date = date_parser.parse(date_str)
                    result["year"] = str(date.year)
                except (ValueError, TypeError):
                    pass
    except Exception as e:
        log.warning(f"Error reading PDF metadata from {pdf_path}: {str(e)}")
        
    return result


def extract_from_epub(epub_path: str) -> Dict[str, str]:
    """
    Extract metadata from EPUB file.
    
    Args:
        epub_path: Path to the EPUB file
        
    Returns:
        Dict containing extracted author, title, and year
    """
    result = {
        "author": UNKNOWN_AUTHOR,
        "title": UNKNOWN_TITLE,
        "year": UNKNOWN_YEAR
    }
    
    if not epub_path.lower().endswith('.epub'):
        return result
    
    try:
        # Try to import epub library only when needed
        import zipfile
        from xml.etree import ElementTree as ET
        
        # EPUB files are ZIP files with metadata in META-INF/container.xml and content.opf
        with zipfile.ZipFile(epub_path, 'r') as zip_ref:
            # First, find the content.opf file location
            try:
                container = zip_ref.read('META-INF/container.xml')
                container_root = ET.fromstring(container)
                # Find the content.opf path
                ns = {'ns': 'urn:oasis:names:tc:opendocument:xmlns:container'}
                content_path = container_root.find('.//ns:rootfile', ns).get('full-path')
                
                # Read the content.opf file
                content = zip_ref.read(content_path)
                content_root = ET.fromstring(content)
                
                # Define namespaces
                dc_ns = {'dc': 'http://purl.org/dc/elements/1.1/', 
                         'opf': 'http://www.idpf.org/2007/opf'}
                
                # Extract metadata
                title_elem = content_root.find('.//dc:title', dc_ns)
                if title_elem is not None and title_elem.text:
                    result["title"] = title_elem.text
                
                # Author might be in creator element
                creator_elem = content_root.find('.//dc:creator', dc_ns)
                if creator_elem is not None and creator_elem.text:
                    result["author"] = creator_elem.text
                
                # Look for date, which might contain year
                date_elem = content_root.find('.//dc:date', dc_ns)
                if date_elem is not None and date_elem.text:
                    # Try to extract year from date
                    date_match = re.search(r'\b(19|20)\d{2}\b', date_elem.text)
                    if date_match:
                        result["year"] = date_match.group(0)
            except (KeyError, ET.ParseError) as e:
                log.warning(f"Error parsing EPUB metadata structure in {epub_path}: {str(e)}")
                
    except ImportError:
        log.warning("zipfile module not available; skipping EPUB metadata extraction")
    except Exception as e:
        log.warning(f"Error reading EPUB metadata from {epub_path}: {str(e)}")
        
    return result


def extract_advanced_metadata_fallback(file_path: str) -> Dict[str, str]:
    """
    Extract metadata using advanced heuristics as a fallback.
    
    Args:
        file_path: Path to the file
        
    Returns:
        Dict containing extracted author, title, and year
    """
    if file_path.lower().endswith('.pdf'):
        try:
            from pdf_renamer.metadata import extract_advanced_metadata
            return extract_advanced_metadata(file_path)
        except Exception as e:
            log.warning(f"Error in advanced metadata extraction from {file_path}: {str(e)}")
    
    return {
        "author": UNKNOWN_AUTHOR,
        "title": UNKNOWN_TITLE,
        "year": UNKNOWN_YEAR
    }


def merge_metadata(filename_data: Dict[str, str], content_data: Dict[str, str], advanced_data: Dict[str, str]) -> Dict[str, str]:
    """
    Merge metadata from filename, file content, and advanced extraction, prioritizing filename data.
    
    Args:
        filename_data: Metadata extracted from filename
        content_data: Metadata extracted from file content
        advanced_data: Metadata extracted using advanced heuristics
        
    Returns:
        Dict containing merged metadata
    """
    result = filename_data.copy()
    
    # Author: Prioritize filename > content metadata > advanced extraction
    if result["author"] == UNKNOWN_AUTHOR:
        if content_data["author"] != UNKNOWN_AUTHOR:
            result["author"] = content_data["author"]
        elif advanced_data["author"] != UNKNOWN_AUTHOR:
            result["author"] = advanced_data["author"]
    
    # Title: Prioritize filename > content metadata > advanced extraction
    if result["title"] == UNKNOWN_TITLE:
        if content_data["title"] != UNKNOWN_TITLE:
            result["title"] = content_data["title"]
        elif advanced_data["title"] != UNKNOWN_TITLE:
            result["title"] = advanced_data["title"]
    
    # Year: Prioritize filename > advanced extraction > content metadata
    if result["year"] == UNKNOWN_YEAR:
        if advanced_data["year"] != UNKNOWN_YEAR:
            result["year"] = advanced_data["year"]
        elif content_data["year"] != UNKNOWN_YEAR:
            result["year"] = content_data["year"]
    
    return result


def clean_metadata(metadata: Dict[str, str]) -> Dict[str, str]:
    """
    Clean and standardize extracted metadata.
    
    Args:
        metadata: The raw extracted metadata
        
    Returns:
        Dict containing cleaned metadata
    """
    result = metadata.copy()
    
    # Clean author names
    author = result["author"]
    # Handle multiple authors
    authors = [a.strip() for a in re.split(r',|&|;|and', author) if a.strip()]
    
    # Process each author name to ensure consistency
    processed_authors = []
    for auth in authors:
        # Remove extra spaces and standardize capitalization
        auth = ' '.join(auth.split())
        # Keep existing capitalization as author names are often LastName, FirstName
        processed_authors.append(auth)
    
    if len(processed_authors) > 3:
        result["author"] = f"{processed_authors[0]}_et_al"
    elif len(processed_authors) > 1:
        result["author"] = "_".join(processed_authors)
    elif len(processed_authors) == 1:
        result["author"] = processed_authors[0]
    else:
        result["author"] = UNKNOWN_AUTHOR
        
    # Clean title: remove extra whitespace and convert to title case
    title_words = result["title"].split()
    # Apply title case but preserve acronyms and capitalized words
    title_words = [w.capitalize() if w.lower() == w or w.upper() == w else w for w in title_words]
    result["title"] = "_".join(title_words)
    
    # Validate year
    year = result["year"]
    if not (str(year).isdigit() and len(str(year)) == 4 and 1800 <= int(year) <= datetime.now().year):
        result["year"] = UNKNOWN_YEAR
    
    # Make computer-friendly
    result["author"] = make_computer_friendly(result["author"])
    result["title"] = make_computer_friendly(result["title"])
        
    return result


def make_computer_friendly(text: str) -> str:
    """
    Make text computer-friendly by replacing spaces and special characters with underscores.
    Preserves original capitalization for readability.
    
    Args:
        text: The text to make computer-friendly
        
    Returns:
        Computer-friendly text
    """
    # Replace illegal characters
    friendly = re.sub(ILLEGAL_CHARS, "_", text)
    
    # Replace spaces and other separators with underscores
    friendly = re.sub(REPLACE_WITH_UNDERSCORE, "_", friendly)
    
    # Replace multiple underscores with a single underscore
    friendly = re.sub(r'_+', '_', friendly)
    
    # Remove trailing/leading underscores
    friendly = friendly.strip('_')
    
    return friendly


def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename to ensure filesystem compatibility while maintaining readability.
    
    Args:
        filename: The filename to sanitize
        
    Returns:
        Sanitized filename
    """
    # Replace only illegal characters, not spaces and parentheses for better readability
    sanitized = re.sub(ILLEGAL_CHARS, "_", filename)
    
    # Replace multiple spaces with single space
    sanitized = re.sub(r'\s+', ' ', sanitized)
    
    # Ensure the filename is not too long (255 chars is a common limit)
    if len(sanitized) > 240:  # Leave room for extension
        base, ext = os.path.splitext(sanitized)
        sanitized = base[:236] + ext  # 236 + 4 (.pdf/.epub) = 240
        
    return sanitized


def generate_new_filename(metadata: Dict[str, str]) -> str:
    """
    Generate new filename based on metadata.
    
    Args:
        metadata: The cleaned metadata
        
    Returns:
        The new filename in the format "Author_Title_Year.ext" with improved readability
    """
    extension = metadata.get("extension", "pdf")
    
    # Convert underscores to spaces for better readability in the final filename
    author = metadata['author'].replace('_', ' ')
    title = metadata['title'].replace('_', ' ')
    year = metadata['year']
    
    # Create filename with better human readability using hyphens and parentheses
    new_name = f"{author} - {title} ({year}).{extension}"
    
    return sanitize_filename(new_name)


def rename_file(
    source_path: str, 
    new_filename: str, 
    dry_run: bool = False
) -> Tuple[bool, str]:
    """
    Rename a file with collision detection.
    
    Args:
        source_path: Path to the source file
        new_filename: The new filename (not path)
        dry_run: If True, don't actually rename
        
    Returns:
        Tuple of (success, message)
    """
    source = Path(source_path)
    target_dir = source.parent
    target_path = target_dir / new_filename
    
    # Handle filename collision
    counter = 1
    original_name_base, ext = os.path.splitext(new_filename)
    while target_path.exists():
        new_name = f"{original_name_base}_{counter}{ext}"
        target_path = target_dir / new_name
        counter += 1
    
    if dry_run:
        return True, f"Would rename '{source.name}' to '{target_path.name}'"
    
    try:
        source.rename(target_path)
        return True, f"Renamed '{source.name}' to '{target_path.name}'"
    except Exception as e:
        return False, f"Error renaming '{source.name}': {str(e)}"


def process_file(file_path: str, dry_run: bool = False, use_advanced: bool = True, use_ai: bool = False, confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD) -> Dict[str, str]:
    """
    Process a single file.
    
    Args:
        file_path: Path to the file
        dry_run: If True, don't actually rename files
        use_advanced: If True, use advanced metadata extraction as fallback
        use_ai: If True, use AI-powered metadata enhancement
        confidence_threshold: Threshold for using AI enhancement
        
    Returns:
        Dict with processing results
    """
    result = {
        "status": "skipped",
        "message": "",
        "original_name": os.path.basename(file_path),
        "new_name": ""
    }
    
    # Determine file type
    is_pdf = file_path.lower().endswith('.pdf')
    is_epub = file_path.lower().endswith('.epub')
    
    if not (is_pdf or is_epub):
        result["message"] = f"Skipped '{os.path.basename(file_path)}' - not a PDF or EPUB file"
        return result
    
    # Step 1: Extract metadata from filename
    filename_data = extract_from_filename(file_path)
    
    # Step 2: Extract metadata from file content
    content_data = {}
    if is_pdf:
        content_data = extract_from_pdf(file_path)
    elif is_epub:
        content_data = extract_from_epub(file_path)
    else:
        content_data = {
            "author": UNKNOWN_AUTHOR,
            "title": UNKNOWN_TITLE,
            "year": UNKNOWN_YEAR
        }
    
    # Step 3: Use advanced extraction if needed
    advanced_data = {
        "author": UNKNOWN_AUTHOR,
        "title": UNKNOWN_TITLE,
        "year": UNKNOWN_YEAR
    }
    
    missing_data = (
        filename_data["author"] == UNKNOWN_AUTHOR or
        filename_data["title"] == UNKNOWN_TITLE or
        filename_data["year"] == UNKNOWN_YEAR
    )
    
    if use_advanced and missing_data and is_pdf:  # Advanced extraction only for PDFs
        log.debug(f"Using advanced metadata extraction for {file_path}")
        advanced_data = extract_advanced_metadata_fallback(file_path)
    
    # Step 4: Merge metadata, prioritizing filename data
    merged_data = merge_metadata(filename_data, content_data, advanced_data)
    
    # Step 5: Use AI-powered enhancement if enabled and needed
    unknown_markers = {
        "author": UNKNOWN_AUTHOR,
        "title": UNKNOWN_TITLE,
        "year": UNKNOWN_YEAR
    }
    
    if use_ai and AI_AVAILABLE:
        # Check if API is valid before attempting to use it
        if not validate_perplexity_api_key():
            log.error("Cannot use AI enhancement: Invalid or missing Perplexity API key")
            log.error("Please set a valid API key in your .env file with PERPLEXITY_API_KEY=pplx-...")
        else:
            log.debug(f"Using AI-powered metadata enhancement for {file_path}")
            try:
                enhanced_metadata = enhance_metadata(
                    merged_data, 
                    os.path.basename(file_path),
                    unknown_markers,
                    confidence_threshold
                )
                
                # Only update merged_data if we actually got enhanced metadata back
                if enhanced_metadata != merged_data:
                    merged_data = enhanced_metadata
                    log.debug("Successfully enhanced metadata with AI")
            except Exception as e:
                log.warning(f"Error in AI metadata enhancement: {str(e)}")
    
    # Step 6: Clean and standardize metadata
    cleaned_data = clean_metadata(merged_data)
    
    # Step 7: Generate new filename
    new_filename = generate_new_filename(cleaned_data)
    result["new_name"] = new_filename
    
    # Step 8: If the original name is already in the correct format, skip renaming
    if os.path.basename(file_path) == new_filename:
        result["status"] = "skipped"
        result["message"] = f"Skipped '{os.path.basename(file_path)}' - already in correct format"
        return result
    
    # Step 9: Rename the file
    success, message = rename_file(file_path, new_filename, dry_run)
    result["message"] = message
    
    if success:
        result["status"] = "success" if not dry_run else "would_rename"
    else:
        result["status"] = "error"
        
    return result


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="Rename book and paper files (PDF, EPUB) with accurate metadata")
    parser.add_argument(
        "directory", 
        nargs="?", 
        default=".", 
        help="Directory containing files (default: current directory)"
    )
    parser.add_argument(
        "--dry-run", 
        action="store_true", 
        help="Show what would be renamed without making changes"
    )
    parser.add_argument(
        "--recursive", "-r",
        action="store_true",
        help="Recursively process subdirectories"
    )
    parser.add_argument(
        "--no-advanced",
        action="store_true",
        help="Disable advanced metadata extraction (faster but less accurate)"
    )
    parser.add_argument(
        "--enable-ai",
        action="store_true",
        help="Enable AI-powered metadata enhancement using Perplexity API"
    )
    parser.add_argument(
        "--confidence-threshold",
        type=float,
        default=DEFAULT_CONFIDENCE_THRESHOLD,
        help="Confidence threshold for using AI enhancement (0.0-1.0)"
    )
    parser.add_argument(
        "--verbose", "-v", 
        action="store_true", 
        help="Enable verbose output"
    )
    parser.add_argument(
        "--type",
        choices=["pdf", "epub", "all"],
        default="all",
        help="File types to process (default: all)"
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        log.setLevel(logging.DEBUG)
    
    # Check for AI capabilities
    if args.enable_ai and not AI_AVAILABLE:
        log.warning("AI enhancement requested but required packages are not available. "
                    "Install with: pip install requests python-dotenv")
        
    # Validate directory
    directory = Path(args.directory)
    if not directory.exists() or not directory.is_dir():
        log.error(f"Directory does not exist or is not a directory: {directory}")
        return 1
    
    # Find files
    file_types = []
    if args.type == "all" or args.type == "pdf":
        file_types.append("pdf")
    if args.type == "all" or args.type == "epub":
        file_types.append("epub")
    
    pattern = "**/*.{" + ",".join(file_types) + "}" if args.recursive else "*.{" + ",".join(file_types) + "}"
    all_files = []
    for file_type in file_types:
        glob_pattern = f"**/*.{file_type}" if args.recursive else f"*.{file_type}"
        all_files.extend(list(directory.glob(glob_pattern)))
    
    if not all_files:
        file_types_str = " and ".join(file_types)
        log.warning(f"No {file_types_str.upper()} files found in {directory}" + 
                    (" and its subdirectories" if args.recursive else ""))
        return 0
    
    log.info(f"Found {len(all_files)} files in {directory}" + 
             (" and its subdirectories" if args.recursive else ""))
    
    # Process files with progress bar
    results = {
        "success": 0,
        "would_rename": 0,
        "error": 0,
        "skipped": 0,
        "ai_enhanced": 0,
        "files_needing_review": []
    }
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        task = progress.add_task(f"Processing {len(all_files)} files...", total=len(all_files))
        
        for file_path in all_files:
            result = process_file(
                str(file_path), 
                dry_run=args.dry_run, 
                use_advanced=not args.no_advanced,
                use_ai=args.enable_ai,
                confidence_threshold=args.confidence_threshold
            )
            
            results[result["status"]] += 1
            
            # Track AI-enhanced files
            if args.enable_ai and AI_AVAILABLE and (
                    result["status"] == "success" or 
                    result["status"] == "would_rename"):
                results["ai_enhanced"] += 1
            
            # Log the result
            if result["status"] == "error":
                log.error(result["message"])
                results["files_needing_review"].append(str(file_path))
            elif result["status"] == "would_rename" and args.dry_run:
                log.info(result["message"])
            elif result["status"] == "success":
                log.debug(result["message"])
            elif result["status"] == "skipped":
                log.debug(result["message"])
                
            # If the new filename contains placeholder data, flag for review
            if UNKNOWN_AUTHOR in result["new_name"] or UNKNOWN_YEAR in result["new_name"]:
                results["files_needing_review"].append(str(file_path))
                
            progress.update(task, advance=1)
    
    # Print summary
    console.print("\n[bold]Summary:[/bold]")
    if args.dry_run:
        console.print(f"Would rename: {results['would_rename']}")
    else:
        console.print(f"Successfully renamed: {results['success']}")
    console.print(f"Skipped: {results['skipped']}")
    console.print(f"Errors: {results['error']}")
    
    if args.enable_ai and AI_AVAILABLE:
        console.print(f"AI-enhanced: {results['ai_enhanced']}")
        
    console.print(f"Files needing review: {len(results['files_needing_review'])}")
    
    if results["files_needing_review"]:
        console.print("\n[bold yellow]Files that may need manual review:[/bold yellow]")
        for file in results["files_needing_review"][:10]:  # Show first 10
            console.print(f"  - {file}")
        if len(results["files_needing_review"]) > 10:
            console.print(f"  ... and {len(results['files_needing_review']) - 10} more")
    
    return 0


if __name__ == "__main__":
    sys.exit(main()) 