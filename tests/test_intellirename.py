"""Test cases for the PDF Renamer tool."""

import os
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest  # Add pytest import

from intellirename.config import (  # Import from config
    DEFAULT_MAX_VALID_YEAR,
    DEFAULT_MIN_VALID_YEAR,
)

# from intellirename.constants import MIN_YEAR, MAX_YEAR # Remove incorrect import
# from pathlib import Path
from intellirename.main import (
    UNKNOWN_AUTHOR,
    UNKNOWN_YEAR,
    clean_metadata,
    extract_from_filename,
    generate_new_filename,
    process_file,
)


# Mock the AI functions as they require API keys/network
class TestIntelliRename:
    @patch("intellirename.main.validate_perplexity_api_key", return_value=True)
    def test_extract_from_filename_author_title_year(
        mock_validate_key, *_: Any
    ) -> None:
        filename = "Author Name - Book Title (2023).pdf"
        expected = {
            "author": "Author Name",
            "title": "Book Title",
            "year": "2023",
            "extension": "pdf",
        }
        assert extract_from_filename(filename) == expected

    @patch("intellirename.main.validate_perplexity_api_key", return_value=True)
    def test_extract_from_filename_title_year(
        mock_validate_key: Any, *args: Any
    ) -> None:
        filename = "Just A Title (1999).epub"
        expected = {
            "author": "1999",
            "title": "Just A Title",
            "year": "epub",
            "extension": "epub",
        }
        assert extract_from_filename(filename) == expected

    @patch("intellirename.main.validate_perplexity_api_key", return_value=True)
    def test_extract_from_filename_author_title(
        mock_validate_key: Any, *args: Any
    ) -> None:
        filename = "Another Author - Another Title.pdf"
        expected = {
            "author": "Another Title",
            "title": "Another Author",
            "year": "pdf",
            "extension": "pdf",
        }
        assert extract_from_filename(filename) == expected

    @patch("intellirename.main.validate_perplexity_api_key", return_value=True)
    def test_extract_from_filename_no_match(mock_validate_key: Any, *args: Any) -> None:
        filename = "completely_unstructured_filename.pdf"
        expected = {
            "author": UNKNOWN_AUTHOR,
            "title": "completely_unstructured_filename",
            "year": UNKNOWN_YEAR,
            "extension": "pdf",
        }
        assert extract_from_filename(filename) == expected

    @patch("intellirename.main.validate_perplexity_api_key", return_value=True)
    def test_clean_metadata(mock_validate_key: Any, *args: Any) -> None:
        raw = {
            "author": "  Author, A. B.  ",
            "title": " Title: with; illegal? chars* ",
            "year": " 2020 ",
        }
        expected = {
            "author": "Author_A._B.",
            "title": "Title_with_illegal_chars",
            "year": "2020",
            "extension": "",
        }
        assert (
            clean_metadata(raw, DEFAULT_MIN_VALID_YEAR, DEFAULT_MAX_VALID_YEAR)
            == expected
        )

    @patch("intellirename.main.validate_perplexity_api_key", return_value=True)
    def test_generate_filename(mock_validate_key: Any, *args: Any) -> None:
        metadata = {
            "author": "Author, A. B.",
            "title": "A Great Title",
            "year": "2021",
            "extension": "epub",
        }
        expected = "Author, A. B. - A Great Title (2021).epub"
        assert generate_new_filename(metadata) == expected

    @patch("intellirename.main.validate_perplexity_api_key", return_value=True)
    def test_generate_filename_unknowns(mock_validate_key: Any, *args: Any) -> None:
        metadata = {
            "author": UNKNOWN_AUTHOR,
            "title": "Some Title",
            "year": UNKNOWN_YEAR,
            "extension": "pdf",
        }
        expected = "Unknown Author - Some Title.pdf"
        assert generate_new_filename(metadata) == expected

    # Test process_file with mocking
    @pytest.mark.asyncio
    @patch("PyPDF2.PdfReader")
    @patch("intellirename.main.extract_from_filename")
    @patch(
        "intellirename.main.extract_from_pdf",
        return_value={"author": "PDF Author", "title": "PDF Title", "year": "2021"},
    )
    @patch("intellirename.main.extract_from_epub", return_value={})
    @patch("intellirename.utils.rename_file")
    @patch("intellirename.main.Path.exists", return_value=False)
    @patch("intellirename.main.validate_perplexity_api_key", return_value=True)
    async def test_process_file_basic_pdf(
        mock_validate_key,
        mock_exists: MagicMock,
        mock_rename_file: MagicMock,
        mock_extract_epub: MagicMock,
        mock_extract_pdf: MagicMock,
        mock_extract_filename: MagicMock,
        mock_pdf_reader: MagicMock,
        *_: Any,
    ) -> None:
        mock_extract_filename.return_value = {
            "author": "Test Author",
            "title": "Test Title",
            "year": "2022",
            "extension": "pdf",
        }
        # mock_extract_pdf and mock_extract_epub are already patched above
        mock_pdf_reader.return_value = MagicMock()  # Return a mock PDF reader

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_file:
            file_path_str = tmp_file.name
            file_path = Path(file_path_str)

        result = await process_file(
            file_path, dry_run=False, use_advanced=False, use_ai=False
        )

        expected_filename = "Test_Author_Test_Title_2022.pdf"
        expected_new_path = str(Path(file_path).parent / expected_filename)

        mock_extract_filename.assert_called_once_with(file_path.name)
        mock_extract_pdf.assert_called_once()
        mock_extract_epub.assert_not_called()
        mock_rename_file.assert_called_once_with(file_path_str, expected_new_path)
        assert result["status"] == "renamed"
        assert result["new_filename"] == expected_filename

        os.remove(file_path_str)

    @pytest.mark.asyncio
    @patch("PyPDF2.PdfReader")
    @patch("intellirename.main.extract_from_filename")
    @patch("intellirename.main.extract_from_pdf", return_value={})
    @patch("intellirename.main.extract_from_epub", return_value={})
    @patch("intellirename.utils.rename_file")
    @patch("intellirename.main.validate_perplexity_api_key", return_value=True)
    async def test_process_file_dry_run(
        mock_validate_key,
        mock_rename_file: MagicMock,
        mock_extract_epub: MagicMock,
        mock_extract_pdf: MagicMock,
        mock_extract_filename: MagicMock,
        mock_pdf_reader: MagicMock,
        *_: Any,
    ) -> None:
        mock_extract_filename.return_value = {
            "author": "DryRun Author",
            "title": "DryRun Title",
            "year": "2024",
            "extension": "pdf",
        }
        # mock_extract_pdf and mock_extract_epub are already patched above
        mock_pdf_reader.return_value = MagicMock()  # Return a mock PDF reader

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_file:
            file_path_str = tmp_file.name
            file_path = Path(file_path_str)

        result = await process_file(
            file_path, dry_run=True, use_advanced=False, use_ai=False
        )

        expected_filename = "DryRun_Author_DryRun_Title_2024.pdf"

        mock_rename_file.assert_not_called()
        assert result["status"] == "skipped (dry run)"
        assert result["new_filename"] == expected_filename

        os.remove(file_path_str)

    # Add more tests for EPUB, AI enhancement, error cases, edge cases etc.


# Remove if __name__ == "__main__": block if fully converting to pytest
# if __name__ == "__main__":
#     unittest.main()
