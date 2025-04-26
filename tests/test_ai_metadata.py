"""
Tests for the AI metadata enhancement functionality (including async calls).

These tests verify that the AI metadata enhancement functions work correctly.
"""

import json
import unittest
from typing import Dict
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from intellirename.ai import (
    clean_garbled_metadata,
    enhance_metadata,
    evaluate_metadata_quality,
    query_perplexity_async,
)
from intellirename.config import MAX_RETRIES, PERPLEXITY_API_KEY
from intellirename.exceptions import (
    AICommunicationError,
    AIProcessingError,
)


# --- Fixtures for pytest --- (Can replace setUp/tearDown if desired)
@pytest.fixture
def unknown_markers() -> Dict[str, str]:
    """Fixture for unknown metadata markers."""
    return {
        "author": "Unknown_Author",
        "title": "Untitled",
        "year": "0000",
    }


# --- Existing Tests (Can be kept as unittest or refactored to pytest style) ---


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


# --- New Async Tests using pytest --- #


@pytest.mark.asyncio
async def test_query_perplexity_async_success() -> None:
    """Test successful async query to Perplexity API."""
    metadata = {"title": "Partial Title"}
    filename = "partial_title.pdf"
    expected_result = {"author": "Doe, John", "title": "Full Title", "year": "2023"}
    mock_response_content = {  # Mocked JSON response from API
        "choices": [
            {
                "message": {
                    "content": f"```json\n{json.dumps(expected_result)}\n```\nExplanation..."
                }
            }
        ]
    }

    mock_resp = AsyncMock(spec=aiohttp.ClientResponse)
    mock_resp.status = 200
    mock_resp.json = AsyncMock(return_value=mock_response_content)
    mock_resp.text = AsyncMock(return_value=json.dumps(mock_response_content))
    # Mock the context manager methods for 'async with'
    mock_resp.__aenter__.return_value = mock_resp
    mock_resp.__aexit__.return_value = None

    # Fix: session.post should return an object that supports async context manager
    mock_session = AsyncMock(spec=aiohttp.ClientSession)
    mock_session.post.return_value = mock_resp  # Instead of being an AsyncMock itself
    mock_session.__aenter__.return_value = mock_session
    mock_session.__aexit__.return_value = None

    with patch("aiohttp.ClientSession", return_value=mock_session):
        # Patch cache functions to simulate cache miss
        with patch("intellirename.ai.get_from_cache", return_value=None):
            with patch("intellirename.ai.save_to_cache") as mock_save_cache:
                result = await query_perplexity_async(metadata, filename)

                assert result == expected_result  # Check if parsed result matches
                mock_session.post.assert_called_once()
                # Check payload includes Authorization header (optional but good)
                call_args, call_kwargs = mock_session.post.call_args
                assert "Authorization" in call_kwargs["headers"]
                assert (
                    call_kwargs["headers"]["Authorization"]
                    == f"Bearer {PERPLEXITY_API_KEY}"
                )
                mock_save_cache.assert_called_once()  # Ensure result was cached


@pytest.mark.asyncio
async def test_query_perplexity_async_cached() -> None:
    """Test async query uses cache when available."""
    metadata = {"title": "Cached Title"}
    filename = "cached_title.pdf"
    cached_result = {
        "author": "Cache, Hit",
        "title": "Cached Title Full",
        "year": "2024",
    }

    mock_session = AsyncMock(spec=aiohttp.ClientSession)

    with patch("aiohttp.ClientSession", return_value=mock_session):
        with patch(
            "intellirename.ai.get_from_cache", return_value=cached_result
        ) as mock_get_cache:
            with patch("intellirename.ai.save_to_cache") as mock_save_cache:
                with patch(
                    "intellirename.ai.construct_prompt"
                ) as mock_construct_prompt:
                    result = await query_perplexity_async(metadata, filename)

                    assert result == cached_result
                    mock_get_cache.assert_called_once()
                    mock_construct_prompt.assert_not_called()  # Prompt shouldn't be constructed
                    mock_session.post.assert_not_called()  # API shouldn't be called
                    mock_save_cache.assert_not_called()  # Nothing new to save


@pytest.mark.asyncio
@patch("asyncio.sleep", new_callable=AsyncMock)  # Mock sleep to speed up retry tests
async def test_query_perplexity_async_retry_then_success(mock_sleep: AsyncMock) -> None:
    """Test async query retries on server error then succeeds."""
    metadata = {"title": "Retry Title"}
    filename = "retry_title.pdf"
    expected_result = {
        "author": "Retry, Success",
        "title": "Retry Title Full",
        "year": "2025",
    }
    mock_success_response_content = {  # Mocked JSON response from API
        "choices": [
            {
                "message": {
                    "content": f"```json\n{json.dumps(expected_result)}\n```\nExplanation..."
                }
            }
        ]
    }

    # First response: server error
    mock_resp_fail = AsyncMock(spec=aiohttp.ClientResponse)
    mock_resp_fail.status = 500
    mock_resp_fail.message = "Server Error"
    mock_resp_fail.raise_for_status = MagicMock(
        side_effect=aiohttp.ClientResponseError(
            MagicMock(), (), status=500, message="Server Error"
        )
    )
    mock_resp_fail.__aenter__.return_value = mock_resp_fail
    mock_resp_fail.__aexit__.return_value = None

    # Second response: success
    mock_resp_success = AsyncMock(spec=aiohttp.ClientResponse)
    mock_resp_success.status = 200
    mock_resp_success.json = AsyncMock(return_value=mock_success_response_content)
    mock_resp_success.text = AsyncMock(
        return_value=json.dumps(mock_success_response_content)
    )
    mock_resp_success.__aenter__.return_value = mock_resp_success
    mock_resp_success.__aexit__.return_value = None

    # Fix: session.post should return an object that supports async context manager
    mock_session = AsyncMock(spec=aiohttp.ClientSession)
    mock_session.post.side_effect = [mock_resp_fail, mock_resp_success]
    mock_session.__aenter__.return_value = mock_session
    mock_session.__aexit__.return_value = None

    with patch("aiohttp.ClientSession", return_value=mock_session):
        with patch("intellirename.ai.get_from_cache", return_value=None):
            with patch("intellirename.ai.save_to_cache") as mock_save_cache:
                result = await query_perplexity_async(metadata, filename)

                assert result == expected_result
                assert (
                    mock_session.post.call_count == 2
                )  # Called twice (1 fail, 1 success)
                mock_sleep.assert_called_once()  # Should sleep once after failure
                mock_save_cache.assert_called_once()


@pytest.mark.asyncio
@patch("asyncio.sleep", new_callable=AsyncMock)
async def test_query_perplexity_async_retry_limit(mock_sleep: AsyncMock) -> None:
    """Test async query fails after exceeding retry limit."""
    metadata = {"title": "Fail Title"}
    filename = "fail_title.pdf"

    mock_resp_fail = AsyncMock(spec=aiohttp.ClientResponse)
    mock_resp_fail.status = 503
    mock_resp_fail.message = "Service Unavailable"
    mock_resp_fail.raise_for_status = MagicMock(
        side_effect=aiohttp.ClientResponseError(
            MagicMock(), (), status=503, message="Service Unavailable"
        )
    )
    mock_resp_fail.__aenter__.return_value = mock_resp_fail
    mock_resp_fail.__aexit__.return_value = None

    # Make post always return the failing response
    mock_session_post = AsyncMock(return_value=mock_resp_fail)
    mock_session = AsyncMock(spec=aiohttp.ClientSession)
    mock_session.post = mock_session_post
    mock_session.__aenter__.return_value = mock_session
    mock_session.__aexit__.return_value = None

    with patch("aiohttp.ClientSession", return_value=mock_session):
        with patch("intellirename.ai.get_from_cache", return_value=None):
            with patch("intellirename.ai.save_to_cache") as mock_save_cache:
                with pytest.raises(AICommunicationError):
                    await query_perplexity_async(metadata, filename)

                assert mock_session.post.call_count == MAX_RETRIES
                assert mock_sleep.call_count == MAX_RETRIES - 1
                mock_save_cache.assert_not_called()


@pytest.mark.asyncio
async def test_query_perplexity_async_processing_error() -> None:
    """Test async query raises AIProcessingError on bad JSON response."""
    metadata = {"title": "Bad JSON"}
    filename = "bad_json.pdf"

    mock_resp = AsyncMock(spec=aiohttp.ClientResponse)
    mock_resp.status = 200
    mock_resp.text = AsyncMock(return_value="Not valid JSON")
    # Simulate json() failing
    mock_resp.json = AsyncMock(
        side_effect=aiohttp.ContentTypeError(MagicMock(), MagicMock())
    )
    mock_resp.__aenter__.return_value = mock_resp
    mock_resp.__aexit__.return_value = None

    # Fix: session.post should return an object that supports async context manager
    mock_session = AsyncMock(spec=aiohttp.ClientSession)
    mock_session.post.return_value = mock_resp
    mock_session.__aenter__.return_value = mock_session
    mock_session.__aexit__.return_value = None

    with patch("aiohttp.ClientSession", return_value=mock_session):
        with patch("intellirename.ai.get_from_cache", return_value=None):
            with patch("intellirename.ai.save_to_cache") as mock_save_cache:
                with pytest.raises(AIProcessingError, match="Failed to decode JSON"):
                    await query_perplexity_async(metadata, filename)

                mock_save_cache.assert_not_called()


@pytest.mark.asyncio
async def test_enhance_metadata_skips_ai_high_confidence(
    unknown_markers: Dict[str, str],
) -> None:
    """Test enhance_metadata skips AI call if confidence is high."""
    metadata = {"author": "Good, Author", "title": "Good Title", "year": "2020"}
    filename = "good.pdf"

    with patch(
        "intellirename.ai.query_perplexity_async", new_callable=AsyncMock
    ) as mock_query_async:
        result = await enhance_metadata(
            metadata, filename, unknown_markers, confidence_threshold=0.7
        )

        assert result == metadata
        mock_query_async.assert_not_called()


@pytest.mark.asyncio
async def test_enhance_metadata_calls_ai_low_confidence(
    unknown_markers: Dict[str, str],
) -> None:
    """Test enhance_metadata calls AI if confidence is low."""
    metadata = {"author": "Unknown_Author", "title": "Low Conf Title", "year": "0000"}
    filename = "low_conf.pdf"
    enhanced = {"author": "AI, Author", "title": "Low Conf Title Fixed", "year": "2021"}

    with patch("intellirename.ai.validate_perplexity_api_key"):
        with patch(
            "intellirename.ai.query_perplexity_async",
            new_callable=AsyncMock,
            return_value=enhanced,
        ) as mock_query_async:
            result = await enhance_metadata(
                metadata, filename, unknown_markers, confidence_threshold=0.9
            )

            assert result == enhanced
            mock_query_async.assert_called_once_with(metadata, filename)


@pytest.mark.asyncio
async def test_enhance_metadata_raises_ai_error(
    unknown_markers: Dict[str, str],
) -> None:
    """Test enhance_metadata raises AI error if query fails."""
    metadata = {"title": "AI Fail"}
    filename = "ai_fail.pdf"
    error_message = "API Boom"

    with patch("intellirename.ai.validate_perplexity_api_key"):
        with patch(
            "intellirename.ai.query_perplexity_async",
            new_callable=AsyncMock,
            side_effect=AICommunicationError(error_message),
        ) as mock_query_async:
            with pytest.raises(AICommunicationError, match=error_message):
                await enhance_metadata(
                    metadata, filename, unknown_markers, confidence_threshold=0.9
                )

            mock_query_async.assert_called_once()
