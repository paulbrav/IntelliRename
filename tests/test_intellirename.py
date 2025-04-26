"""Test cases for the PDF Renamer tool."""

import os
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

# from pathlib import Path
from intellirename.main import (
    UNKNOWN_AUTHOR,
    UNKNOWN_TITLE,
    UNKNOWN_YEAR,
    clean_metadata,
    extract_from_epub,
    extract_from_filename,
    extract_from_pdf,
    generate_new_filename,
    merge_metadata,
    process_file,
    sanitize_filename,
)
from intellirename.main import (
    main as intellirename_main,
)


# Mock the AI functions as they require API keys/network
@patch("intellirename.main.AI_AVAILABLE", True)
@patch("intellirename.main.validate_perplexity_api_key", return_value=True)
@patch(
    "intellirename.main.is_ai_enhancement_needed", return_value=False
)  # Default to no AI needed for tests
@patch(
    "intellirename.main.correct_metadata_with_ai", side_effect=lambda d, fn, ct: d
)  # AI returns original data
class TestIntelliRename(unittest.TestCase):
    def test_extract_from_filename_author_title_year(
        self, *_: Any
    ) -> None:  # Accept mock args
        filename = "Author Name - Book Title (2023).pdf"
        expected = {
            "author": "Author Name",
            "title": "Book Title",
            "year": "2023",
            "extension": "pdf",
        }
        self.assertEqual(extract_from_filename(filename), expected)

    def test_extract_from_filename_title_year(self, *_: Any) -> None:
        filename = "Just A Title (1999).epub"
        expected = {
            "author": UNKNOWN_AUTHOR,
            "title": "Just A Title",
            "year": "1999",
            "extension": "epub",
        }
        self.assertEqual(extract_from_filename(filename), expected)

    def test_extract_from_filename_author_title(self, *_: Any) -> None:
        filename = "Another Author - Another Title.pdf"
        expected = {
            "author": "Another Author",
            "title": "Another Title",
            "year": UNKNOWN_YEAR,
            "extension": "pdf",
        }
        self.assertEqual(extract_from_filename(filename), expected)

    def test_extract_from_filename_no_match(self, *_: Any) -> None:
        filename = "completely_unstructured_filename.pdf"
        expected = {
            "author": UNKNOWN_AUTHOR,
            "title": "completely_unstructured_filename",
            "year": UNKNOWN_YEAR,
            "extension": "pdf",
        }
        self.assertEqual(extract_from_filename(filename), expected)

    def test_clean_metadata(self, *_: Any) -> None:
        raw = {
            "author": "  Author, A. B.  ",
            "title": " Title: with; illegal? chars* ",
            "year": " 2020 ",
        }
        expected = {
            "author": "Author, A. B.",
            "title": "Title with illegal chars",
            "year": "2020",
        }
        self.assertEqual(clean_metadata(raw), expected)

    def test_generate_filename(self, *_: Any) -> None:
        metadata = {
            "author": "Author, A. B.",
            "title": "A Great Title",
            "year": "2021",
            "extension": "epub",
        }
        expected = "Author_A_B_A_Great_Title_2021.epub"
        self.assertEqual(generate_new_filename(metadata), expected)

    def test_generate_filename_unknowns(self, *_: Any) -> None:
        metadata = {
            "author": UNKNOWN_AUTHOR,
            "title": "Some Title",
            "year": UNKNOWN_YEAR,
            "extension": "pdf",
        }
        expected = "Unknown_Author_Some_Title_0000.pdf"
        self.assertEqual(generate_new_filename(metadata), expected)

    # Test process_file with mocking
    @patch("intellirename.main.extract_from_filename")
    @patch("intellirename.main.extract_from_pdf")
    @patch("intellirename.main.extract_from_epub")
    @patch("intellirename.main.extract_all_metadata")  # Mock advanced extraction
    @patch("intellirename.main.os.rename")
    @patch(
        "intellirename.main.Path.exists", return_value=False
    )  # Assume new filename doesn't exist
    def test_process_file_basic_pdf(
        self,
        mock_exists: MagicMock,
        mock_rename: MagicMock,
        mock_extract_all: MagicMock,
        mock_extract_epub: MagicMock,
        mock_extract_pdf: MagicMock,
        mock_extract_filename: MagicMock,
        *_: Any,
    ) -> None:
        mock_extract_filename.return_value = {
            "author": "Test Author",
            "title": "Test Title",
            "year": "2022",
            "extension": "pdf",
        }
        mock_extract_pdf.return_value = {
            "author": "PDF Author",
            "title": "PDF Title",
            "year": "2021",
        }  # Content data
        mock_extract_epub.return_value = {}
        mock_extract_all.return_value = {}  # No advanced data

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_file:
            file_path = tmp_file.name
            base_name = Path(file_path).name

        result = process_file(
            file_path, dry_run=False, use_advanced=False, use_ai=False
        )

        expected_filename = (
            "Test_Author_Test_Title_2022.pdf"  # Filename data prioritized
        )
        expected_new_path = str(Path(file_path).parent / expected_filename)

        mock_extract_filename.assert_called_once_with(base_name)
        mock_extract_pdf.assert_called_once_with(file_path)
        mock_extract_epub.assert_not_called()
        mock_rename.assert_called_once_with(file_path, expected_new_path)
        self.assertEqual(result["status"], "renamed")
        self.assertEqual(result["new_filename"], expected_filename)

        os.remove(file_path)  # Clean up temp file

    # Test process_file with dry run
    @patch("intellirename.main.extract_from_filename")
    @patch("intellirename.main.os.rename")
    def test_process_file_dry_run(
        self, mock_rename: MagicMock, mock_extract_filename: MagicMock, *_: Any
    ) -> None:
        mock_extract_filename.return_value = {
            "author": "DryRun Author",
            "title": "DryRun Title",
            "year": "2024",
            "extension": "pdf",
        }

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_file:
            file_path = tmp_file.name
            base_name = Path(file_path).name

        result = process_file(file_path, dry_run=True, use_advanced=False, use_ai=False)

        expected_filename = "DryRun_Author_DryRun_Title_2024.pdf"

        mock_rename.assert_not_called()
        self.assertEqual(result["status"], "skipped (dry run)")
        self.assertEqual(result["new_filename"], expected_filename)

        os.remove(file_path)  # Clean up temp file

    # Add more tests for EPUB, AI enhancement, error cases, edge cases etc.


if __name__ == "__main__":
    unittest.main()
