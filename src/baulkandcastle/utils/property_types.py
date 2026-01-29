"""
Property Type Utilities

Consolidates property type mapping and validation from:
- valuation_predictor.py:PROPERTY_TYPE_MAP
- baulkandcastle_scraper.py:_extract_property_type()

Provides consistent property type handling across all modules.
"""

from typing import List, Optional, Set

from baulkandcastle.logging_config import get_logger

logger = get_logger(__name__)

# Property type consolidation mapping
# Maps various Domain property types to standardized categories
PROPERTY_TYPE_MAP = {
    # House types
    "house": "house",
    "free-standing": "house",
    "duplex": "house",
    "semi-detached": "house",
    "terrace": "house",
    "villa": "house",
    "acreage": "house",
    "rural": "house",
    # Unit types
    "unit": "unit",
    "apartment": "unit",
    "apartment-unit-flat": "unit",
    "studio": "unit",
    "pent-house": "unit",
    "penthouse": "unit",
    "flat": "unit",
    "serviced-apartment": "unit",
    # Townhouse types
    "townhouse": "townhouse",
    "town-house": "townhouse",
    # Other types
    "other": "other",
    "vacant-land": "other",
    "land": "other",
    "block-of-units": "other",
    "development-site": "other",
    "commercial": "other",
    "retirement": "other",
}

# Consolidated property categories
PROPERTY_CATEGORIES = {"house", "unit", "townhouse", "other"}

# Unit types (for land size imputation)
UNIT_TYPES: Set[str] = {
    "unit",
    "apartment",
    "apartment-unit-flat",
    "studio",
    "pent-house",
    "penthouse",
    "flat",
    "serviced-apartment",
}

# House types (for land size imputation)
HOUSE_TYPES: Set[str] = {
    "house",
    "free-standing",
    "duplex",
    "semi-detached",
    "terrace",
    "villa",
    "acreage",
    "rural",
}

# Townhouse types
TOWNHOUSE_TYPES: Set[str] = {
    "townhouse",
    "town-house",
}


def consolidate_property_type(prop_type: Optional[str]) -> str:
    """Map various property types to consolidated categories.

    Args:
        prop_type: Raw property type string from Domain.

    Returns:
        Consolidated property type: "house", "unit", "townhouse", or "other".

    Example:
        >>> consolidate_property_type("apartment-unit-flat")
        "unit"
        >>> consolidate_property_type("free-standing")
        "house"
        >>> consolidate_property_type(None)
        "other"
    """
    if not prop_type:
        return "other"

    prop_type_lower = str(prop_type).lower().strip()
    return PROPERTY_TYPE_MAP.get(prop_type_lower, "other")


def is_unit_type(prop_type: Optional[str]) -> bool:
    """Check if a property type is a unit/apartment.

    Args:
        prop_type: Property type to check.

    Returns:
        True if the property is a unit type.

    Example:
        >>> is_unit_type("apartment")
        True
        >>> is_unit_type("house")
        False
    """
    if not prop_type:
        return False

    prop_type_lower = str(prop_type).lower().strip()
    return prop_type_lower in UNIT_TYPES or consolidate_property_type(prop_type) == "unit"


def is_house_type(prop_type: Optional[str]) -> bool:
    """Check if a property type is a house.

    Args:
        prop_type: Property type to check.

    Returns:
        True if the property is a house type.

    Example:
        >>> is_house_type("free-standing")
        True
        >>> is_house_type("apartment")
        False
    """
    if not prop_type:
        return False

    prop_type_lower = str(prop_type).lower().strip()
    return prop_type_lower in HOUSE_TYPES or consolidate_property_type(prop_type) == "house"


def is_townhouse_type(prop_type: Optional[str]) -> bool:
    """Check if a property type is a townhouse.

    Args:
        prop_type: Property type to check.

    Returns:
        True if the property is a townhouse type.
    """
    if not prop_type:
        return False

    prop_type_lower = str(prop_type).lower().strip()
    return prop_type_lower in TOWNHOUSE_TYPES or consolidate_property_type(prop_type) == "townhouse"


def get_default_land_size(prop_type: Optional[str]) -> float:
    """Get the default imputed land size for a property type.

    Used when land size is not available from the listing.

    Args:
        prop_type: Property type.

    Returns:
        Default land size in square meters.

    Example:
        >>> get_default_land_size("house")
        550.0
        >>> get_default_land_size("unit")
        0.0
    """
    consolidated = consolidate_property_type(prop_type)

    if consolidated == "house":
        return 550.0  # Average for Baulkham Hills/Castle Hill
    elif consolidated == "townhouse":
        return 250.0
    elif consolidated == "unit":
        return 0.0  # Units don't have meaningful land size
    else:
        return 400.0  # Default for unknown types


def extract_property_type_from_url(url: str) -> Optional[str]:
    """Extract property type from a Domain listing URL.

    Args:
        url: Domain listing URL.

    Returns:
        Property type string or None if not found.

    Example:
        >>> extract_property_type_from_url("https://www.domain.com.au/123-smith-st-house-castle-hill-2154")
        "house"
    """
    if not url:
        return None

    url_lower = url.lower()

    # Check for property types in URL
    for prop_type in PROPERTY_TYPE_MAP.keys():
        if f"-{prop_type}-" in url_lower or url_lower.endswith(f"-{prop_type}"):
            return prop_type

    return None


def get_all_property_types() -> List[str]:
    """Get a list of all recognized property types.

    Returns:
        Sorted list of property type strings.
    """
    return sorted(PROPERTY_TYPE_MAP.keys())


def get_property_categories() -> List[str]:
    """Get a list of consolidated property categories.

    Returns:
        List of category strings.
    """
    return sorted(PROPERTY_CATEGORIES)
