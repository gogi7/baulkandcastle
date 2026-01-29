"""
Flask REST API for property valuation service.

Provides endpoints for:
- Property value predictions
- Model information and health checks
- Property data queries
"""

from baulkandcastle.api.server import create_app
from baulkandcastle.api.routes import register_routes

__all__ = [
    "create_app",
    "register_routes",
]
