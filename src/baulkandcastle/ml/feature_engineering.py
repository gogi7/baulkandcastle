"""
Feature Engineering for Property Valuation Model

Provides functions for creating ML features from property data.
"""

import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from baulkandcastle.utils.date_parser import parse_date, get_season
from baulkandcastle.utils.property_types import (
    consolidate_property_type,
    is_unit_type,
    get_default_land_size,
)
from baulkandcastle.logging_config import get_logger

logger = get_logger(__name__)

# Feature column names
FEATURE_COLUMNS = [
    "land_size_numeric",
    "beds",
    "baths",
    "cars",
    "bedroom_to_land_ratio",
    "bathroom_to_bedroom_ratio",
    "suburb_castle_hill",
    "property_type_house",
    "property_type_unit",
    "property_type_townhouse",
    "is_house_large_land",
    "has_real_land_size",
    "is_spring",
    "is_summer",
    "is_autumn",
    "is_winter",
    "years_since_sale",
    "rolling_avg_price_per_m2",
]


def parse_land_size(land_size_str: str) -> Optional[float]:
    """Extract numeric land size from string like '450m²' or '450'.

    Args:
        land_size_str: Land size string.

    Returns:
        Numeric land size or None.
    """
    if not land_size_str or land_size_str in ("na", "NA", "-", ""):
        return None
    match = re.search(r"(\d+(?:\.\d+)?)", str(land_size_str))
    if match:
        value = float(match.group(1))
        return value if value > 0 else None
    return None


def engineer_features(
    row: Dict,
    rolling_avg_cache: Optional[Dict[str, float]] = None,
    reference_date: Optional[datetime] = None,
) -> Dict[str, float]:
    """Engineer features for a single property.

    Args:
        row: Property data dictionary with keys like beds, baths, land_size, etc.
        rolling_avg_cache: Cache of rolling average price per m2 by suburb.
        reference_date: Reference date for time-based features.

    Returns:
        Dictionary of feature values.
    """
    if reference_date is None:
        reference_date = datetime.now()

    if rolling_avg_cache is None:
        rolling_avg_cache = {}

    # Parse inputs
    beds = int(row.get("beds", 0) or 0)
    baths = int(row.get("baths", 0) or 0)
    cars = int(row.get("cars", 0) or 0)
    suburb = str(row.get("suburb", "")).upper()
    prop_type_raw = row.get("property_type", "")

    # Consolidate property type
    prop_type = consolidate_property_type(prop_type_raw)

    # Parse land size
    land_size_raw = row.get("land_size")
    land_size = parse_land_size(str(land_size_raw)) if land_size_raw else None

    # Determine if we have real land size data
    has_real_land_size = 1.0 if land_size and land_size > 0 else 0.0

    # Impute land size if missing
    if land_size is None or land_size == 0:
        land_size = get_default_land_size(prop_type)

    # Parse sold date for time features
    sold_date_str = row.get("sold_date_iso") or row.get("sold_date")
    sold_date = parse_date(sold_date_str) if sold_date_str else reference_date

    # Calculate years since sale
    years_since = (reference_date - sold_date).days / 365.25 if sold_date else 0.0

    # Get season
    season = get_season(sold_date) if sold_date else get_season(reference_date)

    # Calculate derived features
    bedroom_to_land_ratio = beds / land_size if land_size > 0 else 0.0
    bathroom_to_bedroom_ratio = baths / beds if beds > 0 else 0.0

    # Large land house indicator
    is_house_large_land = 1.0 if prop_type == "house" and land_size > 700 else 0.0

    # Get rolling average price per m2
    cache_key = f"{suburb}_{reference_date.strftime('%Y-%m')}"
    rolling_avg = rolling_avg_cache.get(cache_key, 5000.0)  # Default fallback

    return {
        "land_size_numeric": land_size,
        "beds": float(beds),
        "baths": float(baths),
        "cars": float(cars),
        "bedroom_to_land_ratio": bedroom_to_land_ratio,
        "bathroom_to_bedroom_ratio": bathroom_to_bedroom_ratio,
        "suburb_castle_hill": 1.0 if "CASTLE" in suburb else 0.0,
        "property_type_house": 1.0 if prop_type == "house" else 0.0,
        "property_type_unit": 1.0 if prop_type == "unit" else 0.0,
        "property_type_townhouse": 1.0 if prop_type == "townhouse" else 0.0,
        "is_house_large_land": is_house_large_land,
        "has_real_land_size": has_real_land_size,
        "is_spring": 1.0 if season == "spring" else 0.0,
        "is_summer": 1.0 if season == "summer" else 0.0,
        "is_autumn": 1.0 if season == "autumn" else 0.0,
        "is_winter": 1.0 if season == "winter" else 0.0,
        "years_since_sale": years_since,
        "rolling_avg_price_per_m2": rolling_avg,
    }


def compute_rolling_avg_price_per_m2(
    df: pd.DataFrame,
    current_date: datetime,
    suburb: str,
    lookback_days: int = 180,
) -> float:
    """Compute rolling average price per m2 for a suburb.

    Args:
        df: DataFrame with property data.
        current_date: Reference date.
        suburb: Suburb name.
        lookback_days: Number of days to look back.

    Returns:
        Average price per square meter.
    """
    # Filter to same suburb, valid price_per_m2, and within lookback period
    cutoff = current_date - pd.Timedelta(days=lookback_days)

    mask = (
        (df["suburb"].str.upper() == suburb.upper())
        & (df["price_per_m2"].notna())
        & (df["price_per_m2"] > 0)
        & (df["sold_date_parsed"] < current_date)
        & (df["sold_date_parsed"] >= cutoff)
    )
    subset = df.loc[mask, "price_per_m2"]

    if len(subset) >= 5:
        return subset.mean()

    # Fall back to overall average if not enough suburb data
    overall_mask = (
        (df["price_per_m2"].notna())
        & (df["price_per_m2"] > 0)
        & (df["sold_date_parsed"] < current_date)
        & (df["sold_date_parsed"] >= cutoff)
    )
    overall_subset = df.loc[overall_mask, "price_per_m2"]

    if len(overall_subset) >= 5:
        return overall_subset.mean()

    # Last resort fallback
    return 5000.0


def build_rolling_avg_cache(
    df: pd.DataFrame,
    suburbs: List[str],
    lookback_days: int = 180,
) -> Dict[str, float]:
    """Build cache of rolling average prices for all suburb/month combinations.

    Args:
        df: DataFrame with property data.
        suburbs: List of suburb names.
        lookback_days: Number of days to look back.

    Returns:
        Dictionary mapping "SUBURB_YYYY-MM" to average price per m2.
    """
    cache = {}

    # Get unique months from the data
    if "sold_date_parsed" not in df.columns:
        return cache

    df_with_dates = df[df["sold_date_parsed"].notna()].copy()
    if len(df_with_dates) == 0:
        return cache

    # Generate month range
    min_date = df_with_dates["sold_date_parsed"].min()
    max_date = df_with_dates["sold_date_parsed"].max()

    current = min_date
    while current <= max_date:
        for suburb in suburbs:
            key = f"{suburb.upper()}_{current.strftime('%Y-%m')}"
            avg = compute_rolling_avg_price_per_m2(df_with_dates, current, suburb, lookback_days)
            cache[key] = avg
        current = current + pd.DateOffset(months=1)

    return cache


def validate_features(features: Dict[str, float]) -> Tuple[bool, List[str]]:
    """Validate feature values are within expected ranges.

    Args:
        features: Dictionary of feature values.

    Returns:
        Tuple of (is_valid, list_of_warnings).
    """
    warnings = []

    # Check for missing required features
    for col in FEATURE_COLUMNS:
        if col not in features:
            warnings.append(f"Missing feature: {col}")

    # Validate ranges
    if features.get("beds", 0) > 10:
        warnings.append(f"Unusual bedroom count: {features.get('beds')}")
    if features.get("baths", 0) > 8:
        warnings.append(f"Unusual bathroom count: {features.get('baths')}")
    if features.get("land_size_numeric", 0) > 10000:
        warnings.append(f"Unusual land size: {features.get('land_size_numeric')}")

    is_valid = len([w for w in warnings if "Missing" in w]) == 0
    return is_valid, warnings
