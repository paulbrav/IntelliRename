# IntelliRename Development Tasks

This file tracks ongoing development tasks based on code reviews and feature requests.

## Code Review Action Items (Initial Review)

### Project Structure & Packaging

-   [x] Remove `sys.path` manipulation in `intellirename/__main__.py`.
-   [x] Extract shared constants (`UNKNOWN_AUTHOR`, etc.) from `intellirename/main.py` and `intellirename/metadata.py` into a new `intellirename/constants.py` file.
-   [x] Centralize environment variable loading and configuration settings (confidence, retries, cache dir, API settings) into a new `intellirename/config.py` file.
-   [x] Move `utils/ai_metadata.py` to `intellirename/ai.py` as it's core functionality.

### Typing & Docstrings

-   [x] Add complete type hints (using `pathlib.Path` where appropriate) to all public functions and methods.
-   [x] Ensure all public functions/methods have complete Google-style docstrings, including `Args:`, `Returns:`, and `Raises:` sections.
-   [x] Add a docstring to `intellirename.main.process_file`.

### Function Length & Complexity

-   [x] Refactor `intellirename.main.process_file` into smaller, focused helper functions (e.g., for metadata extraction, AI enhancement decision, renaming logic).
-   [x] Refactor `intellirename.main.main` to delegate more logic to helper functions.
-   [x] Simplify nested `try...except` blocks by extracting logic into helper functions where feasible.

### Error Handling

-   [x] Standardize error handling approach (choose between returning status tuples like `(bool, str)` or raising exceptions for API/library functions).
    -   [x] Decision: Standardize on raising specific custom exceptions.
    -   [x] Create `intellirename/exceptions.py` with base and specific exception classes.
-   [x] Replace bare `except Exception:` clauses with specific exception types or use `log.exception` to include tracebacks.
    -   [x] Refactor `intellirename/main.py`:
        -   [x] Update `extract_from_pdf` to raise `MetadataExtractionError`.
        -   [x] Update `extract_from_epub` to raise `MetadataExtractionError`.
        -   [x] Update `rename_file` to raise `RenamingError` or `FileOperationError` instead of returning tuple.
        -   [x] Update `process_file` to handle specific `IntelliRenameError` subclasses.
        -   [x] Update `main` function's main loop to handle specific errors gracefully.
    -   [x] Refactor `intellirename/metadata.py` to raise `MetadataExtractionError`.
    -   [x] Refactor `intellirename/ai.py` to raise `ConfigurationError`, `AICommunicationError`, `AIProcessingError`.
    -   [x] Refactor `intellirename/config.py` to raise `ConfigurationError`.

### I/O & Performance

-   [x] Optimize PDF reading to avoid opening/reading the same file multiple times within `process_file` (cache `PdfReader` or pass page text).
-   [x] Implement asynchronous Perplexity API calls using `aiohttp`:
    -   [x] **Dependencies:** Add `aiohttp` to `pyproject.toml` and update lockfile/sync.
    -   [x] **Refactor API Client (`intellirename/ai.py`):**
        -   [x] Make `query_perplexity` asynchronous (`async def query_perplexity_async`).
        -   [x] Use `aiohttp.ClientSession` for the API request.
        -   [x] Adapt error handling for `aiohttp.ClientError` and JSON errors.
        -   [x] Make `enhance_metadata` asynchronous.
    -   [x] **Refactor Processing Logic (`intellirename/main.py`):**
        -   [x] Make the main file processing function (`process_file`) asynchronous (`async def`).
        -   [x] Modify the main file processing loop (`main`) to create `asyncio` tasks for `process_file` calls.
        -   [x] Use `asyncio.gather` to run tasks concurrently and collect results/exceptions.
        -   [x] Handle results and exceptions from gathered tasks.
    -   [x] **Adapt Entry Point:**
        -   [x] Make `main()` in `intellirename/main.py` asynchronous (`async def`).
        -   [x] Update `intellirename/__main__.py` to use `asyncio.run(main())`.
    -   [ ] **Configuration (`intellirename/config.py`):** (Optional) Add `aiohttp`-specific configurations if needed.
    -   [~] **Testing:** Add `pytest-asyncio`, update/add tests using `AsyncMock` or `aresponses`. (Tests added, linter needs env check).
    -   [x] **Documentation:** Update docstrings and `README.md`.

### Security & Robustness

-   [x] Enhance `sanitize_filename` to handle control characters and potentially use a library like `pathvalidate`.
-   [x] Review the year validation range (currently 1800-present) and consider making it configurable or widening it.

### Logging

-   [x] Move CLI-specific logging configuration (e.g., `basicConfig` with `RichHandler`) from the global scope in `main.py` into the `main()` function or a dedicated `cli.py` module.
-   [x] Use `log.exception(...)` instead of `log.error(...)` or `log.warning(...)` within `except` blocks to automatically capture tracebacks.

### README & Documentation

-   [x] Update `README.md` to reflect the actual project structure (`intellirename/` not `pdf_renamer/`).
-   [x] Correct the `README.md` section about `config.py` once the file is created.

### Dependency Management

-   [x] (or `pyproject.toml` if using `uv`) exists and pins major versions. should have a uv lock file.
-   [x] Add `uv` usage instructions to the README if it's the preferred package manager.

## Future Enhancements

-   [x] Add unit tests (e.g., using `pytest`) covering core logic like filename parsing, metadata extraction, sanitization, and caching.
-   [x] Add integration tests for the main CLI workflow.
-   [x] Implement asynchronous API calls for performance improvement (see I/O section). 