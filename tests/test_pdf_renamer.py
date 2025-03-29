"""Test cases for the PDF Renamer tool."""

import unittest

# from pathlib import Path
# from unittest.mock import MagicMock, patch
from pdf_renamer.main import (
    clean_metadata,
    extract_from_filename,
    generate_new_filename,
    sanitize_filename,
)


class TestPDFRenamer(unittest.TestCase):
    """Test cases for the PDF Renamer functions."""

    def test_extract_from_filename(self) -> None:
        """Test extracting metadata from various filename formats."""
        # Test common formats
        result = extract_from_filename("Author - Title (2020).pdf")
        self.assertEqual(result["author"], "Author")
        self.assertEqual(result["title"], "Title")
        self.assertEqual(result["year"], "2020")

        # Test with publisher in brackets
        result = extract_from_filename("[Publisher] Author - Title (2020).pdf")
        self.assertEqual(result["author"], "Author")
        self.assertEqual(result["title"], "Title")
        self.assertEqual(result["year"], "2020")

        # Test with only title and year
        result = extract_from_filename("Title (2020).pdf")
        self.assertEqual(result["author"], "Unknown Author")
        self.assertEqual(result["title"], "Title")
        self.assertEqual(result["year"], "2020")

        # Test with only author and title
        result = extract_from_filename("Author - Title.pdf")
        self.assertEqual(result["author"], "Author")
        self.assertEqual(result["title"], "Title")
        self.assertEqual(result["year"], "YYYY")

        # Test with no recognizable pattern
        result = extract_from_filename("some_random_filename.pdf")
        self.assertEqual(result["author"], "Unknown Author")
        self.assertEqual(result["title"], "some_random_filename")
        self.assertEqual(result["year"], "YYYY")

    def test_clean_metadata(self) -> None:
        """Test cleaning and standardizing metadata."""
        # Test multiple authors
        result = clean_metadata(
            {"author": "Author1, Author2, Author3", "title": "Title", "year": "2020"}
        )
        self.assertEqual(result["author"], "Author1, Author2, Author3")

        # Test many authors (should use et al.)
        result = clean_metadata(
            {
                "author": "Author1, Author2, Author3, Author4",
                "title": "Title",
                "year": "2020",
            }
        )
        self.assertEqual(result["author"], "Author1, et al.")

        # Test invalid year
        result = clean_metadata({"author": "Author", "title": "Title", "year": "20XX"})
        self.assertEqual(result["year"], "YYYY")

        # Test future year
        result = clean_metadata({"author": "Author", "title": "Title", "year": "3000"})
        self.assertEqual(result["year"], "YYYY")

    def test_sanitize_filename(self) -> None:
        """Test sanitizing filenames for filesystem compatibility."""
        # Test illegal characters
        result = sanitize_filename('Author: "Title" ? * / \\ | < > (2020).pdf')
        self.assertEqual(result, "Author_ _Title_ _ _ _ _ _ _ (2020).pdf")

        # Test multiple spaces
        result = sanitize_filename("Author  -  Title   (2020).pdf")
        self.assertEqual(result, "Author - Title (2020).pdf")

        # Test very long filename (should be truncated)
        long_title = "A" * 300
        result = sanitize_filename(f"Author - {long_title} (2020).pdf")
        self.assertTrue(len(result) <= 240)

    def test_generate_new_filename(self) -> None:
        """Test generating new filenames based on metadata."""
        result = generate_new_filename(
            {"author": "John Doe", "title": "The Great Book", "year": "2020"}
        )
        self.assertEqual(result, "John Doe - The Great Book (2020).pdf")

        # Test with unknown values
        result = generate_new_filename(
            {"author": "Unknown Author", "title": "Untitled Document", "year": "YYYY"}
        )
        self.assertEqual(result, "Unknown Author - Untitled Document (YYYY).pdf")


if __name__ == "__main__":
    unittest.main()
