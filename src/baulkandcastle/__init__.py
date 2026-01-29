"""
Baulkham Hills & Castle Hill Property Tracker

A comprehensive property tracking and valuation tool for the
Baulkham Hills (2153) and Castle Hill (2154) suburbs in NSW, Australia.

Main components:
- scraper: Web scraping from Domain.com.au
- estimator: Domain Property Profile estimate extraction
- ml: XGBoost-based property valuation model
- api: Flask REST API server
- cli: Command-line interfaces

Usage:
    from baulkandcastle import config
    from baulkandcastle.core import database
    from baulkandcastle.ml import PropertyValuationModel
"""

__version__ = "1.0.0"
__author__ = "Antigravity (for Goran)"

from baulkandcastle.config import get_config
from baulkandcastle.logging_config import setup_logging

__all__ = [
    "__version__",
    "__author__",
    "get_config",
    "setup_logging",
]
