"""CLI utility functions."""

import sys


def get_python_path() -> str:
    """Return the path to the current Python interpreter."""
    return sys.executable
