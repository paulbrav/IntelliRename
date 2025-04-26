#!/usr/bin/env python3
"""
Rename book and paper files (PDF, EPUB) with accurate metadata.

This script processes book and academic paper files, extracts metadata (Author, Title, Year)
from filenames and content, cleans garbled metadata, and renames files to a standardized format.
Uses AI and web search capabilities to enhance metadata quality when needed.
"""

import argparse
import asyncio
import logging
import re
import sys
import time
from pathlib import Path
from typing import Any, Awaitable, Dict, List, Optional, Tuple, Union

# Third-party imports
import PyPDF2
from PyPDF2.errors import PyPdfError
from rich.console import Console
from rich.logging import RichHandler
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)

# Local application imports
from . import config
from .ai import (
    # AI_AVAILABLE, # Removed - Check is implicit in import success
    enhance_metadata,
    validate_perplexity_api_key,
)
from .constants import (
    UNKNOWN_AUTHOR,
    UNKNOWN_TITLE,
    UNKNOWN_YEAR,
)
from .exceptions import (
    AICommunicationError,
    AIProcessingError,
    ConfigurationError,
    FileOperationError,
    IntelliRenameError,
    MetadataExtractionError,
)
from .metadata import (
    clean_metadata,
    extract_advanced_metadata,
    extract_from_epub,
    extract_from_filename,
    extract_from_pdf,
    merge_metadata,
)
from .utils import (
    find_files,
    generate_new_filename,
    rename_file,
)

# Filename parsing patterns
FILENAME_PATTERNS = [
    # "[Publisher] Author(s) - Title (Year, Publisher).pdf"
    re.compile(
        r"^\[.*?\]\s*(.+?)\s*-\s*(.+?)\s*\((\d{4}).*?\)\.(pdf|epub)$", re.IGNORECASE
    ),
    # "Author(s) - Title (Year).pdf"
    re.compile(r"^(.+?)\s*-\s*(.+?)\s*\((\d{4}).*?\)\.(pdf|epub)$", re.IGNORECASE),
    # "Title - Author(s) (Year).pdf"
    re.compile(r"^(.+?)\s*-\s*(.+?)\s*\((\d{4}).*?\)\.(pdf|epub)$", re.IGNORECASE),
    # "Title (Year).pdf"
    re.compile(r"^(.+?)\s*\((\d{4}).*?\)\.(pdf|epub)$", re.IGNORECASE),
    # "Author(s) - Title.pdf"
    re.compile(r"^(.+?)\s*-\s*(.+?)\.(pdf|epub)$", re.IGNORECASE),
]

# Configure logging with rich
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(rich_tracebacks=True)],
)
log = logging.getLogger("book_renamer")
console = Console()

# Load configuration early (consider moving if setup_logging needs config values)
try:
    config.load_config()
except ConfigurationError as e:
    # Use basic print for early config errors before Rich is setup
    print(f"Fatal Configuration Error: {e}", file=sys.stderr)
    sys.exit(1)


def setup_logging(level: str = "INFO") -> None:
    """Configure logging using RichHandler.

    Args:
        level (str): Logging level (e.g., "INFO", "DEBUG").
    """
    log_level = getattr(logging, level.upper(), logging.INFO)
    # Get the root logger or a specific one
    # Using root logger ensures libraries also use this config if they don't set their own
    # logger = logging.getLogger("intellirename")
    logger = logging.getLogger()  # Get root logger
    logger.setLevel(log_level)

    # Remove existing handlers to avoid duplicate messages
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

    # Add RichHandler
    rich_handler = RichHandler(
        rich_tracebacks=True,
        tracebacks_show_locals=True,  # Optional: show locals in tracebacks
        markup=True,
    )
    logger.addHandler(rich_handler)

    # Optional: Adjust logging level for specific libraries
    # logging.getLogger("PyPDF2").setLevel(logging.WARNING)

    log = logging.getLogger(__name__)  # Get logger for this module after setup
    log.debug("Logging setup complete.")


# --- Helper Functions for process_file ---


def _extract_initial_metadata(
    file_path: Path, use_advanced: bool
) -> Tuple[Dict[str, Any], Optional[PyPDF2.PdfReader]]:
    """Extract initial metadata from filename and content (PDF/EPUB).

    Args:
        file_path (Path): Path to the file.
        use_advanced (bool): Whether to use advanced PDF metadata extraction.

    Returns:
        Tuple[Dict[str, Any], Optional[PyPDF2.PdfReader]]: Merged metadata and PDF reader object (if PDF).

    Raises:
        MetadataExtractionError: If metadata extraction fails.
        FileNotFoundError: If the file does not exist.
        IOError: If there is an error opening the file.
    """
    original_filename = file_path.name
    file_suffix = file_path.suffix.lower()
    pdf_reader = None

    # Step 1: Extract from filename
    filename_data = extract_from_filename(original_filename)

    # Step 2 & 3: Extract from content (PDF/EPUB)
    content_data: Dict[str, Any] = {}
    advanced_data: Dict[str, Any] = {}

    if file_suffix == ".pdf":
        try:
            # Keep the file open and pass the reader object
            pdf_file = open(file_path, "rb")  # Keep file open for potential later use
            pdf_reader = PyPDF2.PdfReader(pdf_file)

            content_data = extract_from_pdf(pdf_reader, str(file_path))
            if use_advanced:
                advanced_data = extract_advanced_metadata(pdf_reader, str(file_path))

        except PyPdfError as e:
            log.error(f"Failed to read PDF structure for {original_filename}: {e}")
            if pdf_reader and hasattr(pdf_reader.stream, "close"):
                pdf_reader.stream.close()
            raise MetadataExtractionError(
                f"Invalid or corrupt PDF: {original_filename}", e
            ) from e
        except (IOError, OSError) as e:
            log.error(f"IO error opening PDF {original_filename}: {e}")
            if pdf_reader and hasattr(pdf_reader.stream, "close"):
                pdf_reader.stream.close()
            raise MetadataExtractionError(
                f"Cannot open PDF: {original_filename}", e
            ) from e
        except Exception as e:
            log.exception(
                f"Unexpected error during PDF metadata extraction for {original_filename}"
            )
            if pdf_reader and hasattr(pdf_reader.stream, "close"):
                pdf_reader.stream.close()
            raise MetadataExtractionError(
                f"PDF metadata error: {original_filename}", e
            ) from e

    elif file_suffix == ".epub":
        try:
            content_data = extract_from_epub(str(file_path))
        except MetadataExtractionError as e:
            log.warning(f"EPUB metadata extraction failed for {original_filename}: {e}")
            # Proceed with potentially empty content_data

    # Step 4: Merge
    merged_data = merge_metadata(filename_data, content_data, advanced_data)
    merged_data["original_filename"] = original_filename

    return merged_data, pdf_reader


async def _conditionally_enhance_metadata(
    metadata: Dict[str, Any],
    file_path: Path,
    use_ai: bool,
    confidence_threshold: float,
    min_year: int,
    max_year: int,
) -> Dict[str, Any]:
    """Clean metadata and optionally enhance it using AI if conditions are met.

    Args:
        metadata (Dict[str, Any]): The initial merged metadata.
        file_path (Path): The path to the file (for logging/AI context).
        use_ai (bool): Flag indicating if AI enhancement is enabled.
        confidence_threshold (float): Threshold to trigger AI enhancement.
        min_year (int): Minimum valid year for cleaning.
        max_year (int): Maximum valid year for cleaning.

    Returns:
        Dict[str, Any]: The cleaned and potentially AI-enhanced metadata.

    Raises:
        ConfigurationError: If AI is requested but not configured.
        AICommunicationError: If there's an error communicating with the AI API.
        AIProcessingError: If there's an error processing the AI response.
    """
    cleaned_data = clean_metadata(
        metadata,
        min_year=min_year,
        max_year=max_year,
    )

    if use_ai:
        # Validate API key availability *before* attempting AI enhancement
        try:
            validate_perplexity_api_key()
        except ConfigurationError as e:
            log.error(f"AI enhancement skipped for {file_path.name}: {e}")
            # Return cleaned data without AI enhancement if key is missing/invalid
            # Or re-raise if strict AI usage is required? Re-raising for now.
            raise

        # Evaluate quality and decide if AI enhancement is needed
        # Note: unknown_markers are now centralized in constants.py
        unknown_markers = {
            "author": UNKNOWN_AUTHOR,
            "title": UNKNOWN_TITLE,
            "year": UNKNOWN_YEAR,
        }
        try:
            from intellirename.ai import evaluate_metadata_quality  # Defer import

            quality_score, _ = evaluate_metadata_quality(cleaned_data, unknown_markers)
            log.debug(
                f"Metadata quality score for {file_path.name}: {quality_score:.2f}"
            )

            if quality_score < confidence_threshold:
                log.info(
                    f"Low metadata quality ({quality_score:.2f} < {confidence_threshold}) for "
                    f"'{file_path.name}'. Attempting AI enhancement."
                )
                enhanced_data = await enhance_metadata(
                    cleaned_data,
                    file_path.name,
                    unknown_markers=unknown_markers,
                    confidence_threshold=confidence_threshold,  # Pass threshold for context if needed
                )
                # Re-clean after enhancement to ensure consistency
                cleaned_data = clean_metadata(
                    enhanced_data, min_year=min_year, max_year=max_year
                )
                cleaned_data["ai_enhanced"] = str(
                    True
                )  # Mark as enhanced (Store as string)
            else:
                log.debug(
                    f"Metadata quality sufficient ({quality_score:.2f} >= {confidence_threshold}) "
                    f"for '{file_path.name}'. Skipping AI enhancement."
                )
                cleaned_data["ai_enhanced"] = str(False)  # Store as string

        except (AICommunicationError, AIProcessingError) as e:
            log.error(f"AI enhancement failed for {file_path.name}: {e}")
            # Decide whether to proceed with cleaned_data or raise. Raising for now.
            raise
        except ImportError:
            log.error(
                "AI features requested, but 'evaluate_metadata_quality' unavailable."
            )
            raise ConfigurationError("AI features seem incorrectly installed.")
        except Exception as e:
            log.exception(
                f"Unexpected error during AI enhancement check for {file_path.name}"
            )
            # Raise a more generic error or handle appropriately
            raise IntelliRenameError(f"Unexpected AI check error: {e}") from e

    return cleaned_data


def _generate_target_path(metadata: Dict[str, Any], file_path: Path) -> Optional[Path]:
    """Generate the proposed new path for the file based on metadata.

    Args:
        metadata (Dict[str, Any]): The final metadata for the file.
        file_path (Path): The original path of the file.

    Returns:
        Optional[Path]: The proposed new Path object, or None if renaming is not needed.
    """
    # Check if metadata is sufficient for renaming
    if metadata["author"] == UNKNOWN_AUTHOR and metadata["title"] == UNKNOWN_TITLE:
        log.warning(
            f"Skipping rename for {file_path.name}: Insufficient metadata "
            f"(Author and Title are unknown)."
        )
        return None

    # Step 6: Generate new filename based on cleaned/enhanced metadata
    new_filename_base_plus_ext = generate_new_filename(metadata)
    # generate_new_filename now includes sanitization and extension
    # We just need the parent dir
    proposed_new_path = file_path.parent / new_filename_base_plus_ext

    # Check if rename is actually needed
    if proposed_new_path == file_path:
        log.info(f"Skipping rename for {file_path.name}: Filename is already correct.")
        return None

    return proposed_new_path


def _perform_rename_operation(
    original_path: Path, proposed_new_path: Path, dry_run: bool
) -> Tuple[str, str]:
    """Perform the file renaming operation or simulate it (dry run).

    Args:
        original_path (Path): The original file path.
        proposed_new_path (Path): The target file path.
        dry_run (bool): If True, simulate instead of actually renaming.

    Returns:
        Tuple[str, str]: A tuple containing the status ("renamed" or "dryrun")
                         and a descriptive message.

    Raises:
        FileOperationError: If the renaming fails.
    """
    if dry_run:
        message = f"[DRY RUN] Would rename '{original_path.name}' to '{proposed_new_path.name}'"
        log.info(message)
        return "dryrun", message
    else:
        try:
            rename_file(
                str(original_path), str(proposed_new_path)
            )  # Convert Path to str
            message = f"Renamed '{original_path.name}' to '{proposed_new_path.name}'"
            log.info(message)
            return "renamed", message
        except FileOperationError as e:
            log.error(f"Failed to rename {original_path.name}: {e}")
            # Let the exception propagate up to be caught by the main processing loop
            raise


async def process_file(
    file_path: Path,
    dry_run: bool = False,
    use_advanced: bool = True,
    use_ai: bool = False,
    confidence_threshold: float = config.DEFAULT_CONFIDENCE_THRESHOLD,
    min_year: int = config.DEFAULT_MIN_VALID_YEAR,
    max_year: int = config.DEFAULT_MAX_VALID_YEAR,
) -> Dict[str, Any]:
    """Processes a single file asynchronously: extracts, cleans, optionally enhances, renames.

    Args:
        file_path (Path): The path to the file to process.
        dry_run (bool): If True, only print proposed changes, don't rename.
        use_advanced (bool): Whether to use advanced PDF metadata extraction.
        use_ai (bool): Whether to use AI-powered metadata enhancement.
        confidence_threshold (float): Confidence threshold for using AI enhancement.
        min_year (int): Minimum valid publication year from config.
        max_year (int): Maximum valid publication year from config.

    Returns:
        Dict[str, Any]: Dictionary with processing results:
            - "original_path": Path
            - "new_path": Optional[Path]
            - "status": str ("skipped", "renamed", "dryrun", "error", "no_change")
            - "message": str
            - "metadata": Dict[str, Any] (final metadata used)
            - "error_details": Optional[str] (exception message if status is "error")
    """
    result: Dict[str, Any] = {
        "original_path": file_path,
        "new_path": None,
        "status": "pending",
        "message": "",
        "metadata": {},
        "error_details": None,
    }
    pdf_reader: Optional[PyPDF2.PdfReader] = None

    try:
        # Validate file type
        if file_path.suffix.lower() not in [".pdf", ".epub"]:
            result["status"] = "skipped"
            result["message"] = f"Skipped '{file_path.name}' - not a PDF or EPUB file"
            return result

        # --- Extraction ---
        merged_data, pdf_reader = _extract_initial_metadata(file_path, use_advanced)
        result["metadata"] = merged_data  # Store initial metadata

        # --- Cleaning & Optional AI Enhancement ---
        final_metadata = await _conditionally_enhance_metadata(
            merged_data,
            file_path,
            use_ai,
            confidence_threshold,
            min_year,
            max_year,
        )
        result["metadata"] = final_metadata  # Update with final metadata

        # --- Filename Generation ---
        proposed_new_path = _generate_target_path(final_metadata, file_path)

        if proposed_new_path is None:
            # This means renaming wasn't needed (insufficient metadata or already correct)
            result["status"] = "no_change"
            # Message might be set by _generate_target_path if insufficient
            if not result["message"]:
                result["message"] = (
                    f"Skipped '{file_path.name}': Filename already correct or insufficient metadata."
                )
            return result

        result["new_path"] = proposed_new_path

        # --- Renaming Operation ---
        status, message = _perform_rename_operation(
            file_path, proposed_new_path, dry_run
        )
        result["status"] = status
        result["message"] = message

    except IntelliRenameError as e:  # Catch specific app errors
        log.error(f"Error processing {file_path.name}: {e}")
        result["status"] = "error"
        result["message"] = f"Failed processing {file_path.name}"
        result["error_details"] = str(e)
    except Exception as e:  # Catch unexpected errors
        log.exception(f"Unexpected error processing {file_path.name}")
        result["status"] = "error"
        result["message"] = f"Unexpected failure processing {file_path.name}"
        result["error_details"] = str(e)
    finally:
        # Ensure the PDF file handle is closed if it was opened
        if pdf_reader and hasattr(pdf_reader.stream, "close"):
            try:
                pdf_reader.stream.close()
            except Exception as close_err:
                log.warning(
                    f"Error closing PDF file handle for {file_path.name}: {close_err}"
                )

    return result


# --- Helper Functions for main ---


def _find_files_to_process(
    input_paths: List[Union[str, Path]], recursive: bool
) -> List[Path]:
    """Find all PDF and EPUB files in the specified paths.

    Args:
        input_paths (List[Union[str, Path]]): List of directories or files.
        recursive (bool): Whether to search directories recursively.

    Returns:
        List[Path]: List of found file Paths.
    """
    log.info("Scanning for PDF and EPUB files...")
    all_files_list: List[Path] = []
    for input_path_arg in input_paths:
        input_path = Path(input_path_arg)  # Ensure it's a Path object
        if input_path.is_dir():
            # find_files returns a generator, convert to list
            found_in_dir = list(find_files(input_path, recursive=recursive))
            log.debug(f"Found {len(found_in_dir)} files in directory: {input_path}")
            all_files_list.extend(found_in_dir)
        elif input_path.is_file() and input_path.suffix.lower() in [".pdf", ".epub"]:
            log.debug(f"Adding single file: {input_path}")
            all_files_list.append(input_path)
        else:
            log.warning(f"Skipping invalid input path: {input_path}")

    # Remove duplicates that might occur if a file is specified directly AND is in a searched dir
    unique_files = list(set(all_files_list))

    if not unique_files:
        log.warning("No PDF or EPUB files found in the specified paths.")
        return []
    log.info(f"Found {len(unique_files)} unique files to process.")
    return unique_files


async def _run_processing_tasks(
    files: List[Path],
    dry_run: bool,
    use_advanced: bool,
    use_ai: bool,
    confidence: float,
    min_year: int,
    max_year: int,
    max_concurrent: int,
) -> List[Dict[str, Any]]:
    """Run the file processing tasks concurrently using asyncio.

    Args:
        files (List[Path]): List of files to process.
        dry_run (bool): Dry run flag.
        use_advanced (bool): Use advanced extraction flag.
        use_ai (bool): Use AI enhancement flag.
        confidence (float): AI confidence threshold.
        min_year (int): Min valid year.
        max_year (int): Max valid year.
        max_concurrent (int): Maximum number of concurrent tasks.

    Returns:
        List[Dict[str, Any]]: List of result dictionaries from process_file.
    """
    results = []
    semaphore = asyncio.Semaphore(max_concurrent)  # Limit concurrency

    async def process_with_semaphore(file_path: Path) -> Dict[str, Any]:
        async with semaphore:
            # Await the actual processing function
            return await process_file(
                file_path,
                dry_run=dry_run,
                use_advanced=use_advanced,
                use_ai=use_ai,
                confidence_threshold=confidence,
                min_year=min_year,
                max_year=max_year,
            )

    # Setup Rich Progress Bar
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        console=console,
        transient=True,  # Clear progress bar on exit
    ) as progress:
        task_id = progress.add_task("Processing files...", total=len(files))
        tasks = [process_with_semaphore(f) for f in files]

        # Gather results as they complete, updating progress
        for future in asyncio.as_completed(tasks):
            try:
                result = await future
                results.append(result)
            except Exception as e:
                # This catches errors *raised* by process_file (or semaphore issues)
                # We should ideally log this, but the result dict format handles errors too
                log.error(f"Task failed unexpectedly: {e}")
                # We might need a way to associate this error back to a file if possible
                # For now, append a generic error result if needed, though process_file handles it
                results.append(
                    {
                        "original_path": None,  # Cannot determine path if task fails externally
                        "new_path": None,
                        "status": "error",
                        "message": "Task execution failed.",
                        "metadata": {},
                        "error_details": str(e),
                    }
                )
            finally:
                progress.update(
                    task_id, advance=1
                )  # Update progress regardless of outcome

    return results


def _print_processing_summary(results: List[Dict[str, Any]], start_time: float) -> int:
    """Print a summary of the processing results.

    Args:
        results (List[Dict[str, Any]]): List of result dictionaries.
        start_time (float): The start time of the processing.

    Returns:
        int: Exit code (0 for success, 1 for errors).
    """
    end_time = time.time()
    total_time = end_time - start_time

    renamed_count = sum(1 for r in results if r["status"] == "renamed")
    dryrun_count = sum(1 for r in results if r["status"] == "dryrun")
    skipped_count = sum(1 for r in results if r["status"] == "skipped")
    nochange_count = sum(1 for r in results if r["status"] == "no_change")
    error_count = sum(1 for r in results if r["status"] == "error")
    total_processed = len(results)

    # Print summary using Rich Panel
    summary_lines = [
        f"Processed: {total_processed}",
        f"Renamed: {renamed_count}",
        f"Dry Run (would rename): {dryrun_count}",
        f"No Change Needed: {nochange_count}",
        f"Skipped (non-PDF/EPUB): {skipped_count}",
        f"Errors: {error_count}",
        f"Total Time: {total_time:.2f} seconds",
    ]
    summary_panel = Panel(
        "\n".join(summary_lines), title="Processing Summary", expand=False
    )
    console.print(summary_panel)

    # Print error details if any
    if error_count > 0:
        console.print("\n[bold red]Errors Encountered:[/bold red]")
        for result in results:
            if result["status"] == "error":
                path_str = str(result.get("original_path", "Unknown File"))
                error_msg = result.get("error_details", "No details")
                console.print(f"- {path_str}: {error_msg}")
        return 1  # Indicate error with exit code
    else:
        return 0  # Indicate success


# --- Main Execution ---


def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description=(
            "Intelligently rename PDF and EPUB files using extracted metadata and AI."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "target",
        nargs="+",
        help="One or more file paths or directories containing files to process.",
    )
    parser.add_argument(
        "-r",
        "--recursive",
        action="store_true",
        help="Recursively search for files in directories.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be renamed without actually changing files.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Set the logging level.",
    )
    parser.add_argument(
        "--use-ai",
        action="store_true",
        help="Use AI (Perplexity API) to enhance metadata if quality is below confidence threshold.",
    )
    parser.add_argument(
        "--confidence",
        type=float,
        default=config.DEFAULT_CONFIDENCE_THRESHOLD,  # Use config value
        help=f"Confidence threshold (0.0-1.0) to trigger AI enhancement (default: {config.DEFAULT_CONFIDENCE_THRESHOLD}).",
    )
    parser.add_argument(
        "--min-year",
        type=int,
        default=config.DEFAULT_MIN_VALID_YEAR,  # Use config value
        help=f"Minimum valid year for metadata (default: {config.DEFAULT_MIN_VALID_YEAR}).",
    )
    parser.add_argument(
        "--max-year",
        type=int,
        default=config.DEFAULT_MAX_VALID_YEAR,  # Use config value
        help=f"Maximum valid year for metadata (default: {config.DEFAULT_MAX_VALID_YEAR}).",
    )
    parser.add_argument(
        "--max-concurrent",
        type=int,
        default=10,  # Default concurrency limit
        help="Maximum number of files to process concurrently (default: 10).",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose output.",
    )
    return parser.parse_args()


async def main() -> int:
    """Main entry point for the IntelliRename CLI."""
    args = parse_arguments()
    start_time = time.time()

    # --- Setup ---
    setup_logging(level="DEBUG" if args.verbose else "INFO")
    log.info("Starting IntelliRename...")
    if args.dry_run:
        log.warning(
            "[bold yellow]Dry run mode enabled. No files will be renamed.[/bold yellow]"
        )

    # Validate AI config if used
    if args.use_ai:
        try:
            validate_perplexity_api_key()
            log.info("AI enhancement enabled and API key validated.")
        except ConfigurationError as e:
            log.error(f"Configuration error: {e}")
            console.print(f"[bold red]Error:[/bold red] {e}")
            return 1

    # --- File Discovery ---
    files_to_process = _find_files_to_process(args.target, args.recursive)
    if not files_to_process:
        return 0  # No files found, successful exit

    # --- Processing ---
    try:
        results = await _run_processing_tasks(
            files=files_to_process,
            dry_run=args.dry_run,
            use_advanced=args.use_advanced,
            use_ai=args.use_ai,
            confidence=args.confidence,
            min_year=args.min_year,
            max_year=args.max_year,
            max_concurrent=args.max_concurrent,
        )
    except Exception as e:
        # Catch errors during task setup/gathering itself (less likely)
        log.exception("Critical error during task execution")
        console.print(f"[bold red]Critical Error:[/bold red] {e}")
        return 1

    # --- Summary ---
    exit_code = _print_processing_summary(results, start_time)

    log.info("IntelliRename finished.")
    return exit_code


# This block is now handled by the `intellirename` entry point in pyproject.toml
# if __name__ == \"__main__\":
#     # Ensure the main function runs within an asyncio event loop
#     # exit_code = asyncio.run(main())
#     # sys.exit(exit_code)
#     pass # Keep the file importable without running main immediately
