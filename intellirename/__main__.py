"""Entry point for running the package as a module."""

import os
import sys

# Ensure the main package is in the Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, project_root)

from intellirename.main import main

if __name__ == "__main__":
    sys.exit(main())
