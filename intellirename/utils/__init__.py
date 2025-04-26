"""Utility modules for Book & Paper Renamer."""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Dict, Iterable

from pathvalidate import sanitize_filename as pathvalidate_sanitize

from intellirename.constants import ILLEGAL_CHARS, REPLACE_WITH_UNDERSCORE
from intellirename.exceptions import FileOperationError, RenamingError

log = logging.getLogger(__name__)

__all__ = [
    "find_files",
    "make_computer_friendly",
    "sanitize_filename",
    "generate_new_filename",
    "rename_file",
]


def find_files(directory: Path, recursive: bool) -> Iterable[Path]:
    """Yield PDF and EPUB files in *directory*.

    Args:
        directory: Directory to search.
        recursive: Recursively traverse sub-directories when ``True``.

    Yields:
        Path: Absolute path to each discovered file.
    """
    glob_pattern = "**/*" if recursive else "*"
    for item in directory.glob(glob_pattern):
        if item.is_file() and item.suffix.lower() in [".pdf", ".epub"]:
            yield item


def make_computer_friendly(text: str) -> str:
    """Return *text* normalised for safe filesystem usage.

    Replaces characters matched by ``ILLEGAL_CHARS`` or
    ``REPLACE_WITH_UNDERSCORE`` with underscores and collapses consecutive
    underscores.

    Args:
        text: Raw text to sanitise.

    Returns:
        Sanitised string suitable for filenames.
    """
    friendly = re.sub(ILLEGAL_CHARS, "_", text)
    friendly = re.sub(REPLACE_WITH_UNDERSCORE, "_", friendly)
    friendly = re.sub(r"_+", "_", friendly)
    friendly = friendly.strip("_")
    return friendly


def sanitize_filename(filename: str) -> str:
    """Sanitise *filename* for the current platform.

    The *pathvalidate* package performs cross-platform sanitisation and length
    checks.

    Args:
        filename: Filename to sanitise (may include extension).

    Returns:
        Sanitised filename.
    """
    return str(pathvalidate_sanitize(filename, platform="auto", replacement_text="_"))


def generate_new_filename(metadata: Dict[str, str]) -> str:
    """Generate a filename from *metadata*.

    Formats the filename as ``"Author - Title (Year).ext"``. Internal metadata
    values are expected to be *computer-friendly* (underscores instead of
    spaces). They are converted back to display form for the final filename and
    then sanitised.

    Args:
        metadata: Cleaned metadata dictionary.

    Returns:
        Sanitised filename string.
    """
    extension = metadata.get("extension", "pdf")

    author_cf = metadata.get("author", "Unknown_Author")
    title_cf = metadata.get("title", "Untitled")
    year = metadata.get("year", "0000")

    author_display = author_cf.replace("_", " ")
    title_display = title_cf.replace("_", " ")
    year_display = f"({year})" if year != "0000" else ""

    new_name = f"{author_display} - {title_display} {year_display}".strip()
    new_name = f"{new_name}.{extension}"

    return sanitize_filename(new_name)


def rename_file(
    source_path_str: str, new_filename: str, *, dry_run: bool = False
) -> str:
    """Rename the file at *source_path_str* to *new_filename*.

    Handles name collisions by appending an incrementing suffix and supports a
    *dry-run* mode that only reports the proposed change.

    Args:
        source_path_str: Original file path.
        new_filename: Desired filename (not full path).
        dry_run: When ``True`` the filesystem is untouched.

    Returns:
        A human-readable message describing the action taken.

    Raises:
        RenamingError: When too many collisions occur or an OS error is raised.
        FileOperationError: For non-rename related filesystem errors.
    """
    source = Path(source_path_str)
    if not source.is_file():
        raise FileOperationError(f"Source not found or not a file: {source_path_str}")

    target_dir = source.parent
    target_path = target_dir / new_filename  # new_filename is already sanitised

    counter = 1
    target_path_base, target_ext = os.path.splitext(new_filename)
    while target_path.exists() and source.resolve() != target_path.resolve():
        new_name_collided = f"{target_path_base}_{counter}{target_ext}"
        target_path = target_dir / new_name_collided
        counter += 1
        if counter > 100:
            raise RenamingError(f"Too many collisions (>100) for: {new_filename}")

    if source.resolve() == target_path.resolve():
        return f"Skipped renaming '{source.name}', new name is identical."

    final_target_name = target_path.name

    if dry_run:
        return f"[Dry Run] Would rename '{source.name}' to '{final_target_name}'"

    try:
        source.rename(target_path)
        log.info("Successfully renamed '%s' to '%s'", source.name, final_target_name)
        return f"Renamed '{source.name}' to '{final_target_name}'"
    except OSError as exc:
        raise RenamingError(
            f"OS error renaming '{source.name}' to '{final_target_name}'",
            original_exception=exc,
        ) from exc
    except Exception as exc:
        raise FileOperationError(
            f"Unexpected error renaming '{source.name}'", original_exception=exc
        ) from exc
