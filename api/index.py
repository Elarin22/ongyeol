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

from app import app  # noqa: E402
from feature_routes import register_feature_routes  # noqa: E402

# Keep feature routes available in both local and deployed entry points.
register_feature_routes(app)

__all__ = ["app"]
