"""Vercel Python function entry point for the Flask application."""

from __future__ import annotations

import sys
from pathlib import Path

FUNCTION_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = FUNCTION_DIR.parent

# The Vercel Python builder normally bundles project files alongside this
# function. Add both likely roots so app.py can be imported in either layout.
for import_path in (PROJECT_ROOT, FUNCTION_DIR):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

from app import app  # noqa: E402,F401
