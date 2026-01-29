"""
Unified Date Parsing Utilities

Consolidates date parsing logic from:
- domain_estimator_helper.py:parse_snapshot_text()
- valuation_predictor.py:_parse_sold_date()
- baulkandcastle_scraper.py:_convert_to_iso_date()

Provides consistent date handling across all modules.
"""

import re
from datetime import datetime
from typing import Optional, Union

from baulkandcastle.exceptions import ParsingError
from baulkandcastle.logging_config import get_logger

logger = get_logger(__name__)

# Common date format patterns
DATE_PATTERNS = [
    # ISO format: 2024-01-15
    (r"^\d{4}-\d{2}-\d{2}$", "%Y-%m-%d"),
    # ISO with time: 2024-01-15T10:30:00
    (r"^\d{4}-\d{2}-\d{2}T", "%Y-%m-%dT%H:%M:%S"),
    # Australian format: 15/01/2024
    (r"^\d{2}/\d{2}/\d{4}$", "%d/%m/%Y"),
    # Domain format: 15 Jan 2024
    (r"^\d{1,2}\s+[A-Za-z]{3}\s+\d{4}$", "%d %b %Y"),
    # Full month: 15 January 2024
    (r"^\d{1,2}\s+[A-Za-z]+\s+\d{4}$", "%d %B %Y"),
    # Month year: Jan 2024
    (r"^[A-Za-z]{3}\s+\d{4}$", "%b %Y"),
    # Compact: 15Jan2024
    (r"^\d{1,2}[A-Za-z]{3}\d{4}$", "%d%b%Y"),
]


def parse_date(date_str: Union[str, None]) -> Optional[datetime]:
    """Parse a date string into a datetime object.

    Handles various date formats commonly seen in property data:
    - ISO format: 2024-01-15, 2024-01-15T10:30:00
    - Australian format: 15/01/2024
    - Domain format: 15 Jan 2024
    - Full month: 15 January 2024
    - Month year: Jan 2024

    Args:
        date_str: Date string to parse.

    Returns:
        datetime object or None if parsing fails.

    Example:
        >>> parse_date("15 Jan 2024")
        datetime(2024, 1, 15, 0, 0)
        >>> parse_date("2024-01-15")
        datetime(2024, 1, 15, 0, 0)
    """
    if not date_str:
        return None

    date_str = str(date_str).strip()
    if not date_str:
        return None

    # Handle ISO format with time component
    if "T" in date_str:
        date_str = date_str.split("T")[0]
        try:
            return datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            pass

    # Try each pattern
    for pattern, fmt in DATE_PATTERNS:
        if re.match(pattern, date_str, re.IGNORECASE):
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue

    # Last resort: try common patterns without regex matching
    fallback_formats = [
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%d %b %Y",
        "%d %B %Y",
        "%b %Y",
        "%d-%m-%Y",
    ]
    for fmt in fallback_formats:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue

    logger.debug("Could not parse date: %s", date_str)
    return None


def parse_to_iso(date_str: Union[str, None]) -> Optional[str]:
    """Parse a date string and return ISO format (YYYY-MM-DD).

    Args:
        date_str: Date string to parse.

    Returns:
        ISO format date string or None if parsing fails.

    Example:
        >>> parse_to_iso("15 Jan 2024")
        "2024-01-15"
    """
    dt = parse_date(date_str)
    if dt:
        return dt.strftime("%Y-%m-%d")
    return None


def parse_snapshot_date(snapshot_text: str) -> Optional[str]:
    """Parse Domain snapshot/estimate date text.

    Handles text like:
    - "Estimated Jan 2024"
    - "As at 15 Jan 2024"
    - "Updated January 2024"

    Args:
        snapshot_text: Text containing a date reference.

    Returns:
        ISO format date string or None if no date found.

    Example:
        >>> parse_snapshot_date("Estimated Jan 2024")
        "2024-01-01"
    """
    if not snapshot_text:
        return None

    # Remove common prefixes
    text = snapshot_text.lower()
    for prefix in ["estimated", "as at", "updated", "last updated"]:
        text = text.replace(prefix, "").strip()

    # Try to parse what remains
    return parse_to_iso(text.strip())


def format_date(dt: Optional[datetime], fmt: str = "%d %b %Y") -> str:
    """Format a datetime object as a string.

    Args:
        dt: datetime object to format.
        fmt: strftime format string.

    Returns:
        Formatted date string, or empty string if dt is None.

    Example:
        >>> format_date(datetime(2024, 1, 15))
        "15 Jan 2024"
    """
    if dt is None:
        return ""
    return dt.strftime(fmt)


def days_between(date1: Union[str, datetime], date2: Union[str, datetime]) -> Optional[int]:
    """Calculate days between two dates.

    Args:
        date1: First date (string or datetime).
        date2: Second date (string or datetime).

    Returns:
        Number of days between dates, or None if parsing fails.
    """
    if isinstance(date1, str):
        date1 = parse_date(date1)
    if isinstance(date2, str):
        date2 = parse_date(date2)

    if date1 is None or date2 is None:
        return None

    return abs((date2 - date1).days)


def get_season(dt: datetime) -> str:
    """Get the Australian season for a date.

    Australian seasons:
    - Summer: Dec, Jan, Feb
    - Autumn: Mar, Apr, May
    - Winter: Jun, Jul, Aug
    - Spring: Sep, Oct, Nov

    Args:
        dt: datetime object.

    Returns:
        Season name ("summer", "autumn", "winter", "spring").
    """
    month = dt.month
    if month in (12, 1, 2):
        return "summer"
    elif month in (3, 4, 5):
        return "autumn"
    elif month in (6, 7, 8):
        return "winter"
    else:
        return "spring"


def years_since(date_str: Union[str, datetime], reference: datetime = None) -> Optional[float]:
    """Calculate years since a date.

    Args:
        date_str: Date to calculate from.
        reference: Reference date (defaults to now).

    Returns:
        Years since the date, or None if parsing fails.
    """
    if reference is None:
        reference = datetime.now()

    if isinstance(date_str, str):
        dt = parse_date(date_str)
    else:
        dt = date_str

    if dt is None:
        return None

    delta = reference - dt
    return delta.days / 365.25
