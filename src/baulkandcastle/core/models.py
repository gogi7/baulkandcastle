"""
Data Models for Baulkham & Castle Property Tracker

Dataclass definitions for properties, estimates, and predictions.
"""

from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, Any


@dataclass
class PropertyListing:
    """Represents a property listing from Domain.com.au."""

    id: str
    address: str
    suburb: str  # "BAULKHAM HILLS" or "CASTLE HILL"
    price_display: str
    price_value: int
    bedrooms: int
    bathrooms: int
    parking: int
    land_size: Optional[str] = None
    property_type: Optional[str] = None
    price_per_m2: Optional[float] = None
    url: str = ""
    agent: str = ""
    scraped_at: str = ""
    status: str = "sale"  # "sale" or "sold"
    sold_date: Optional[str] = None
    sold_date_iso: Optional[str] = None
    first_seen: Optional[str] = None
    in_excelsior_catchment: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


@dataclass
class DomainEstimate:
    """Full Domain property profile estimate data."""

    property_id: str
    address: str
    suburb: str
    property_type: Optional[str] = None
    beds: Optional[int] = None
    baths: Optional[int] = None
    parking: Optional[int] = None
    land_size: Optional[str] = None

    # Property Value Estimates
    estimate_low: Optional[int] = None
    estimate_mid: Optional[int] = None
    estimate_high: Optional[int] = None
    estimate_accuracy: Optional[str] = None
    estimate_date: Optional[str] = None

    # Rental Estimates
    rental_weekly: Optional[int] = None
    rental_yield: Optional[float] = None
    rental_accuracy: Optional[str] = None
    rental_estimate_date: Optional[str] = None

    # Sale History
    last_sold_date: Optional[str] = None
    last_sold_price: Optional[int] = None
    last_sold_agent: Optional[str] = None
    last_sold_days_listed: Optional[int] = None

    # Current Listing
    listing_status: Optional[str] = None
    listing_agent: Optional[str] = None
    listing_agency: Optional[str] = None

    # Features
    features: Optional[str] = None

    # Metadata
    domain_url: Optional[str] = None
    scraped_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


@dataclass
class PropertyPrediction:
    """ML model prediction result for a property."""

    property_id: str
    predicted_price: int
    price_range_low: int
    price_range_high: int
    confidence_score: float = 0.0
    predicted_at: str = ""
    model_version: str = ""

    # Input features used
    beds: Optional[int] = None
    baths: Optional[int] = None
    cars: Optional[int] = None
    land_size: Optional[float] = None
    property_type: Optional[str] = None
    suburb: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


@dataclass
class DailySummary:
    """Daily scraping summary statistics."""

    date: str
    new_count: int = 0
    sold_count: int = 0
    adjusted_count: int = 0
    total_for_sale: int = 0
    total_sold: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


@dataclass
class PropertyStats:
    """Aggregate property statistics for dashboard."""

    total_for_sale: int = 0
    total_sold: int = 0
    new_this_week: int = 0
    sold_this_week: int = 0
    avg_price_for_sale: float = 0.0
    avg_price_sold: float = 0.0
    median_price_for_sale: float = 0.0
    median_price_sold: float = 0.0
    by_suburb: Dict[str, Dict[str, int]] = field(default_factory=dict)
    by_property_type: Dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)
