"""
Pytest Configuration and Fixtures

Provides shared fixtures for all tests.
"""

import os
import sqlite3
import tempfile
from pathlib import Path
from typing import Generator

import pytest

# Add src to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


@pytest.fixture(scope="session")
def project_root() -> Path:
    """Get the project root directory."""
    return Path(__file__).parent.parent


@pytest.fixture(scope="function")
def temp_db() -> Generator[str, None, None]:
    """Create a temporary test database.

    Yields:
        Path to temporary database file.
    """
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    # Initialize database schema
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create tables
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS properties (
            property_id TEXT PRIMARY KEY,
            address TEXT,
            suburb TEXT,
            first_seen TEXT,
            url TEXT,
            in_excelsior_catchment INTEGER DEFAULT 0
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS listing_history (
            property_id TEXT,
            date TEXT,
            status TEXT,
            price_display TEXT,
            price_value INTEGER,
            beds INTEGER,
            baths INTEGER,
            cars INTEGER,
            land_size TEXT,
            property_type TEXT,
            agent TEXT,
            scraped_at TEXT,
            sold_date TEXT,
            sold_date_iso TEXT,
            price_per_m2 REAL,
            PRIMARY KEY (property_id, date, status)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS daily_summary (
            date TEXT PRIMARY KEY,
            new_count INTEGER,
            sold_count INTEGER,
            adj_count INTEGER
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS property_valuations (
            property_id TEXT PRIMARY KEY,
            latest_low INTEGER,
            latest_high INTEGER,
            propertyvalue_url TEXT,
            last_updated TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS xgboost_predictions (
            property_id TEXT PRIMARY KEY,
            predicted_price INTEGER,
            price_range_low INTEGER,
            price_range_high INTEGER,
            predicted_at TEXT,
            model_version TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS domain_estimates (
            property_id TEXT PRIMARY KEY,
            address TEXT,
            suburb TEXT,
            estimate_low INTEGER,
            estimate_mid INTEGER,
            estimate_high INTEGER,
            estimate_date TEXT,
            scraped_at TEXT
        )
    """)

    conn.commit()
    conn.close()

    yield db_path

    # Cleanup
    try:
        os.unlink(db_path)
    except (OSError, PermissionError):
        pass


@pytest.fixture(scope="function")
def test_config(temp_db: str, monkeypatch):
    """Create test configuration with temp database.

    Args:
        temp_db: Path to temporary database.
        monkeypatch: pytest monkeypatch fixture.

    Yields:
        Config object configured for testing.
    """
    # Set environment variables
    monkeypatch.setenv("BAULKANDCASTLE_DB_PATH", temp_db)
    monkeypatch.setenv("BAULKANDCASTLE_LOG_LEVEL", "DEBUG")

    # Reset config singleton
    from baulkandcastle.config import reset_config, get_config
    reset_config()

    config = get_config()
    yield config

    # Cleanup
    reset_config()


@pytest.fixture(scope="function")
def sample_property_data() -> dict:
    """Sample property data for testing."""
    return {
        "id": "test-property-123",
        "address": "123 Test Street",
        "suburb": "CASTLE HILL",
        "price_display": "$1,500,000",
        "price_value": 1500000,
        "bedrooms": 4,
        "bathrooms": 2,
        "parking": 2,
        "land_size": "600m²",
        "property_type": "house",
        "url": "https://www.domain.com.au/123-test-street-castle-hill-nsw-2154",
        "status": "sale",
    }


@pytest.fixture(scope="function")
def sample_sold_property() -> dict:
    """Sample sold property data for testing."""
    return {
        "id": "sold-property-456",
        "address": "456 Sold Street",
        "suburb": "BAULKHAM HILLS",
        "price_display": "$1,200,000",
        "price_value": 1200000,
        "bedrooms": 3,
        "bathrooms": 2,
        "parking": 1,
        "land_size": "450m²",
        "property_type": "house",
        "url": "https://www.domain.com.au/456-sold-street-baulkham-hills-nsw-2153",
        "status": "sold",
        "sold_date": "15 Jan 2024",
        "sold_date_iso": "2024-01-15",
    }


@pytest.fixture(scope="function")
def sample_unit_property() -> dict:
    """Sample unit property data for testing."""
    return {
        "id": "unit-property-789",
        "address": "5/10 Unit Block",
        "suburb": "CASTLE HILL",
        "price_display": "$750,000",
        "price_value": 750000,
        "bedrooms": 2,
        "bathrooms": 1,
        "parking": 1,
        "land_size": None,
        "property_type": "apartment-unit-flat",
        "url": "https://www.domain.com.au/5-10-unit-block-castle-hill-nsw-2154",
        "status": "sale",
    }


@pytest.fixture(scope="function")
def populated_db(temp_db: str, sample_property_data: dict, sample_sold_property: dict) -> str:
    """Create a database with sample data.

    Returns:
        Path to populated database.
    """
    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()

    # Insert for-sale property
    cursor.execute("""
        INSERT INTO properties (property_id, address, suburb, first_seen, url)
        VALUES (?, ?, ?, ?, ?)
    """, (
        sample_property_data["id"],
        sample_property_data["address"],
        sample_property_data["suburb"],
        "2024-01-01",
        sample_property_data["url"],
    ))

    cursor.execute("""
        INSERT INTO listing_history (
            property_id, date, status, price_display, price_value,
            beds, baths, cars, land_size, property_type
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        sample_property_data["id"],
        "2024-01-01",
        "sale",
        sample_property_data["price_display"],
        sample_property_data["price_value"],
        sample_property_data["bedrooms"],
        sample_property_data["bathrooms"],
        sample_property_data["parking"],
        sample_property_data["land_size"],
        sample_property_data["property_type"],
    ))

    # Insert sold property
    cursor.execute("""
        INSERT INTO properties (property_id, address, suburb, first_seen, url)
        VALUES (?, ?, ?, ?, ?)
    """, (
        sample_sold_property["id"],
        sample_sold_property["address"],
        sample_sold_property["suburb"],
        "2023-12-01",
        sample_sold_property["url"],
    ))

    cursor.execute("""
        INSERT INTO listing_history (
            property_id, date, status, price_display, price_value,
            beds, baths, cars, land_size, property_type,
            sold_date, sold_date_iso
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        sample_sold_property["id"],
        "2024-01-15",
        "sold",
        sample_sold_property["price_display"],
        sample_sold_property["price_value"],
        sample_sold_property["bedrooms"],
        sample_sold_property["bathrooms"],
        sample_sold_property["parking"],
        sample_sold_property["land_size"],
        sample_sold_property["property_type"],
        sample_sold_property["sold_date"],
        sample_sold_property["sold_date_iso"],
    ))

    conn.commit()
    conn.close()

    return temp_db
