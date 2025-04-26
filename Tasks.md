# IntelliRename Development Tasks

This file tracks ongoing development tasks based on code reviews and feature requests.

## Code Review Action Items (Initial Review)

### Project Structure & Packaging

-   [ ] Remove `sys.path` manipulation in `intellirename/__main__.py`.
-   [ ] Extract shared constants (`UNKNOWN_AUTHOR`, etc.) from `intellirename/main.py` and `intellirename/metadata.py` into a new `intellirename/constants.py` file.
-   [ ] Centralize environment variable loading and configuration settings (confidence, retries, cache dir, API settings) into a new `intellirename/config.py` file.
-   [ ] Consider moving `utils/ai_metadata.py` to `intellirename/ai.py` as it's core functionality.

### Typing & Docstrings

-   [ ] Add complete type hints (using `pathlib.Path` where appropriate) to all public functions and methods.
-   [ ] Ensure all public functions/methods have complete Google-style docstrings, including `Args:`, `Returns:`, and `Raises:` sections.
-   [ ] Add a docstring to `intellirename.main.process_file`.

### Function Length & Complexity

-   [ ] Refactor `intellirename.main.process_file` into smaller, focused helper functions (e.g., for metadata extraction, AI enhancement decision, renaming logic).
-   [ ] Refactor `intellirename.main.main` to delegate more logic to helper functions.
-   [ ] Simplify nested `try...except` blocks by extracting logic into helper functions where feasible.

### Error Handling

-   [ ] Replace bare `except Exception:` clauses with specific exception types or use `log.exception` to include tracebacks.
-   [ ] Standardize error handling approach (choose between returning status tuples like `(bool, str)` or raising exceptions for API/library functions).

### I/O & Performance

-   [ ] Optimize PDF reading to avoid opening/reading the same file multiple times within `process_file` (cache `PdfReader` or pass page text).
-   [ ] (Optional/Future) Consider using `concurrent.futures` or `asyncio`/`httpx` for parallel/asynchronous Perplexity API calls to improve batch performance.

### Security & Robustness

-   [ ] Enhance `sanitize_filename` to handle control characters and potentially use a library like `pathvalidate`.
-   [ ] Review the year validation range (currently 1800-present) and consider making it configurable or widening it.

### Logging

-   [ ] Move CLI-specific logging configuration (e.g., `basicConfig` with `RichHandler`) from the global scope in `main.py` into the `main()` function or a dedicated `cli.py` module.
-   [ ] Use `log.exception(...)` instead of `log.error(...)` or `log.warning(...)` within `except` blocks to automatically capture tracebacks.

### README & Documentation

-   [ ] Update `README.md` to reflect the actual project structure (`intellirename/` not `pdf_renamer/`).
-   [ ] Correct the `README.md` section about `config.py` once the file is created.

### Dependency Management

-   [ ] Ensure `requirements.txt` (or `pyproject.toml` if using `uv`) exists and pins major versions.
-   [ ] Add `uv` usage instructions to the README if it's the preferred package manager.

## Future Enhancements

-   [ ] Add unit tests (e.g., using `pytest`) covering core logic like filename parsing, metadata extraction, sanitization, and caching.
-   [ ] Add integration tests for the main CLI workflow.
-   [ ] Implement asynchronous API calls for performance improvement (see I/O section). 