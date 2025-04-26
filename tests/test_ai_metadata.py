"""
Tests for the AI metadata enhancement functionality.

These tests verify that the AI metadata enhancement functions work correctly.
"""

import os
import unittest
from typing import Dict
from unittest.mock import MagicMock, patch

from intellirename.utils.ai_metadata import (
    clean_garbled_metadata,
    evaluate_metadata_quality,
    validate_perplexity_api_key,
)


class TestMetadataQuality(unittest.TestCase):
    """Test the metadata quality evaluation functionality."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.unknown_markers = {
            "author": "Unknown_Author",
            "title": "Untitled",
            "year": "0000",
        }

    def test_evaluate_empty_metadata(self) -> None:
        """Test that empty metadata gets a low quality score."""
        metadata: Dict[str, str] = {}
        score, field_scores = evaluate_metadata_quality(metadata, self.unknown_markers)
        self.assertLessEqual(score, 0.2)

    def test_evaluate_complete_good_metadata(self) -> None:
        """Test that good metadata gets a high quality score."""
        metadata = {"author": "John_Smith", "title": "The_Great_Book", "year": "2022"}
        score, field_scores = evaluate_metadata_quality(metadata, self.unknown_markers)
        self.assertGreaterEqual(score, 0.7)

    def test_evaluate_garbled_metadata(self) -> None:
        """Test that garbled metadata gets a medium quality score."""
        metadata = {
            "author": "S_or_Dargo",  # Garbled "Sandor Dargo"
            "title": "Daily_C++_Interview",
            "year": "2023",
        }
        score, field_scores = evaluate_metadata_quality(metadata, self.unknown_markers)
        self.assertLess(score, 0.7)
        self.assertGreater(score, 0.3)


class TestMetadataCleaning(unittest.TestCase):
    """Test the metadata cleaning functionality."""

    def test_clean_garbled_author(self) -> None:
        """Test cleaning garbled author names."""
        metadata = {
            "author": "S_or_Dargo",  # Garbled "Sandor Dargo"
            "title": "Daily_C++_Interview",
            "year": "2023",
        }
        cleaned = clean_garbled_metadata(metadata)
        self.assertEqual(cleaned["author"], "Sandor_Dargo")

    def test_clean_title_with_artifacts(self) -> None:
        """Test cleaning titles with artifacts."""
        metadata = {"author": "John_Smith", "title": "Great_Book_(PDF)", "year": "2022"}
        cleaned = clean_garbled_metadata(metadata)
        self.assertEqual(cleaned["title"], "Great_Book")

    def test_clean_multiple_underscores(self) -> None:
        """Test cleaning multiple underscores."""
        metadata = {"author": "John__Smith", "title": "Great___Book", "year": "2022"}
        cleaned = clean_garbled_metadata(metadata)
        self.assertEqual(cleaned["author"], "John_Smith")
        self.assertEqual(cleaned["title"], "Great_Book")


if __name__ == "__main__":
    unittest.main()
