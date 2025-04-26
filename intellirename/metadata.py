"""
Utilities for advanced metadata extraction from PDF files.

This module provides additional methods for extracting and cleaning
metadata from PDF files beyond the basic PyPDF2 extraction.
"""

import logging
import re
from typing import Dict, List, Optional, Tuple

import PyPDF2

# Import constants from the main module
from intellirename.main import UNKNOWN_AUTHOR, UNKNOWN_TITLE, UNKNOWN_YEAR

log = logging.getLogger("book_renamer.metadata")


def extract_title_from_first_page(pdf_path: str) -> Optional[str]:
    """
    Extract title by analyzing the first page content.

    This function attempts to identify a title by looking for large font text
    at the beginning of the document.

    Args:
        pdf_path: Path to the PDF file

    Returns:
        Extracted title or None if extraction failed
    """
    try:
        with open(pdf_path, "rb") as f:
            pdf = PyPDF2.PdfReader(f)
            if len(pdf.pages) > 0:
                # Extract text from the first page
                first_page_text = pdf.pages[0].extract_text()
                if not first_page_text:
                    return None

                # Split by newlines and get first few non-empty lines
                lines = [
                    line.strip() for line in first_page_text.split("\n") if line.strip()
                ]
                if not lines:
                    return None

                # The title is often one of the first few lines
                # Heuristic: Take the longest line from the first 3 lines that's not too long
                candidate_lines = lines[:3]
                title_candidates = [
                    line for line in candidate_lines if 3 < len(line) < 100
                ]

                if title_candidates:
                    return max(title_candidates, key=len)

                # If no good candidates found, just return the first line
                return lines[0][:100] if lines else None
    except Exception:
        return None

    return None


def extract_authors_from_first_page(pdf_path: str) -> Optional[str]:
    """
    Extract authors by analyzing the first page content.

    This function attempts to identify authors typically listed after the title.

    Args:
        pdf_path: Path to the PDF file

    Returns:
        Extracted authors or None if extraction failed
    """
    try:
        with open(pdf_path, "rb") as f:
            pdf = PyPDF2.PdfReader(f)
            if len(pdf.pages) > 0:
                # Extract text from the first page
                first_page_text = pdf.pages[0].extract_text()
                if not first_page_text:
                    return None

                # Split by newlines
                lines = [
                    line.strip() for line in first_page_text.split("\n") if line.strip()
                ]
                if len(lines) < 2:
                    return None

                # Check lines after potential title for author patterns
                for i in range(1, min(5, len(lines))):
                    line = lines[i]

                    # Common author indicators
                    if re.search(r"by\s+", line, re.IGNORECASE):
                        return line.split("by", 1)[1].strip()

                    # Look for patterns like "John Doe, Jane Smith"
                    if re.search(
                        r"^[A-Z][a-z]+\s+[A-Z][a-z]+(\s*,\s*[A-Z][a-z]+\s+[A-Z][a-z]+)*$",
                        line,
                    ):
                        return line

                    # Look for email addresses which often appear with author names
                    if "@" in line and len(line) < 100:
                        return line

                    # Look for affiliation indicators
                    if re.search(
                        r"University|Institute|College|Department", line, re.IGNORECASE
                    ):
                        # Try to get the previous line as the author
                        if i > 1:
                            return lines[i - 1]

                # If nothing found, return the second line as a guess
                if len(lines) > 1 and len(lines[1]) < 100:
                    return lines[1]
    except Exception:
        return None

    return None


def extract_year_from_content(pdf_path: str) -> Optional[str]:
    """
    Extract publication year by analyzing the PDF content.

    This function looks for year patterns in the document text.

    Args:
        pdf_path: Path to the PDF file

    Returns:
        Extracted year or None if extraction failed
    """
    try:
        with open(pdf_path, "rb") as f:
            pdf = PyPDF2.PdfReader(f)

            # Get text from first few pages (to find publication info)
            all_text = ""
            for i in range(min(3, len(pdf.pages))):
                page_text = pdf.pages[i].extract_text()
                if page_text:
                    all_text += page_text

            if not all_text:
                return None

            # Look for year patterns with publication context
            # Priority to year in copyright notice
            copyright_match = re.search(
                r"copyright\s+©?\s*(\d{4})", all_text, re.IGNORECASE
            )
            if copyright_match:
                return copyright_match.group(1)

            # Look for year with publication context
            pub_year_match = re.search(
                r"published\s+in\s+(\d{4})", all_text, re.IGNORECASE
            )
            if pub_year_match:
                return pub_year_match.group(1)

            # Try to find conference/journal with year
            conf_match = re.search(
                r"proceedings\s+of.*?(\d{4})", all_text, re.IGNORECASE
            )
            if conf_match:
                return conf_match.group(1)

            # Last resort: find any 4-digit number that looks like a year (current century or previous)
            import datetime

            current_year = datetime.datetime.now().year
            year_matches = re.findall(r"\b((?:19|20)\d{2})\b", all_text)
            if year_matches:
                # Filter to only possible years (not future, not too old)
                valid_years = [
                    int(y) for y in year_matches if 1900 <= int(y) <= current_year
                ]
                if valid_years:
                    # Get the most frequent year
                    from collections import Counter

                    return str(Counter(valid_years).most_common(1)[0][0])
    except Exception:
        return None

    return None


def extract_advanced_metadata(pdf_path: str) -> Dict[str, str]:
    """
    Extract metadata using advanced heuristics.

    This function combines various extraction methods to get the best metadata possible.

    Args:
        pdf_path: Path to the PDF file

    Returns:
        Dict containing extracted author, title, and year
    """
    result = {"author": UNKNOWN_AUTHOR, "title": UNKNOWN_TITLE, "year": UNKNOWN_YEAR}

    # Try to extract title
    title = extract_title_from_first_page(pdf_path)
    if title:
        result["title"] = title

    # Try to extract authors
    authors = extract_authors_from_first_page(pdf_path)
    if authors:
        result["author"] = authors

    # Try to extract year
    year = extract_year_from_content(pdf_path)
    if year:
        result["year"] = year

    return result
