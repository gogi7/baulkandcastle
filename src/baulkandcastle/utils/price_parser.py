"""
Unified Price Parsing Utilities

Consolidates price parsing logic from:
- domain_estimator_helper.py:parse_price_string()
- baulkandcastle_scraper.py:_extract_price_value()

Provides consistent price handling across all modules.
"""

import re
from typing import Optional, Tuple, Union

from baulkandcastle.logging_config import get_logger

logger = get_logger(__name__)


def extract_price_value(price_str: Union[str, None]) -> Optional[int]:
    """Extract numeric price value from a price string.

    Handles various price formats:
    - "$1,500,000"
    - "$1.5M"
    - "$1.5m"
    - "1500000"
    - "$1,500,000 - $1,700,000" (returns lower bound)
    - "Price Guide $1,500,000"
    - "Auction" (returns None)
    - "Contact Agent" (returns None)

    Args:
        price_str: Price string to parse.

    Returns:
        Integer price value or None if cannot be extracted.

    Example:
        >>> extract_price_value("$1,500,000")
        1500000
        >>> extract_price_value("$1.5M")
        1500000
    """
    if not price_str:
        return None

    price_str = str(price_str).strip()
    if not price_str:
        return None

    # Skip non-numeric indicators
    lower_str = price_str.lower()
    if any(skip in lower_str for skip in ["auction", "contact", "expression", "eoi", "offers"]):
        return None

    # Handle millions shorthand (e.g., "$1.5M")
    million_match = re.search(r'\$?(\d+(?:\.\d+)?)\s*[mM]', price_str)
    if million_match:
        value = float(million_match.group(1))
        return int(value * 1_000_000)

    # Handle thousands shorthand (e.g., "$500K")
    thousand_match = re.search(r'\$?(\d+(?:\.\d+)?)\s*[kK]', price_str)
    if thousand_match:
        value = float(thousand_match.group(1))
        return int(value * 1_000)

    # For ranges, extract the first number (lower bound)
    # "$1,500,000 - $1,700,000" -> 1500000
    range_match = re.search(r'\$?([\d,]+)\s*[-–—]\s*\$?([\d,]+)', price_str)
    if range_match:
        try:
            return int(range_match.group(1).replace(",", ""))
        except ValueError:
            pass

    # Extract any numeric value with optional dollar sign and commas
    numeric_match = re.search(r'\$?([\d,]+)', price_str)
    if numeric_match:
        try:
            value = int(numeric_match.group(1).replace(",", ""))
            # Sanity check: ignore values that are clearly not prices
            if value >= 10_000:
                return value
        except ValueError:
            pass

    logger.debug("Could not extract price from: %s", price_str)
    return None


def parse_price(price_str: Union[str, None]) -> Tuple[Optional[int], Optional[int]]:
    """Parse a price string and extract both low and high values.

    For range prices, returns (low, high).
    For single prices, returns (price, price).

    Args:
        price_str: Price string to parse.

    Returns:
        Tuple of (low_price, high_price) or (None, None) if parsing fails.

    Example:
        >>> parse_price("$1,500,000 - $1,700,000")
        (1500000, 1700000)
        >>> parse_price("$1,500,000")
        (1500000, 1500000)
    """
    if not price_str:
        return None, None

    price_str = str(price_str).strip()
    if not price_str:
        return None, None

    # Check for range pattern
    range_patterns = [
        r'\$?([\d,]+(?:\.\d+)?[mMkK]?)\s*[-–—to]+\s*\$?([\d,]+(?:\.\d+)?[mMkK]?)',
        r'from\s*\$?([\d,]+(?:\.\d+)?[mMkK]?)',
    ]

    for pattern in range_patterns:
        match = re.search(pattern, price_str, re.IGNORECASE)
        if match:
            low_str = match.group(1)
            low = _parse_single_value(low_str)

            if len(match.groups()) > 1:
                high_str = match.group(2)
                high = _parse_single_value(high_str)
            else:
                high = low

            if low and high:
                return min(low, high), max(low, high)
            elif low:
                return low, low

    # Single value
    value = extract_price_value(price_str)
    if value:
        return value, value

    return None, None


def _parse_single_value(value_str: str) -> Optional[int]:
    """Parse a single price value string."""
    # Handle millions
    if re.search(r'[mM]', value_str):
        num_match = re.search(r'([\d,]+(?:\.\d+)?)', value_str)
        if num_match:
            return int(float(num_match.group(1).replace(",", "")) * 1_000_000)

    # Handle thousands
    if re.search(r'[kK]', value_str):
        num_match = re.search(r'([\d,]+(?:\.\d+)?)', value_str)
        if num_match:
            return int(float(num_match.group(1).replace(",", "")) * 1_000)

    # Regular number
    num_match = re.search(r'([\d,]+)', value_str)
    if num_match:
        return int(num_match.group(1).replace(",", ""))

    return None


def format_price(price: Union[int, float, None], compact: bool = False) -> str:
    """Format a price value as a string.

    Args:
        price: Price value to format.
        compact: If True, use compact notation ($1.5M instead of $1,500,000).

    Returns:
        Formatted price string.

    Example:
        >>> format_price(1500000)
        "$1,500,000"
        >>> format_price(1500000, compact=True)
        "$1.5M"
    """
    if price is None:
        return "-"

    price = int(price)

    if compact:
        if price >= 1_000_000:
            value = price / 1_000_000
            if value == int(value):
                return f"${int(value)}M"
            return f"${value:.1f}M".rstrip("0").rstrip(".")
        elif price >= 1_000:
            value = price / 1_000
            if value == int(value):
                return f"${int(value)}K"
            return f"${value:.1f}K".rstrip("0").rstrip(".")

    return f"${price:,}"


def format_price_range(low: Optional[int], high: Optional[int], compact: bool = False) -> str:
    """Format a price range as a string.

    Args:
        low: Low price value.
        high: High price value.
        compact: If True, use compact notation.

    Returns:
        Formatted price range string.

    Example:
        >>> format_price_range(1500000, 1700000)
        "$1,500,000 - $1,700,000"
        >>> format_price_range(1500000, 1700000, compact=True)
        "$1.5M - $1.7M"
    """
    if low is None and high is None:
        return "-"

    if low is None:
        return format_price(high, compact)

    if high is None:
        return format_price(low, compact)

    if low == high:
        return format_price(low, compact)

    return f"{format_price(low, compact)} - {format_price(high, compact)}"


def calculate_price_per_sqm(price: Union[int, float, None], land_size: Union[str, float, None]) -> Optional[float]:
    """Calculate price per square meter.

    Args:
        price: Property price.
        land_size: Land size (can be string like "450m²" or numeric).

    Returns:
        Price per square meter, or None if calculation not possible.
    """
    if price is None or price <= 0:
        return None

    # Parse land size if string
    if isinstance(land_size, str):
        land_size = _parse_land_size(land_size)

    if land_size is None or land_size <= 0:
        return None

    return price / land_size


def _parse_land_size(land_str: str) -> Optional[float]:
    """Parse land size from string like '450m²' or '450'."""
    if not land_str or land_str.lower() in ("na", "-", ""):
        return None

    match = re.search(r'(\d+(?:\.\d+)?)', str(land_str))
    if match:
        value = float(match.group(1))
        return value if value > 0 else None
    return None
