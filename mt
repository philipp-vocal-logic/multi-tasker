#!/usr/bin/env python3
"""Executable wrapper for the `mt` CLI."""

import sys

from src.cli.main import main

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
