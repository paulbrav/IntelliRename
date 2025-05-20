# Codex Agent Instructions

This repository uses [uv](https://github.com/astral-sh/uv) for dependency management and `mypy` for type checking.

## Environment Setup

1. Create a virtual environment and install dependencies with uv:

   ```bash
   uv venv
   uv pip install -e ".[dev]"
   ```

2. If the lock file changes, run `uv sync` to install updated dependencies.

## Required Checks

Before committing or opening a pull request, run the following checks:

1. **Type Checking**

   ```bash
   uv run mypy intellirename tests
   ```

2. **Tests**

   ```bash
   uv run pytest
   ```

Both commands should complete without errors. Include their results in the PR summary.

