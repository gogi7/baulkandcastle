"""
Core modules for Baulkham & Castle Property Tracker.

Contains database helpers, data models, and shared constants.
"""

from baulkandcastle.core.constants import (
    TARGET_SUBURBS,
    POSTCODES,
    EXCELSIOR_CATCHMENT_URL,
)
from baulkandcastle.core.database import (
    get_connection,
    fetch_all,
    fetch_one,
    execute,
)
from baulkandcastle.core.models import PropertyListing, DomainEstimate

__all__ = [
    "TARGET_SUBURBS",
    "POSTCODES",
    "EXCELSIOR_CATCHMENT_URL",
    "get_connection",
    "fetch_all",
    "fetch_one",
    "execute",
    "PropertyListing",
    "DomainEstimate",
]
