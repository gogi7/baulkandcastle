#!/usr/bin/env python
"""
Estimate For Sale Properties

Runs ML predictions on all current "for sale" properties and stores
estimates with timestamps. Old estimates are archived to history table.

Usage:
    python ml/estimate_for_sale.py
    python ml/estimate_for_sale.py --db path/to/database.db
"""

import argparse
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from ml.valuation_predictor import PropertyValuationModel


def init_estimate_tables(conn: sqlite3.Connection):
    """Create estimate tables if they don't exist."""
    cursor = conn.cursor()

    # Current estimates table (one row per property)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS property_estimates (
            property_id TEXT PRIMARY KEY,
            estimated_price INTEGER,
            price_range_low INTEGER,
            price_range_high INTEGER,
            estimate_date TEXT,
            model_mape REAL,
            input_land_size REAL,
            input_beds INTEGER,
            input_baths INTEGER,
            input_cars INTEGER,
            input_suburb TEXT,
            input_property_type TEXT
        )
    ''')

    # Historical estimates table (multiple rows per property over time)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS property_estimates_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            property_id TEXT,
            estimated_price INTEGER,
            price_range_low INTEGER,
            price_range_high INTEGER,
            estimate_date TEXT,
            archived_at TEXT,
            model_mape REAL,
            input_land_size REAL,
            input_beds INTEGER,
            input_baths INTEGER,
            input_cars INTEGER,
            input_suburb TEXT,
            input_property_type TEXT
        )
    ''')

    # Index for faster history lookups
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_estimates_history_property
        ON property_estimates_history(property_id)
    ''')

    conn.commit()


def archive_old_estimates(conn: sqlite3.Connection, property_ids: list):
    """Move existing estimates to history table before updating."""
    cursor = conn.cursor()
    now = datetime.now().isoformat()

    # Move existing estimates to history
    cursor.execute('''
        INSERT INTO property_estimates_history
        (property_id, estimated_price, price_range_low, price_range_high,
         estimate_date, archived_at, model_mape, input_land_size, input_beds,
         input_baths, input_cars, input_suburb, input_property_type)
        SELECT
            property_id, estimated_price, price_range_low, price_range_high,
            estimate_date, ?, model_mape, input_land_size, input_beds,
            input_baths, input_cars, input_suburb, input_property_type
        FROM property_estimates
        WHERE property_id IN ({})
    '''.format(','.join('?' * len(property_ids))), [now] + property_ids)

    archived_count = cursor.rowcount
    conn.commit()
    return archived_count


def get_for_sale_properties(conn: sqlite3.Connection) -> list:
    """Get all current for-sale properties with their latest data."""
    cursor = conn.cursor()

    # Get latest snapshot for each for-sale property
    query = '''
        SELECT
            h.property_id,
            p.suburb,
            h.beds,
            h.baths,
            h.cars,
            h.land_size,
            h.property_type,
            h.price_value,
            h.price_display,
            p.address
        FROM listing_history h
        JOIN properties p ON h.property_id = p.property_id
        WHERE h.status = 'sale'
        AND h.date = (
            SELECT MAX(date) FROM listing_history
            WHERE property_id = h.property_id AND status = 'sale'
        )
    '''

    cursor.execute(query)
    columns = [desc[0] for desc in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def parse_land_size(land_size_str: str) -> float:
    """Extract numeric land size from string."""
    if not land_size_str or land_size_str in ('na', 'NA', '-', ''):
        return 0
    import re
    match = re.search(r'(\d+(?:\.\d+)?)', str(land_size_str))
    if match:
        return float(match.group(1))
    return 0


def run_estimates(db_path: str, verbose: bool = True):
    """Run ML estimates on all for-sale properties."""

    # Load model
    if verbose:
        print("Loading ML model...")
    model = PropertyValuationModel()
    if not model.load():
        print("Error: Model not found. Run 'python ml/train_model.py' first.")
        sys.exit(1)

    mape = model.metadata.get('metrics', {}).get('mape', 15)

    # Connect to database
    conn = sqlite3.connect(db_path)
    init_estimate_tables(conn)

    # Get for-sale properties
    if verbose:
        print("Loading for-sale properties...")
    properties = get_for_sale_properties(conn)

    if not properties:
        print("No for-sale properties found.")
        conn.close()
        return

    if verbose:
        print(f"Found {len(properties)} for-sale properties")

    # Archive old estimates
    property_ids = [p['property_id'] for p in properties]
    archived = archive_old_estimates(conn, property_ids)
    if verbose and archived > 0:
        print(f"Archived {archived} old estimates to history")

    # Run predictions
    now = datetime.now().isoformat()
    cursor = conn.cursor()

    success_count = 0
    skip_count = 0
    error_count = 0

    if verbose:
        print("\nRunning predictions...")
        print("-" * 70)

    for prop in properties:
        property_id = prop['property_id']

        # Parse inputs
        land_size_raw = parse_land_size(prop.get('land_size'))
        beds = prop.get('beds') or 0
        baths = prop.get('baths') or 0
        cars = prop.get('cars') or 0
        suburb = prop.get('suburb', 'CASTLE HILL')
        property_type = prop.get('property_type', 'house') or 'house'

        # Skip properties without enough data
        if land_size_raw == 0 and beds == 0:
            skip_count += 1
            continue

        # Default beds/baths/cars if missing
        if beds == 0:
            beds = 3
        if baths == 0:
            baths = 2
        if cars == 0:
            cars = 1

        # Determine if we have real land size data
        # For units: land size is N/A, pass None to let model handle it
        # For houses/townhouses: pass real land size if available, else None
        is_unit = property_type and ('unit' in property_type.lower() or
                                      'apartment' in property_type.lower() or
                                      'flat' in property_type.lower())

        if is_unit:
            # Units don't use land size
            land_size_to_use = None
        elif land_size_raw > 0:
            # Real land size from scraped data
            land_size_to_use = land_size_raw
        else:
            # No land size data - let model use defaults
            land_size_to_use = None

        try:
            # Run prediction
            result = model.predict(
                land_size=land_size_to_use,
                beds=beds,
                bathrooms=baths,
                car_spaces=cars,
                suburb=suburb,
                property_type=property_type
            )

            # Get effective land size used by model for storage
            land_size_used = result['input_features'].get('land_size_used', 0)

            # Store estimate
            cursor.execute('''
                INSERT OR REPLACE INTO property_estimates
                (property_id, estimated_price, price_range_low, price_range_high,
                 estimate_date, model_mape, input_land_size, input_beds, input_baths,
                 input_cars, input_suburb, input_property_type)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                property_id,
                int(result['predicted_price']),
                int(result['price_range_low']),
                int(result['price_range_high']),
                now,
                mape,
                land_size_used,
                beds,
                baths,
                cars,
                suburb,
                property_type
            ))

            success_count += 1

            if verbose:
                address = prop.get('address', 'Unknown')[:40]
                asking = prop.get('price_value', 0)
                est = int(result['predicted_price'])
                diff = est - asking if asking > 0 else 0
                diff_pct = (diff / asking * 100) if asking > 0 else 0

                # Show comparison if asking price is known
                if asking > 0:
                    indicator = "+" if diff > 0 else ""
                    print(f"{address:<40} Ask: ${asking:>10,} | Est: ${est:>10,} | {indicator}{diff_pct:>5.1f}%")
                else:
                    print(f"{address:<40} Est: ${est:>10,}")

        except Exception as e:
            error_count += 1
            if verbose:
                print(f"Error for {property_id}: {e}")

    conn.commit()
    conn.close()

    # Summary
    if verbose:
        print("-" * 70)
        print(f"\nSUMMARY")
        print(f"  Estimated:  {success_count}")
        print(f"  Skipped:    {skip_count} (insufficient data)")
        print(f"  Errors:     {error_count}")
        print(f"  Timestamp:  {now}")
        print(f"\nEstimates stored in property_estimates table")
        if archived > 0:
            print(f"Previous estimates archived in property_estimates_history table")


def main():
    parser = argparse.ArgumentParser(
        description="Run ML price estimates on all for-sale properties"
    )
    parser.add_argument(
        "--db",
        type=str,
        default="baulkandcastle_properties.db",
        help="Path to SQLite database"
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress detailed output"
    )

    args = parser.parse_args()

    # Resolve database path
    db_path = Path(args.db)
    if not db_path.is_absolute():
        project_root = Path(__file__).parent.parent
        db_path = project_root / args.db

    if not db_path.exists():
        print(f"Error: Database not found at {db_path}")
        sys.exit(1)

    print("=" * 70)
    print("PROPERTY ESTIMATE CALCULATOR")
    print("Baulkham Hills & Castle Hill")
    print("=" * 70)

    run_estimates(str(db_path), verbose=not args.quiet)


if __name__ == "__main__":
    main()
