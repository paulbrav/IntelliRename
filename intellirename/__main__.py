"""Entry point for running the package as a module."""

import asyncio
import sys

from intellirename.main import main

if __name__ == "__main__":
    return_code = asyncio.run(main())
    sys.exit(return_code)
