#!/usr/bin/env python3
"""
Runner script for the Book & Paper Renamer tool.

This script allows for easy invocation of the book renaming tool by providing a simple entry point.
"""

import sys
from pdf_renamer.main import main

if __name__ == "__main__":
    sys.exit(main()) 