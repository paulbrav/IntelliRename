"""
Utilities for advanced metadata extraction from PDF files.

This module provides additional methods for extracting and cleaning
metadata from PDF files beyond the basic PyPDF2 extraction.
"""

import logging
import os
import re
import xml.etree.ElementTree as ET
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import PyPDF2

# Import PyPDF2 exceptions

# Import constants
from intellirename.constants import UNKNOWN_AUTHOR, UNKNOWN_TITLE, UNKNOWN_YEAR

# Import custom exceptions
from intellirename.exceptions import MetadataExtractionError

# Import utility function needed by clean_metadata
from intellirename.utils import make_computer_friendly

log = logging.getLogger("book_renamer.metadata")

# --- Filename Parsing (Moved from main.py) ---
FILENAME_PATTERNS = [
    # "[Publisher] Author(s) - Title (Year, Publisher).ext"
    re.compile(
        r"^\[.*?\]\s*(?P<author>.+?)\s*-\s*(?P<title>.+?)\s*\((?P<year>\d{4}).*?\)\.(?P<ext>pdf|epub)$",
        re.IGNORECASE,
    ),
    # "Author(s) - Title (Year).ext"
    re.compile(
        r"^(?P<author>.+?)\s*-\s*(?P<title>.+?)\s*\((?P<year>\d{4}).*?\)\.(?P<ext>pdf|epub)$",
        re.IGNORECASE,
    ),
    # "Title - Author(s) (Year).ext"
    re.compile(
        r"^(?P<title>.+?)\s*-\s*(?P<author>.+?)\s*\((?P<year>\d{4}).*?\)\.(?P<ext>pdf|epub)$",
        re.IGNORECASE,
    ),
    # "Title (Year).ext"
    re.compile(
        r"^(?P<title>.+?)\s*\((?P<year>\d{4}).*?\)\.(?P<ext>pdf|epub)$",
        re.IGNORECASE,
    ),
    # "Author(s) - Title.ext"
    re.compile(
        r"^(?P<author>.+?)\s*-\s*(?P<title>.+?)\.(?P<ext>pdf|epub)$",
        re.IGNORECASE,
    ),
]


def extract_from_filename(filename: str) -> Dict[str, str]:
    """Extract metadata from a filename using predefined patterns.
    Args: filename (str): The filename to parse.
    Returns: Dict[str, str]: Dictionary with keys 'author', 'title', 'year', 'extension'.
    """
    base_filename = os.path.basename(filename)
    file_path = Path(filename)
    extension = file_path.suffix[1:].lower() if file_path.suffix else ""

    for pattern in FILENAME_PATTERNS:
        match = pattern.match(base_filename)
        if match:
            groups = match.groupdict()
            return {
                "author": groups.get("author", UNKNOWN_AUTHOR).strip(),
                "title": groups.get("title", file_path.stem).strip(),
                "year": groups.get("year", UNKNOWN_YEAR).strip(),
                "extension": groups.get("ext", extension).lower(),
            }

    # Fallback: Use filename as title
    return {
        "author": UNKNOWN_AUTHOR,
        "title": file_path.stem,  # Use Path.stem for filename without extension
        "year": UNKNOWN_YEAR,
        "extension": extension,
    }


def extract_from_pdf(reader: PyPDF2.PdfReader, pdf_path_str: str) -> Dict[str, str]:
    """Extract metadata from an already opened PDF reader object.
    Args:
        reader: The PyPDF2.PdfReader object.
        pdf_path_str (str): Path to the PDF file (for logging).
    Returns:
        Dict[str, str]: Dictionary with keys 'author', 'title', 'year'.
    Raises:
        MetadataExtractionError: If accessing metadata fails.
    """
    result = {"author": UNKNOWN_AUTHOR, "title": UNKNOWN_TITLE, "year": UNKNOWN_YEAR}
    try:
        # Access metadata directly from the reader object
        info = reader.metadata

        if info:
            if info.author:
                result["author"] = info.author
            if info.title:
                result["title"] = info.title
            if info.creation_date:
                try:
                    # Attempt to parse year from creation_date
                    if hasattr(info.creation_date, "year"):
                        result["year"] = str(info.creation_date.year)
                    else:
                        date_str = str(info.creation_date)
                        year_match = re.search(r"(19|20)\d{2}", date_str)
                        if year_match:
                            result["year"] = year_match.group(0)
                except Exception as date_err:
                    log.debug(
                        f"Could not parse date {info.creation_date} from {pdf_path_str}: {date_err}"
                    )
                    pass  # Ignore date parsing errors

    except Exception as e:
        # Catch potential errors accessing reader.metadata or its attributes
        raise MetadataExtractionError(
            f"Unexpected error reading PDF metadata from reader for {pdf_path_str}", e
        ) from e

    return result


def extract_from_epub(epub_path_str: str) -> Dict[str, str]:
    """Extract metadata from an EPUB file by parsing its internal XML files.
    Args: epub_path_str (str): Path to the EPUB file.
    Returns: Dict[str, str]: Dictionary with keys 'author', 'title', 'year'.
    Raises: MetadataExtractionError: If reading or parsing fails.
    """
    epub_path = Path(epub_path_str)
    result = {"author": UNKNOWN_AUTHOR, "title": UNKNOWN_TITLE, "year": UNKNOWN_YEAR}
    if not epub_path.suffix.lower() == ".epub":
        return result

    try:
        with zipfile.ZipFile(epub_path, "r") as zip_ref:
            try:
                container = zip_ref.read("META-INF/container.xml")
                container_root = ET.fromstring(container)
                ns = {"ns": "urn:oasis:names:tc:opendocument:xmlns:container"}
                rootfile = container_root.find(".//ns:rootfile", ns)
                if rootfile is None or "full-path" not in rootfile.attrib:
                    raise MetadataExtractionError(
                        f"Invalid container.xml in {epub_path}"
                    )

                content_path = rootfile.get("full-path")
                # Check if content_path is None before proceeding
                if content_path is None:
                    raise MetadataExtractionError(
                        f"Missing full-path in container.xml for {epub_path}"
                    )

                content = zip_ref.read(
                    content_path
                )  # Now content_path is guaranteed to be str
                content_root = ET.fromstring(content)
                dc_ns = {"dc": "http://purl.org/dc/elements/1.1/"}

                title_elem = content_root.find(".//dc:title", dc_ns)
                if title_elem is not None and title_elem.text:
                    result["title"] = title_elem.text.strip()

                creator_elem = content_root.find(".//dc:creator", dc_ns)
                if creator_elem is not None and creator_elem.text:
                    result["author"] = creator_elem.text.strip()

                date_elem = content_root.find(".//dc:date", dc_ns)
                if date_elem is not None and date_elem.text:
                    date_match = re.search(r"\b(19|20)\d{2}\b", date_elem.text)
                    if date_match:
                        result["year"] = date_match.group(0)

            except (KeyError, ET.ParseError, ValueError, IndexError) as e:
                raise MetadataExtractionError(
                    f"Error parsing EPUB XML in {epub_path}", e
                ) from e
            except MetadataExtractionError:  # Re-raise errors from checks above
                raise

    except (zipfile.BadZipFile, IOError, OSError) as e:
        raise MetadataExtractionError(f"Error reading EPUB file {epub_path}", e) from e
    except Exception as e:
        raise MetadataExtractionError(
            f"Unexpected error reading EPUB {epub_path}", e
        ) from e

    return result


# --- Merging and Cleaning (Moved from main.py) ---


def merge_metadata(
    filename_data: Dict[str, str],
    content_data: Dict[str, str],
    advanced_data: Dict[str, str],
) -> Dict[str, str]:
    """Merge metadata from filename, file content, and advanced extraction.
    Prioritizes filename > content > advanced for author/title.
    Prioritizes filename > advanced > content for year.
    Args:
        filename_data: Metadata from filename.
        content_data: Metadata from file content (PDF/EPUB).
        advanced_data: Metadata from advanced PDF analysis.
    Returns:
        Merged metadata dictionary.
    """
    # Start with filename data as base, including the 'extension'
    result = filename_data.copy()

    # Ensure advanced_data has default keys if empty
    advanced_data.setdefault("author", UNKNOWN_AUTHOR)
    advanced_data.setdefault("title", UNKNOWN_TITLE)
    advanced_data.setdefault("year", UNKNOWN_YEAR)

    # Ensure content_data has default keys if empty (might happen if file is not PDF/EPUB)
    content_data.setdefault("author", UNKNOWN_AUTHOR)
    content_data.setdefault("title", UNKNOWN_TITLE)
    content_data.setdefault("year", UNKNOWN_YEAR)

    # Author: filename > content > advanced
    if result.get("author", UNKNOWN_AUTHOR) == UNKNOWN_AUTHOR:
        if content_data.get("author", UNKNOWN_AUTHOR) != UNKNOWN_AUTHOR:
            result["author"] = content_data["author"]
        elif advanced_data.get("author", UNKNOWN_AUTHOR) != UNKNOWN_AUTHOR:
            result["author"] = advanced_data["author"]

    # Title: filename > content > advanced
    if result.get("title", UNKNOWN_TITLE) == UNKNOWN_TITLE:
        if content_data.get("title", UNKNOWN_TITLE) != UNKNOWN_TITLE:
            result["title"] = content_data["title"]
        elif advanced_data.get("title", UNKNOWN_TITLE) != UNKNOWN_TITLE:
            result["title"] = advanced_data["title"]

    # Year: filename > advanced > content
    if result.get("year", UNKNOWN_YEAR) == UNKNOWN_YEAR:
        if advanced_data.get("year", UNKNOWN_YEAR) != UNKNOWN_YEAR:
            result["year"] = advanced_data["year"]
        elif content_data.get("year", UNKNOWN_YEAR) != UNKNOWN_YEAR:
            result["year"] = content_data["year"]

    return result


def clean_metadata(
    metadata: Dict[str, str], min_year: int, max_year: int
) -> Dict[str, str]:
    """Clean and standardize extracted metadata fields.

    Args:
        metadata: The raw extracted metadata.
        min_year: The minimum acceptable publication year.
        max_year: The maximum acceptable publication year.

    Returns:
        Dictionary containing cleaned metadata.
    """
    result = metadata.copy()

    # Clean author names
    author = result.get("author", UNKNOWN_AUTHOR)
    # Handle multiple authors separated by common delimiters
    authors = [
        a.strip()
        for a in re.split(r"[,;&]|\\band\\b", author, flags=re.IGNORECASE)
        if a.strip()
    ]

    processed_authors = []
    for auth in authors:
        # Remove extra spaces, keep original capitalization (often LastName, FirstName)
        processed_authors.append(" ".join(auth.split()))

    if len(processed_authors) > 3:
        result["author"] = f"{processed_authors[0]}_et_al"
    elif len(processed_authors) > 0:
        # Join with underscore for computer-friendly internal representation
        result["author"] = "_".join(processed_authors)
    else:
        result["author"] = UNKNOWN_AUTHOR

    # Clean title: remove extra whitespace, convert non-proper nouns to title case?
    # For now, just replace spaces with underscores for internal representation
    title = result.get("title", UNKNOWN_TITLE)
    result["title"] = " ".join(title.split())  # Consolidate whitespace

    # Validate year using provided range
    year_str = result.get("year", UNKNOWN_YEAR)
    try:
        year_int = int(year_str)
        # Use passed-in min_year and max_year for validation
        if not (min_year <= year_int <= max_year):
            log.debug(
                f"Year {year_int} is outside the valid range [{min_year}-{max_year}]."
                f" Resetting to {UNKNOWN_YEAR}."
            )
            result["year"] = UNKNOWN_YEAR
        else:
            result["year"] = str(year_int)  # Ensure it's stored as string
    except (ValueError, TypeError):
        log.debug(f"Invalid year format '{year_str}'. Resetting to {UNKNOWN_YEAR}.")
        result["year"] = UNKNOWN_YEAR

    # Make fields computer-friendly using the utility function
    result["author"] = make_computer_friendly(result["author"])
    result["title"] = make_computer_friendly(result["title"])

    # Keep extension if it exists
    result["extension"] = metadata.get("extension", "")

    return result


# --- Advanced PDF Analysis Helpers ---


def _extract_text_from_pages(reader: PyPDF2.PdfReader, page_indices: List[int]) -> str:
    """Helper to extract text from specific pages using a PdfReader object."""
    text = ""
    try:
        for i in page_indices:
            if 0 <= i < len(reader.pages):
                page = reader.pages[i]
                text += page.extract_text() or ""
    except Exception as e:
        # Log error during text extraction but don't necessarily fail the whole process
        log.warning(f"Error extracting text from pages {page_indices}: {e}")
    return text


def extract_title_from_first_page(
    reader: PyPDF2.PdfReader, pdf_path_str: str
) -> Optional[str]:
    """Attempt to extract a title from the first page text using a PdfReader.

    Looks for larger font sizes or text near the top.
    Args:
        reader: The PyPDF2.PdfReader object.
        pdf_path_str: The path to the PDF file (for logging).
    Returns:
        The extracted title string, or None if not found.
    """
    log.debug(f"Attempting advanced title extraction for: {pdf_path_str}")
    try:
        if not reader.pages:
            return None

        # Extract text from the first page
        first_page_text = _extract_text_from_pages(reader, [0])
        if not first_page_text:
            return None

        lines = first_page_text.split("\n")
        potential_titles = []

        # Simple heuristic: Look for capitalized lines near the top, non-trivial length
        for line in lines[:15]:  # Check top lines
            stripped_line = line.strip()
            if (
                len(stripped_line) > 5
                and stripped_line == stripped_line.title()  # Check title case
                # Avoid lines containing common non-title keywords or just a year
                and not re.search(
                    r"(Abstract|Introduction|Contents|DOI:|\d{4})",
                    stripped_line,
                    re.IGNORECASE,
                )
                and not stripped_line.isupper()  # Avoid all caps lines usually headers/footers
            ):
                potential_titles.append(stripped_line)

        # Prioritize shorter, earlier potential titles if multiple found
        if potential_titles:
            best_title = min(
                potential_titles, key=len
            )  # Simplistic: shortest title-cased line
            log.debug(f"Advanced extracted title: {best_title}")
            return best_title

    except Exception as e:
        log.warning(f"Error during advanced title extraction for {pdf_path_str}: {e}")

    return None


def extract_authors_from_first_page(
    reader: PyPDF2.PdfReader, pdf_path_str: str
) -> Optional[str]:
    """Attempt to extract author names from the first page text using a PdfReader.

    Looks for patterns common in academic papers or books.
    Args:
        reader: The PyPDF2.PdfReader object.
        pdf_path_str: The path to the PDF file (for logging).
    Returns:
        A string of author names (e.g., "John Smith, Jane Doe"), or None.
    """
    log.debug(f"Attempting advanced author extraction for: {pdf_path_str}")
    try:
        if not reader.pages:
            return None

        # Extract text from the first page
        first_page_text = _extract_text_from_pages(reader, [0])
        if not first_page_text:
            return None

        lines = first_page_text.split("\n")
        potential_authors: List[str] = []

        # Heuristic 1: Look for lines with multiple capitalized words, possibly with commas/and
        # Avoid lines that look like titles or affiliations
        author_pattern = re.compile(
            r"^[A-Z][a-z]+(?: [A-Z][a-z\.]*)+(?:(?:, | and | & )+[A-Z][a-z]+(?: [A-Z][a-z\.]*)+)*$"
        )

        for line in lines[:20]:  # Check lines below potential title area
            stripped = line.strip()
            if len(stripped) > 5 and len(stripped) < 100:  # Reasonable length
                # Check if it looks like a name list
                if author_pattern.match(stripped):
                    # Basic check to avoid matching Title Cased Lines
                    if (
                        not stripped.endswith((".", ":", "?", "!"))
                        and stripped == stripped.title()
                    ):
                        potential_authors.append(stripped)
                        log.debug(f"Found potential author line: {stripped}")
                        break  # Often authors are on one line just below title

        # Heuristic 2: Look for lines starting with "By" or "Author(s):"
        if not potential_authors:
            for line in lines[:20]:
                stripped = line.strip()
                if stripped.lower().startswith("by ") and len(stripped) > 3:
                    author_part = stripped[3:].strip()
                    if len(author_part) > 3:
                        potential_authors.append(author_part)
                        log.debug(
                            f"Found potential author line starting with 'By': {author_part}"
                        )
                        break
                elif stripped.lower().startswith("author") and len(stripped) > 7:
                    author_part = stripped.split(":")[-1].strip()
                    if len(author_part) > 3:
                        potential_authors.append(author_part)
                        log.debug(
                            f"Found potential author line starting with 'Author': {author_part}"
                        )
                        break

        if potential_authors:
            # Simple approach: take the first plausible line found
            # Could be improved with scoring or checking against affiliations
            authors_str = potential_authors[0]
            # Clean up common artifacts like email addresses if accidentally included
            authors_str = re.sub(r"\S+@\S+\s*", "", authors_str).strip()
            log.debug(f"Advanced extracted authors: {authors_str}")
            return authors_str

    except Exception as e:
        log.warning(f"Error during advanced author extraction for {pdf_path_str}: {e}")

    return None


def extract_year_from_content(
    reader: PyPDF2.PdfReader,
    pdf_path_str: str,
    min_year: int = 1800,
    max_year: int = datetime.now().year,
) -> Optional[str]:
    """Attempt to extract a plausible publication year from PDF content using a PdfReader.

    Scans first and last few pages for 4-digit years within a plausible range.
    Args:
        reader: The PyPDF2.PdfReader object.
        pdf_path_str: The path to the PDF file (for logging).
        min_year (int): Minimum plausible year.
        max_year (int): Maximum plausible year (current year by default).
    Returns:
        The extracted year string, or None if not found.
    """
    log.debug(f"Attempting advanced year extraction for: {pdf_path_str}")
    years_found = []
    num_pages = len(reader.pages)

    # Pages to scan: first 2 and last 2 (avoiding duplicates if few pages)
    pages_to_scan_indices = list(set([0, 1, num_pages - 2, num_pages - 1]))
    pages_to_scan_indices = [p for p in pages_to_scan_indices if 0 <= p < num_pages]

    try:
        text_to_scan = _extract_text_from_pages(reader, pages_to_scan_indices)
        if not text_to_scan:
            return None

        # Look for 4-digit numbers within the plausible year range
        # \b ensures we match whole words/numbers
        year_pattern = re.compile(r"\b(1[8-9]\d{2}|20\d{2})\b")
        for match in year_pattern.finditer(text_to_scan):
            year = int(match.group(0))
            if min_year <= year <= max_year:
                # Look for context like "Published", "Copyright", "©"
                context_window = text_to_scan[
                    max(0, match.start() - 20) : min(
                        len(text_to_scan), match.end() + 20
                    )
                ]
                if re.search(
                    r"(publish|copyright|©|\bDate\b|received|accepted)",
                    context_window,
                    re.IGNORECASE,
                ):
                    years_found.append(str(year))
                    log.debug(
                        f"Found plausible year {year} with context: ...{context_window}... "
                    )
                elif (
                    len(years_found) < 5
                ):  # Collect a few context-less years just in case
                    years_found.append(str(year))
                    log.debug(f"Found plausible year {year} without strong context.")

        if years_found:
            # Prioritize years with context, often the latest year found is publication year
            # Simple heuristic: return the most frequent year found
            from collections import Counter

            year_counts = Counter(years_found)
            most_common_year = year_counts.most_common(1)[0][0]
            log.debug(f"Advanced extracted year: {most_common_year}")
            return most_common_year

    except Exception as e:
        log.warning(f"Error during advanced year extraction for {pdf_path_str}: {e}")

    return None


# --- Main Advanced Extraction Function ---


def extract_advanced_metadata(
    reader: PyPDF2.PdfReader, pdf_path_str: str
) -> Dict[str, str]:
    """Extract metadata by analyzing PDF content (first page text, etc.) using a PdfReader.

    Args:
        reader: The PyPDF2.PdfReader object.
        pdf_path_str: The path to the PDF file (for logging).

    Returns:
        Dict[str, str]: Dictionary with 'author', 'title', 'year'.
    Raises:
        MetadataExtractionError: If text extraction or analysis fails unexpectedly.
    """
    result = {"author": UNKNOWN_AUTHOR, "title": UNKNOWN_TITLE, "year": UNKNOWN_YEAR}

    try:
        # Extract title from first page text
        title = extract_title_from_first_page(reader, pdf_path_str)
        if title:
            result["title"] = title

        # Extract authors from first page text
        authors = extract_authors_from_first_page(reader, pdf_path_str)
        if authors:
            result["author"] = authors

        # Extract year from content analysis
        year = extract_year_from_content(
            reader, pdf_path_str
        )  # Add min/max year args if needed
        if year:
            result["year"] = year

    except Exception as e:
        # Wrap unexpected errors from helpers
        raise MetadataExtractionError(
            f"Advanced metadata analysis failed for {pdf_path_str}", e
        ) from e

    log.debug(f"Advanced metadata extraction result for {pdf_path_str}: {result}")
    return result
