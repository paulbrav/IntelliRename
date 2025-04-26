#!/usr/bin/env python3
"""
Runner script for the Book & Paper Renamer tool.

This script allows for easy invocation of the book renaming tool by providing a simple entry point.
"""

import os
import sys

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from intellirename.main import main

if __name__ == "__main__":
    sys.exit(main())
