"""
Shared Constants for Baulkham & Castle Property Tracker

Contains all constant values used across the application.
"""

from typing import Dict, List

# Target suburbs for property tracking
TARGET_SUBURBS: List[str] = ["BAULKHAM HILLS", "CASTLE HILL"]

# Postcodes for each suburb
POSTCODES: Dict[str, str] = {
    "BAULKHAM HILLS": "2153",
    "CASTLE HILL": "2154",
}

# Excelsior Public School catchment URL (Castle Hill area)
EXCELSIOR_CATCHMENT_URL: str = (
    "https://www.domain.com.au/school-catchment/excelsior-public-school-nsw-2154-637"
    "?ptype=apartment-unit-flat,block-of-units,duplex,free-standing,new-apartments,"
    "new-home-designs,new-house-land,pent-house,semi-detached,studio,terrace,"
    "town-house,villa&ssubs=0"
)

# Domain.com.au base URLs
DOMAIN_BASE_URL: str = "https://www.domain.com.au"
DOMAIN_SEARCH_URL: str = f"{DOMAIN_BASE_URL}/sale/"
DOMAIN_SOLD_URL: str = f"{DOMAIN_BASE_URL}/sold-listings/"
DOMAIN_PROFILE_URL: str = f"{DOMAIN_BASE_URL}/property-profile/"

# Database table names
TABLE_PROPERTIES: str = "properties"
TABLE_LISTING_HISTORY: str = "listing_history"
TABLE_DAILY_SUMMARY: str = "daily_summary"
TABLE_VALUATIONS: str = "property_valuations"
TABLE_PREDICTIONS: str = "xgboost_predictions"
TABLE_DOMAIN_ESTIMATES: str = "domain_estimates"

# Property status values
STATUS_FOR_SALE: str = "sale"
STATUS_SOLD: str = "sold"

# Default values
DEFAULT_LAND_SIZE_HOUSE: float = 550.0
DEFAULT_LAND_SIZE_UNIT: float = 0.0
DEFAULT_LAND_SIZE_TOWNHOUSE: float = 250.0

# Price thresholds for validation
MIN_VALID_PRICE: int = 100_000
MAX_VALID_PRICE: int = 50_000_000

# Feature limits for validation
MAX_BEDROOMS: int = 10
MAX_BATHROOMS: int = 8
MAX_PARKING: int = 10
MAX_LAND_SIZE: float = 10_000.0  # 1 hectare
