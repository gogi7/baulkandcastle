"""
Baulkham Hills & Castle Hill Property Tracker
Automated Domain.com.au tracker with SQLite persistence.

Covers suburbs: Baulkham Hills (2153) & Castle Hill (2154)
Property types: All residential (apartments, townhouses, villas, houses, land, etc.)

Author: Antigravity (for Goran)
"""

import asyncio
import sys
import json
import re
import sqlite3
import argparse
import warnings
from datetime import datetime, timedelta
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional, List, Dict, Any, Set
from bs4 import BeautifulSoup

# Note: Windows event loop policy no longer needed on Python 3.12+

try:
    from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig
    CRAWL4AI_AVAILABLE = True
except ImportError:
    CRAWL4AI_AVAILABLE = False
    # Only exit if we're not just generating reports or running accuracy analysis
    import sys
    if "--reports-only" not in sys.argv and "--accuracy-report" not in sys.argv:
        print("Error: crawl4ai not installed. Run: pip install crawl4ai")
        exit(1)

# --- Configuration ---
TARGET_SUBURBS = ["BAULKHAM HILLS", "CASTLE HILL"]
DB_NAME = "baulkandcastle_properties.db"

# Excelsior Public School catchment URL (Castle Hill area)
EXCELSIOR_CATCHMENT_URL = "https://www.domain.com.au/school-catchment/excelsior-public-school-nsw-2154-637?ptype=apartment-unit-flat,block-of-units,duplex,free-standing,new-apartments,new-home-designs,new-house-land,pent-house,semi-detached,studio,terrace,town-house,villa&ssubs=0"

@dataclass
class PropertyListing:
    id: str
    address: str
    suburb: str  # Will be "BAULKHAM HILLS" or "CASTLE HILL"
    price_display: str
    price_value: int
    bedrooms: int
    bathrooms: int
    parking: int
    land_size: Optional[str]
    property_type: Optional[str] = None  # apartment, house, townhouse, etc.
    price_per_m2: Optional[float] = None
    url: str = ""
    agent: str = ""
    scraped_at: str = ""
    status: str = "sale"  # 'sale' or 'sold'
    sold_date: Optional[str] = None
    sold_date_iso: Optional[str] = None  # ISO format date for ML model
    first_seen: Optional[str] = None

class PropertyDB:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            # Core property table (static info)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS properties (
                    property_id TEXT PRIMARY KEY,
                    address TEXT,
                    suburb TEXT,
                    first_seen TEXT,
                    url TEXT
                )
            ''')
            # History table (dynamic info, unique per property/day/status)
            cursor.execute('''
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
            ''')
            # Add sold_date_iso column if it doesn't exist (for existing databases)
            try:
                cursor.execute('ALTER TABLE listing_history ADD COLUMN sold_date_iso TEXT')
            except sqlite3.OperationalError:
                pass  # Column already exists
            # Add in_excelsior_catchment column if it doesn't exist
            try:
                cursor.execute('ALTER TABLE properties ADD COLUMN in_excelsior_catchment INTEGER DEFAULT 0')
            except sqlite3.OperationalError:
                pass  # Column already exists
            # Daily Summary table (for running history)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS daily_summary (
                    date TEXT PRIMARY KEY,
                    new_count INTEGER,
                    sold_count INTEGER,
                    adj_count INTEGER
                )
            ''')
            # Property Valuations table (for future valuation scraping)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS property_valuations (
                    property_id TEXT PRIMARY KEY,
                    latest_low INTEGER,
                    latest_high INTEGER,
                    propertyvalue_url TEXT,
                    last_updated TEXT
                )
            ''')
            # XGBoost Predictions table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS xgboost_predictions (
                    property_id TEXT PRIMARY KEY,
                    predicted_price INTEGER,
                    price_range_low INTEGER,
                    price_range_high INTEGER,
                    predicted_at TEXT,
                    model_version TEXT
                )
            ''')
            conn.commit()

    def save_listings(self, listings: List[PropertyListing]):
        now = datetime.now()
        today_str = now.strftime('%Y-%m-%d')

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            for l in listings:
                # 1. Update/Insert property core record
                cursor.execute("SELECT first_seen FROM properties WHERE property_id = ?", (l.id,))
                row = cursor.fetchone()
                if not row:
                    l.first_seen = today_str
                    cursor.execute('''
                        INSERT INTO properties (property_id, address, suburb, first_seen, url)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (l.id, l.address, l.suburb, today_str, l.url))
                else:
                    l.first_seen = row[0]

                # 2. For SOLD properties: only insert if not already in database
                # Sold data never changes, so we only need one entry per property
                if l.status == 'sold':
                    cursor.execute('''
                        SELECT 1 FROM listing_history
                        WHERE property_id = ? AND status = 'sold'
                        LIMIT 1
                    ''', (l.id,))
                    if cursor.fetchone():
                        # Already have this sold property, skip it
                        continue

                    # New sold property - insert it
                    cursor.execute('''
                        INSERT INTO listing_history
                        (property_id, date, status, price_display, price_value, beds, baths, cars, land_size, property_type, agent, scraped_at, sold_date, sold_date_iso, price_per_m2)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (l.id, today_str, l.status, l.price_display, l.price_value,
                          l.bedrooms, l.bathrooms, l.parking, l.land_size, l.property_type, l.agent, l.scraped_at, l.sold_date, l.sold_date_iso, l.price_per_m2))
                else:
                    # 3. For SALE properties: daily snapshots (price can change)
                    cursor.execute('''
                        INSERT OR REPLACE INTO listing_history
                        (property_id, date, status, price_display, price_value, beds, baths, cars, land_size, property_type, agent, scraped_at, sold_date, sold_date_iso, price_per_m2)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (l.id, today_str, l.status, l.price_display, l.price_value,
                          l.bedrooms, l.bathrooms, l.parking, l.land_size, l.property_type, l.agent, l.scraped_at, l.sold_date, l.sold_date_iso, l.price_per_m2))
            conn.commit()

    def get_daily_changes(self, target_date: str) -> List[Dict]:
        """Identifies properties with changes today compared to their most recent previous record."""
        changes = []
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # 1. New Properties (first seen today)
            cursor.execute('''
                SELECT p.address, p.url, p.suburb, h.*
                FROM listing_history h
                JOIN properties p ON h.property_id = p.property_id
                WHERE h.date = ? AND p.first_seen = ?
            ''', (target_date, target_date))
            for row in cursor.fetchall():
                changes.append({'type': 'NEW', 'data': dict(row)})

            # 2. Value/Status Changes
            cursor.execute('''
                SELECT h_now.*, p.address, p.url, p.suburb,
                       h_prev.price_display as old_price, h_prev.status as old_status,
                       h_prev.beds as old_beds, h_prev.baths as old_baths, h_prev.cars as old_cars
                FROM listing_history h_now
                JOIN properties p ON h_now.property_id = p.property_id
                JOIN listing_history h_prev ON h_now.property_id = h_prev.property_id
                WHERE h_now.date = ?
                AND h_prev.date = (SELECT MAX(date) FROM listing_history WHERE property_id = h_now.property_id AND date < ?)
                AND (h_now.price_display != h_prev.price_display
                     OR h_now.status != h_prev.status
                     OR h_now.beds != h_prev.beds
                     OR h_now.baths != h_prev.baths
                     OR h_now.cars != h_prev.cars
                     OR h_now.land_size != h_prev.land_size)
            ''', (target_date, target_date))
            for row in cursor.fetchall():
                changes.append({'type': 'ADJUSTMENT', 'data': dict(row)})

        return changes

    def get_comprehensive_daily_changes(self, target_date: str) -> Dict[str, List[Dict]]:
        """Get detailed day-over-day changes, filtering out meaningless capitalization differences."""
        result = {
            'new': [],           # New listings
            'sold': [],          # Properties that changed to sold status
            'disappeared': [],   # Properties that were for sale but no longer appear
            'price_changes': [], # Real price changes (not capitalization)
            'guide_revealed': [] # Auction guides revealed
        }

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Get previous date
            cursor.execute('SELECT MAX(date) FROM listing_history WHERE date < ?', (target_date,))
            prev_row = cursor.fetchone()
            prev_date = prev_row[0] if prev_row else None

            if not prev_date:
                # First day - all are new
                cursor.execute('''
                    SELECT h.*, p.address, p.url, p.suburb
                    FROM listing_history h
                    JOIN properties p ON h.property_id = p.property_id
                    WHERE h.date = ? AND h.status = 'sale'
                ''', (target_date,))
                for row in cursor.fetchall():
                    result['new'].append(dict(row))
                return result

            # 1. NEW listings (first seen today)
            cursor.execute('''
                SELECT h.*, p.address, p.url, p.suburb
                FROM listing_history h
                JOIN properties p ON h.property_id = p.property_id
                WHERE h.date = ? AND p.first_seen = ?
            ''', (target_date, target_date))
            for row in cursor.fetchall():
                result['new'].append(dict(row))

            # 2. Properties that changed to SOLD
            cursor.execute('''
                SELECT h_now.*, p.address, p.url, p.suburb,
                       h_prev.price_display as old_price, h_prev.price_value as old_price_value
                FROM listing_history h_now
                JOIN properties p ON h_now.property_id = p.property_id
                JOIN listing_history h_prev ON h_now.property_id = h_prev.property_id
                WHERE h_now.date = ? AND h_now.status = 'sold'
                AND h_prev.date = ? AND h_prev.status = 'sale'
            ''', (target_date, prev_date))
            for row in cursor.fetchall():
                result['sold'].append(dict(row))

            # 3. DISAPPEARED - were for sale yesterday but not seen today (and not explicitly sold)
            cursor.execute('''
                SELECT h_prev.*, p.address, p.url, p.suburb
                FROM listing_history h_prev
                JOIN properties p ON h_prev.property_id = p.property_id
                WHERE h_prev.date = ? AND h_prev.status = 'sale'
                AND NOT EXISTS (
                    SELECT 1 FROM listing_history h_now
                    WHERE h_now.property_id = h_prev.property_id AND h_now.date = ?
                )
            ''', (prev_date, target_date))
            for row in cursor.fetchall():
                result['disappeared'].append(dict(row))

            # 4. PRICE CHANGES - real price changes (not just capitalization)
            cursor.execute('''
                SELECT h_now.*, p.address, p.url, p.suburb,
                       h_prev.price_display as old_price, h_prev.price_value as old_price_value
                FROM listing_history h_now
                JOIN properties p ON h_now.property_id = p.property_id
                JOIN listing_history h_prev ON h_now.property_id = h_prev.property_id
                WHERE h_now.date = ? AND h_now.status = 'sale'
                AND h_prev.date = ? AND h_prev.status = 'sale'
            ''', (target_date, prev_date))

            for row in cursor.fetchall():
                d = dict(row)
                old_price = (d.get('old_price') or '').strip()
                new_price = (d.get('price_display') or '').strip()
                old_val = d.get('old_price_value') or 0
                new_val = d.get('price_value') or 0

                # Skip if both prices are identical (case-insensitive)
                if old_price.lower() == new_price.lower():
                    continue

                # Check for real value change
                if old_val > 0 and new_val > 0 and old_val != new_val:
                    d['price_diff'] = new_val - old_val
                    result['price_changes'].append(d)
                # Check if auction guide was revealed
                elif old_val == 0 and new_val > 0:
                    result['guide_revealed'].append(d)
                elif new_val == 0 and old_val > 0:
                    # Price hidden (e.g., "Contact Agent")
                    result['price_changes'].append(d)

        return result

    def update_daily_stats(self, target_date: str):
        """Calculates and stores daily metrics in daily_summary table."""
        changes = self.get_daily_changes(target_date)
        new_count = len([c for c in changes if c['type'] == 'NEW'])
        adj_count = len([c for c in changes if c['type'] == 'ADJUSTMENT'])

        # Count "Sold/Disappeared"
        # Properties that were 'sale' yesterday but are not 'sale' today (and not 'sold' today)
        sold_count = 0
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT COUNT(*) FROM listing_history h_prev
                WHERE h_prev.date = (SELECT MAX(date) FROM listing_history WHERE date < ?)
                AND h_prev.status = 'sale'
                AND NOT EXISTS (
                    SELECT 1 FROM listing_history h_now
                    WHERE h_now.property_id = h_prev.property_id
                    AND h_now.date = ?
                )
            ''', (target_date, target_date))
            sold_count = cursor.fetchone()[0]

            # Also include properties that moved to 'sold' status today
            cursor.execute('''
                SELECT COUNT(*) FROM listing_history
                WHERE date = ? AND status = 'sold'
                AND property_id IN (
                    SELECT property_id FROM listing_history
                    WHERE date = (SELECT MAX(date) FROM listing_history WHERE date < ?)
                    AND status = 'sale'
                )
            ''', (target_date, target_date))
            sold_count += cursor.fetchone()[0]

            cursor.execute('''
                INSERT OR REPLACE INTO daily_summary (date, new_count, sold_count, adj_count)
                VALUES (?, ?, ?, ?)
            ''', (target_date, new_count, sold_count, adj_count))
            conn.commit()

    def get_daily_history(self) -> List[Dict]:
        """Gets the history of daily changes."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            return [dict(r) for r in conn.execute("SELECT * FROM daily_summary ORDER BY date DESC").fetchall()]

    def get_latest_listings(self, status: str) -> List[Dict]:
        """Gets the most recent snapshot for all properties of a specific status, including first price, valuation, and XGBoost predictions."""
        query = '''
            SELECT h.*, p.address, p.url, p.first_seen, p.suburb, p.in_excelsior_catchment,
                   (SELECT price_display FROM listing_history WHERE property_id = h.property_id ORDER BY date ASC LIMIT 1) as first_price,
                   v.latest_low, v.latest_high, v.propertyvalue_url,
                   de.estimate_mid as domain_estimate_mid,
                   de.estimate_low as domain_estimate_low,
                   de.estimate_high as domain_estimate_high,
                   de.scraped_at as domain_scraped_at,
                   de.domain_url as domain_profile_url,
                   xp.predicted_price as xgboost_predicted_price,
                   xp.price_range_low as xgboost_price_low,
                   xp.price_range_high as xgboost_price_high,
                   xp.predicted_at as xgboost_predicted_at
            FROM listing_history h
            JOIN properties p ON h.property_id = p.property_id
            LEFT JOIN property_valuations v ON h.property_id = v.property_id
            LEFT JOIN domain_estimates de ON h.property_id = de.property_id
            LEFT JOIN xgboost_predictions xp ON h.property_id = xp.property_id
            WHERE h.status = ?
            AND h.date = (SELECT MAX(date) FROM listing_history WHERE property_id = h.property_id AND status = ?)
        '''
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(query, (status, status)).fetchall()
            return [dict(r) for r in rows]

    def get_stats(self) -> Dict:
        """Calculates basic stats for the summary report."""
        stats = {}
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            # Total unique properties tracked
            stats['total_tracked'] = conn.execute("SELECT COUNT(*) FROM properties").fetchone()[0]
            # Current for sale
            stats['count_sale'] = conn.execute("SELECT COUNT(*) FROM listing_history WHERE status='sale' AND date=(SELECT MAX(date) FROM listing_history)").fetchone()[0]
            # Average price of current for sale (where price > 0)
            avg_price_row = conn.execute("SELECT AVG(price_value) FROM listing_history WHERE status='sale' AND price_value > 0 AND date=(SELECT MAX(date) FROM listing_history)").fetchone()
            stats['avg_price_sale'] = int(avg_price_row[0]) if avg_price_row[0] else 0

            # Stats per suburb
            stats['baulkham_hills_count'] = conn.execute("SELECT COUNT(*) FROM properties WHERE suburb = 'BAULKHAM HILLS'").fetchone()[0]
            stats['castle_hill_count'] = conn.execute("SELECT COUNT(*) FROM properties WHERE suburb = 'CASTLE HILL'").fetchone()[0]
            # Catchment stats
            stats['excelsior_catchment_count'] = conn.execute("SELECT COUNT(*) FROM properties WHERE in_excelsior_catchment = 1").fetchone()[0]
            stats['excelsior_catchment_sale'] = conn.execute("""
                SELECT COUNT(DISTINCT p.property_id) FROM properties p
                JOIN listing_history h ON p.property_id = h.property_id
                WHERE p.in_excelsior_catchment = 1 AND h.status = 'sale'
                AND h.date = (SELECT MAX(date) FROM listing_history)
            """).fetchone()[0]
            stats['excelsior_catchment_sold'] = conn.execute("""
                SELECT COUNT(DISTINCT p.property_id) FROM properties p
                JOIN listing_history h ON p.property_id = h.property_id
                WHERE p.in_excelsior_catchment = 1 AND h.status = 'sold'
            """).fetchone()[0]
        return stats

    def update_catchment_flags(self, catchment_ids: Set[str]) -> Dict[str, Any]:
        """Mark properties that are in the Excelsior catchment.

        Returns:
            Dict with 'updated_count', 'for_sale', 'sold' lists of property details
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            # Reset all to 0
            cursor.execute("UPDATE properties SET in_excelsior_catchment = 0")

            # Set matching properties to 1 and collect details
            updated_ids = []
            for prop_id in catchment_ids:
                cursor.execute(
                    "UPDATE properties SET in_excelsior_catchment = 1 WHERE property_id = ?",
                    (prop_id,)
                )
                if cursor.rowcount > 0:
                    updated_ids.append(prop_id)

            conn.commit()

            # Get details of updated properties with their current status
            result = {
                'updated_count': len(updated_ids),
                'for_sale': [],
                'sold': [],
                'catchment_ids_found': len(catchment_ids),
            }

            if updated_ids:
                # Query property details with latest status from listing_history
                placeholders = ','.join('?' * len(updated_ids))
                cursor.execute(f'''
                    SELECT p.property_id, p.address, p.suburb,
                           (SELECT lh.status FROM listing_history lh
                            WHERE lh.property_id = p.property_id
                            ORDER BY lh.date DESC LIMIT 1) as current_status,
                           (SELECT lh.price_display FROM listing_history lh
                            WHERE lh.property_id = p.property_id
                            ORDER BY lh.date DESC LIMIT 1) as current_price
                    FROM properties p
                    WHERE p.property_id IN ({placeholders})
                    ORDER BY p.suburb, p.address
                ''', tuple(updated_ids))

                for row in cursor.fetchall():
                    prop_info = {
                        'property_id': row[0],
                        'address': row[1],
                        'suburb': row[2],
                        'price': row[4] or 'N/A'
                    }
                    status = row[3] or 'sale'
                    if status == 'sold':
                        result['sold'].append(prop_info)
                    else:
                        result['for_sale'].append(prop_info)

            return result

    def get_catchment_property_ids(self) -> Set[str]:
        """Get all property IDs currently marked as in Excelsior catchment."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT property_id FROM properties WHERE in_excelsior_catchment = 1")
            return {row[0] for row in cursor.fetchall()}

    def get_prediction_accuracy_report(self, days_back: int = 365) -> Dict[str, Any]:
        """Get prediction accuracy comparison for sold properties.

        Compares XGBoost predictions, Domain estimates, and listing prices
        against actual sold prices. Date-aware: only uses predictions/estimates
        made BEFORE the sale date.

        Args:
            days_back: How many days of sold data to analyze

        Returns:
            Dict with accuracy stats and individual property comparisons
        """
        from datetime import datetime, timedelta
        cutoff_date = (datetime.now() - timedelta(days=days_back)).strftime('%Y-%m-%d')

        comparisons = []

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Get all sold properties with valid prices
            cursor.execute('''
                SELECT DISTINCT
                    p.property_id,
                    p.address,
                    p.suburb,
                    h_sold.price_value as sold_price,
                    h_sold.sold_date,
                    h_sold.sold_date_iso,
                    h_sold.date as record_date,
                    h_sold.beds,
                    h_sold.baths,
                    h_sold.cars,
                    h_sold.property_type
                FROM properties p
                JOIN listing_history h_sold ON p.property_id = h_sold.property_id
                WHERE h_sold.status = 'sold'
                AND h_sold.price_value > 0
                ORDER BY h_sold.sold_date_iso DESC, h_sold.date DESC
            ''')

            sold_properties = cursor.fetchall()

            for sold in sold_properties:
                prop_id = sold['property_id']
                sold_price = sold['sold_price']
                sold_date = sold['sold_date']
                sold_date_iso = sold['sold_date_iso'] or sold['record_date']

                comparison = {
                    'property_id': prop_id,
                    'address': sold['address'],
                    'suburb': sold['suburb'],
                    'sold_price': sold_price,
                    'sold_date': sold_date,
                    'sold_date_iso': sold_date_iso,
                    'beds': sold['beds'],
                    'baths': sold['baths'],
                    'cars': sold['cars'],
                    'property_type': sold['property_type'],
                    'listed_price': None,
                    'listed_display': None,
                    'xgboost_price': None,
                    'xgboost_date': None,
                    'domain_estimate': None,
                    'domain_date': None,
                    'listed_error_pct': None,
                    'xgboost_error_pct': None,
                    'domain_error_pct': None,
                }

                # Get listing price (most recent 'sale' record before it sold)
                cursor.execute('''
                    SELECT price_value, price_display, date
                    FROM listing_history
                    WHERE property_id = ? AND status = 'sale'
                    ORDER BY date DESC
                    LIMIT 1
                ''', (prop_id,))
                listing = cursor.fetchone()
                if listing and listing['price_value'] and listing['price_value'] > 0:
                    comparison['listed_price'] = listing['price_value']
                    comparison['listed_display'] = listing['price_display']
                    comparison['listed_error_pct'] = round((listing['price_value'] - sold_price) / sold_price * 100, 1)
                elif listing:
                    comparison['listed_display'] = listing['price_display']

                # Get XGBoost prediction (made before sale date)
                cursor.execute('''
                    SELECT predicted_price, predicted_at
                    FROM xgboost_predictions
                    WHERE property_id = ?
                    ORDER BY predicted_at DESC
                    LIMIT 1
                ''', (prop_id,))
                xgb = cursor.fetchone()
                if xgb and xgb['predicted_price']:
                    comparison['xgboost_price'] = xgb['predicted_price']
                    comparison['xgboost_date'] = xgb['predicted_at'][:10] if xgb['predicted_at'] else None
                    comparison['xgboost_error_pct'] = round((xgb['predicted_price'] - sold_price) / sold_price * 100, 1)

                # Get Domain estimate (made before sale date)
                # First try history table for date-aware lookup
                cursor.execute('''
                    SELECT estimate_mid, scraped_at
                    FROM domain_estimates_history
                    WHERE property_id = ?
                    ORDER BY scraped_at DESC
                    LIMIT 1
                ''', (prop_id,))
                domain = cursor.fetchone()
                if not domain:
                    # Fallback to current estimates table
                    cursor.execute('''
                        SELECT estimate_mid, scraped_at
                        FROM domain_estimates
                        WHERE property_id = ?
                    ''', (prop_id,))
                    domain = cursor.fetchone()

                if domain and domain['estimate_mid']:
                    comparison['domain_estimate'] = domain['estimate_mid']
                    comparison['domain_date'] = domain['scraped_at'][:10] if domain['scraped_at'] else None
                    comparison['domain_error_pct'] = round((domain['estimate_mid'] - sold_price) / sold_price * 100, 1)

                # Only include if we have at least one prediction to compare
                if comparison['listed_price'] or comparison['xgboost_price'] or comparison['domain_estimate']:
                    comparisons.append(comparison)

        # Calculate aggregate statistics
        stats = {
            'total_sold': len(sold_properties),
            'with_comparisons': len(comparisons),
            'listed': {'count': 0, 'total_error': 0, 'errors': []},
            'xgboost': {'count': 0, 'total_error': 0, 'errors': []},
            'domain': {'count': 0, 'total_error': 0, 'errors': []},
        }

        for c in comparisons:
            if c['listed_error_pct'] is not None:
                stats['listed']['count'] += 1
                stats['listed']['total_error'] += abs(c['listed_error_pct'])
                stats['listed']['errors'].append(c['listed_error_pct'])

            if c['xgboost_error_pct'] is not None:
                stats['xgboost']['count'] += 1
                stats['xgboost']['total_error'] += abs(c['xgboost_error_pct'])
                stats['xgboost']['errors'].append(c['xgboost_error_pct'])

            if c['domain_error_pct'] is not None:
                stats['domain']['count'] += 1
                stats['domain']['total_error'] += abs(c['domain_error_pct'])
                stats['domain']['errors'].append(c['domain_error_pct'])

        # Calculate MAPE (Mean Absolute Percentage Error) for each
        for key in ['listed', 'xgboost', 'domain']:
            if stats[key]['count'] > 0:
                stats[key]['mape'] = round(stats[key]['total_error'] / stats[key]['count'], 1)
                # Also calculate median error
                errors = sorted([abs(e) for e in stats[key]['errors']])
                mid = len(errors) // 2
                stats[key]['median_error'] = errors[mid] if errors else 0
            else:
                stats[key]['mape'] = None
                stats[key]['median_error'] = None

        return {
            'comparisons': comparisons,
            'stats': stats
        }

    def get_listings_for_prediction(self, status: str = 'sale') -> List[Dict]:
        """Get current listings with features needed for XGBoost prediction."""
        query = '''
            SELECT h.property_id, p.suburb, h.beds, h.baths, h.cars, h.land_size, h.property_type
            FROM listing_history h
            JOIN properties p ON h.property_id = p.property_id
            WHERE h.status = ?
            AND h.date = (SELECT MAX(date) FROM listing_history WHERE property_id = h.property_id AND status = ?)
        '''
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(query, (status, status)).fetchall()
            return [dict(r) for r in rows]

    def save_xgboost_predictions(self, predictions: List[Dict], model_version: str = None):
        """Save XGBoost predictions to database."""
        now = datetime.now().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            for pred in predictions:
                cursor.execute('''
                    INSERT OR REPLACE INTO xgboost_predictions
                    (property_id, predicted_price, price_range_low, price_range_high, predicted_at, model_version)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    pred['property_id'],
                    pred['predicted_price'],
                    pred.get('price_range_low'),
                    pred.get('price_range_high'),
                    now,
                    model_version
                ))
            conn.commit()
            return len(predictions)

class BaulkandcastleScraper:
    BASE_URL = "https://www.domain.com.au"

    # URLs with multiple suburbs and all residential property types
    URL_SALE = "https://www.domain.com.au/sale/?suburb=baulkham-hills-nsw-2153,castle-hill-nsw-2154&ptype=apartment-unit-flat,block-of-units,development-site,duplex,free-standing,new-apartments,new-home-designs,new-house-land,new-land,pent-house,semi-detached,studio,terrace,town-house,vacant-land,villa&ssubs=0"

    URL_SOLD = "https://www.domain.com.au/sold-listings/?suburb=baulkham-hills-nsw-2153,castle-hill-nsw-2154&ptype=apartment-unit-flat,block-of-units,development-site,duplex,free-standing,new-apartments,new-home-designs,new-house-land,new-land,pent-house,semi-detached,studio,terrace,town-house,vacant-land,villa&ssubs=0"

    # Month name to number mapping for date parsing
    MONTH_MAP = {
        'jan': '01', 'feb': '02', 'mar': '03', 'apr': '04',
        'may': '05', 'jun': '06', 'jul': '07', 'aug': '08',
        'sep': '09', 'oct': '10', 'nov': '11', 'dec': '12'
    }

    def __init__(self):
        self.db = PropertyDB(DB_NAME)
        self.listings: List[PropertyListing] = []
        self.mode = "sale"
        self.total_count_text = "Unknown"

    def _convert_to_iso_date(self, date_str: str) -> Optional[str]:
        """Convert 'DD MMM YYYY' or ISO format to 'YYYY-MM-DD' ISO format."""
        if not date_str:
            return None
        try:
            # Already in ISO format
            if 'T' in date_str:
                return date_str.split('T')[0]
            if re.match(r'^\d{4}-\d{2}-\d{2}', date_str):
                return date_str[:10]
            # Parse "DD MMM YYYY" format
            match = re.match(r'(\d{1,2})\s+([A-Za-z]{3})\s+(\d{4})', date_str)
            if match:
                day = match.group(1).zfill(2)
                month = self.MONTH_MAP.get(match.group(2).lower())
                year = match.group(3)
                if month:
                    return f"{year}-{month}-{day}"
        except Exception:
            pass
        return None

    def _extract_price_value(self, price_text: str) -> int:
        if not price_text: return 0
        nums = re.findall(r'\d{1,3}(?:,\d{3})*', price_text)
        if nums:
            try:
                val = int(nums[0].replace(',', ''))
                if val > 100_000: return val
            except: pass
        return 0

    def _extract_property_type(self, model: dict, item: dict) -> Optional[str]:
        """Extract property type from listing data."""
        prop_type = model.get('propertyType') or item.get('propertyType') or ''
        if not prop_type:
            # Try from features or other fields
            prop_type = model.get('features', {}).get('propertyType', '')
        return prop_type.lower() if prop_type else None

    def parse_domain_data(self, html: str) -> List[PropertyListing]:
        parsed = []
        soup = BeautifulSoup(html, 'html.parser')
        script = soup.find('script', id='__NEXT_DATA__')

        if not script: return []

        try:
            data = json.loads(script.get_text())
            listings_map = data.get('props', {}).get('pageProps', {}).get('componentProps', {}).get('listingsMap', {})

            if not listings_map: return []

            for lid, item in listings_map.items():
                model = item.get('listingModel') or {}
                address_obj = model.get('address') or item.get('address') or {}
                suburb = address_obj.get('suburb', '').upper()

                # Filter for target suburbs
                if suburb not in TARGET_SUBURBS:
                    continue

                # Address Building
                street = address_obj.get('street', '')
                unit = address_obj.get('unitNumber', '')
                st_num = address_obj.get('streetNumber', '')
                addr_parts = [f"{unit}/" if unit else "", st_num if st_num else "", street, suburb.title()]
                full_address = " ".join(filter(None, addr_parts)).replace("/ ", "/")
                if not street or len(street) < 3:
                    full_address = model.get('headline') or item.get('headline') or model.get('displayAddress') or item.get('displayAddress') or full_address

                # Property Type
                prop_type = self._extract_property_type(model, item)

                # Price & Sold Date
                sold_date_str = None
                if self.mode == 'sale':
                    price_disp = model.get('price') or item.get('price') or "Contact Agent"
                else:
                    price_disp = model.get('price') or model.get('soldPrice') or item.get('soldPrice') or "Price Withheld"
                    tags = model.get('tags', {})
                    tag_text = tags.get('tagText', '')
                    date_match = re.search(r'(\d{2} [A-Z][a-z]{2} \d{4})', tag_text)
                    sold_date_str = date_match.group(1) if date_match else (model.get('soldDate') or item.get('soldDate'))

                    if not self._is_recent_sale(sold_date_str): continue

                price_val = self._extract_price_value(price_disp)
                if self.mode == 'sold' and sold_date_str:
                    price_disp = f"{price_disp} ({sold_date_str})"

                # Features (Beds, Baths, Cars - separate as requested)
                feats = model.get('features') or item.get('features') or {}
                beds = int(feats.get('beds', 0))
                baths = int(feats.get('baths', 0))
                cars = int(feats.get('parking', 0))

                # Land Size with regex fallback
                land = feats.get('landSize', 0)
                land_unit = feats.get('landUnit', 'm²')
                land_str = f"{land}{land_unit}" if land and land > 0 else None

                if not land_str:
                    # Fallback to headline or description
                    text_to_search = (model.get('headline') or item.get('headline') or "") + " " + (item.get('summaryDescription') or "")
                    land_match = re.search(r'(\d{2,4})\s*(?:m2|m\u00b2)', text_to_search, re.IGNORECASE)
                    if land_match:
                        land_str = f"{land_match.group(1)}m²"
                    else:
                        land_str = "na"

                # Calculate Price Per m2
                price_per_m2 = None
                if price_val > 0 and land_str and land_str != "na":
                    land_match = re.search(r'(\d+(?:\.\d+)?)', land_str)
                    if land_match:
                        try:
                            l_size = float(land_match.group(1))
                            if l_size > 0:
                                price_per_m2 = round(price_val / l_size, 2)
                        except: pass

                # URL
                url_snippet = model.get('url') or item.get('seoUrl') or ""
                url = f"https://www.domain.com.au{url_snippet}" if url_snippet and not url_snippet.startswith('http') else (url_snippet or f"https://www.domain.com.au/property-{lid}")

                # Agent
                agent = model.get('branding', {}).get('agentName') or item.get('agentName') or 'Domain'

                # Compute ISO format date for ML model
                sold_date_iso = self._convert_to_iso_date(sold_date_str) if sold_date_str else None

                l = PropertyListing(
                    id=lid,
                    address=full_address,
                    suburb=suburb,  # Store actual suburb
                    price_display=price_disp,
                    price_value=price_val,
                    bedrooms=beds,
                    bathrooms=baths,
                    parking=cars,
                    land_size=land_str,
                    property_type=prop_type,
                    price_per_m2=price_per_m2,
                    url=url,
                    agent=agent,
                    scraped_at=datetime.now().isoformat(),
                    status=self.mode,
                    sold_date=sold_date_str,
                    sold_date_iso=sold_date_iso
                )
                parsed.append(l)

        except Exception as e:
            print(f"   Error parsing JSON: {e}")

        return parsed

    def _is_recent_sale(self, date_str: str) -> bool:
        if not date_str: return True
        try:
            dt = None
            if 'T' in date_str: dt = datetime.fromisoformat(date_str.split('T')[0])
            else:
                try: dt = datetime.strptime(date_str, "%d %b %Y")
                except: pass
            if not dt: return True
            return dt >= (datetime.now() - timedelta(days=365))  # Keep 1 year of sold data
        except: return True

    def parse_catchment_property_ids(self, html: str) -> Set[str]:
        """Extract just property IDs from a catchment page (no full parsing needed)."""
        property_ids = set()
        soup = BeautifulSoup(html, 'html.parser')
        script = soup.find('script', id='__NEXT_DATA__')

        if not script:
            return property_ids

        try:
            data = json.loads(script.get_text())
            listings_map = data.get('props', {}).get('pageProps', {}).get('componentProps', {}).get('listingsMap', {})

            if listings_map:
                property_ids.update(listings_map.keys())
        except Exception as e:
            print(f"   Error parsing catchment JSON: {e}")

        return property_ids

    async def scrape_catchment_property_ids(self, crawler) -> tuple:
        """Scrape Excelsior catchment to get list of property IDs.
        Returns tuple of (property_ids, pages_scraped, elapsed_str)."""
        property_ids = set()
        page = 1
        max_pages = 50  # Safety limit
        pages_scraped = 0
        start_time = datetime.now()

        print("\nScraping Excelsior catchment property IDs...")

        while page <= max_pages:
            url = EXCELSIOR_CATCHMENT_URL + (f"&page={page}" if page > 1 else "")
            print(f"   Catchment page {page}...")

            result = await crawler.arun(url, config=CrawlerRunConfig(cache_mode="BYPASS", magic=True, delay_before_return_html=2.0))

            if not result.success:
                print(f"   Failed to fetch page {page}")
                break

            pages_scraped += 1
            new_ids = self.parse_catchment_property_ids(result.html)

            if not new_ids:
                print(f"   No more properties found on page {page}")
                break

            property_ids.update(new_ids)
            print(f"   Found {len(new_ids)} properties (total: {len(property_ids)})")
            page += 1
            await asyncio.sleep(2)

        elapsed = datetime.now() - start_time
        elapsed_str = str(elapsed).split('.')[0]

        return property_ids, pages_scraped, elapsed_str

    async def scrape_mode(self, crawler, mode: str, max_pages: int = 30):
        self.mode = mode
        self.listings = []
        page = 1
        empty_pages = 0
        pages_scraped = 0
        start_time = datetime.now()

        base_url = self.URL_SALE if mode == 'sale' else self.URL_SOLD
        print(f"\nScraping {mode.upper()} listings...")

        while page <= max_pages:
            url = base_url + (f"&page={page}" if page > 1 else "")
            print(f"   Page {page}...")
            result = await crawler.arun(url, config=CrawlerRunConfig(cache_mode="BYPASS", magic=True, delay_before_return_html=2.0))

            if not result.success: break

            pages_scraped += 1
            new_listings = self.parse_domain_data(result.html)
            if not new_listings:
                empty_pages += 1
                if empty_pages >= 2: break
            else:
                empty_pages = 0
                self.listings.extend(new_listings)
                if page == 1:
                    # Auto-detect total pages from "X properties" text
                    soup = BeautifulSoup(result.html, 'html.parser')
                    text = soup.get_text()
                    match = re.search(r'([\d,]+)\s+properties', text, re.IGNORECASE)
                    if match:
                        total = int(match.group(1).replace(',', ''))
                        detected_pages = (total + 19) // 20
                        if mode == 'sale':
                            # For sale: scrape all available pages (no hard cap)
                            max_pages = detected_pages
                            print(f"   Detected {total} properties across ~{detected_pages} pages")
                        else:
                            # For sold: use min of detected or requested pages
                            max_pages = min(detected_pages, max_pages)
                            print(f"   Detected {total} properties, scraping up to {max_pages} pages")

            page += 1
            await asyncio.sleep(2)

        elapsed = datetime.now() - start_time
        elapsed_str = str(elapsed).split('.')[0]  # Remove microseconds

        self.db.save_listings(self.listings)
        print(f"   Processed {len(self.listings)} {mode} listings across {pages_scraped} pages in {elapsed_str}")

        # Return stats for summary
        return {'mode': mode, 'listings': len(self.listings), 'pages': pages_scraped, 'elapsed': elapsed_str, 'elapsed_seconds': elapsed.total_seconds()}

    async def run_all(self, sold_pages: int = 30):
        total_start = datetime.now()
        stats = []

        browser_conf = BrowserConfig(headless=True, user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        async with AsyncWebCrawler(config=browser_conf) as crawler:
            sale_stats = await self.scrape_mode(crawler, 'sale')
            stats.append(sale_stats)

            sold_stats = await self.scrape_mode(crawler, 'sold', sold_pages)
            stats.append(sold_stats)

            # Auto-update catchment flags after full scrape
            print("\nUpdating Excelsior catchment flags...")
            catchment_ids, catchment_pages, catchment_elapsed = await self.scrape_catchment_property_ids(crawler)
            updated = self.db.update_catchment_flags(catchment_ids)
            print(f"   Found {len(catchment_ids)} properties in Excelsior catchment")
            print(f"   Marked {updated} existing properties as in catchment")

        today = datetime.now().strftime('%Y-%m-%d')
        self.db.update_daily_stats(today)

        self.generate_all_reports()
        self.print_terminal_summary()
        self.output_json_summary()

        # Print scrape summary
        total_elapsed = datetime.now() - total_start
        total_elapsed_str = str(total_elapsed).split('.')[0]
        total_pages = sum(s['pages'] for s in stats) + catchment_pages
        total_listings = sum(s['listings'] for s in stats)

        print(f"\n{'='*60}")
        print("SCRAPE SUMMARY")
        print(f"{'='*60}")
        for s in stats:
            print(f"  {s['mode'].upper():6}: {s['pages']:3} pages, {s['listings']:5} listings ({s['elapsed']})")
        print(f"  {'CATCH':6}: {catchment_pages:3} pages, {len(catchment_ids):5} properties ({catchment_elapsed})")
        print(f"  {'TOTAL':6}: {total_pages:3} pages, {total_listings:5} listings")
        print(f"{'='*60}")
        print(f"Total time: {total_elapsed_str}")
        print(f"{'='*60}")

    async def run_daily(self, sale_pages: int = 1, sold_pages: int = 1):
        """Quick daily scan with configurable page limits."""
        total_start = datetime.now()
        stats = []

        browser_conf = BrowserConfig(headless=True, user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        async with AsyncWebCrawler(config=browser_conf) as crawler:
            # Scrape sale listings
            sale_stats = await self.scrape_mode(crawler, 'sale', max_pages=sale_pages)
            stats.append(sale_stats)
            # Scrape sold listings
            sold_stats = await self.scrape_mode(crawler, 'sold', max_pages=sold_pages)
            stats.append(sold_stats)

        today = datetime.now().strftime('%Y-%m-%d')
        self.db.update_daily_stats(today)

        self.generate_all_reports()
        self.print_terminal_summary()
        self.output_json_summary()

        # Print scrape summary
        total_elapsed = datetime.now() - total_start
        total_elapsed_str = str(total_elapsed).split('.')[0]
        total_pages = sum(s['pages'] for s in stats)
        total_listings = sum(s['listings'] for s in stats)

        print(f"\n{'='*60}")
        print("SCRAPE SUMMARY (DAILY MODE)")
        print(f"{'='*60}")
        for s in stats:
            print(f"  {s['mode'].upper():6}: {s['pages']:3} pages, {s['listings']:5} listings ({s['elapsed']})")
        print(f"  {'TOTAL':6}: {total_pages:3} pages, {total_listings:5} listings")
        print(f"{'='*60}")
        print(f"Total time: {total_elapsed_str}")
        print(f"{'='*60}")

    async def run_update_catchment(self):
        """Update catchment flags only (no property scraping)."""
        browser_conf = BrowserConfig(headless=True, user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        async with AsyncWebCrawler(config=browser_conf) as crawler:
            print("Updating Excelsior catchment flags...")
            catchment_ids, pages_scraped, elapsed = await self.scrape_catchment_property_ids(crawler)
            result = self.db.update_catchment_flags(catchment_ids)

        # Print detailed summary
        print("\n" + "=" * 60)
        print("EXCELSIOR CATCHMENT UPDATE")
        print("=" * 60)
        print(f"Pages scraped: {pages_scraped} ({elapsed})")
        print(f"Properties found on Domain catchment page: {result['catchment_ids_found']}")
        print(f"Properties matched in database: {result['updated_count']}")
        print(f"  - For Sale: {len(result['for_sale'])}")
        print(f"  - Sold: {len(result['sold'])}")
        print("-" * 60)

        if result['for_sale']:
            print("\nFOR SALE IN EXCELSIOR CATCHMENT:")
            for p in result['for_sale']:
                print(f"  {p['address']} ({p['suburb']}) - {p['price']}")

        if result['sold']:
            print("\nSOLD IN EXCELSIOR CATCHMENT:")
            for p in result['sold']:
                print(f"  {p['address']} ({p['suburb']}) - {p['price']}")

        print("=" * 60)

        self.generate_all_reports()
        print(f"\n[CATCHMENT UPDATE] Reports regenerated with catchment flags")

        # Output JSON summary for API
        self._output_catchment_json_summary(result)

    def _output_catchment_json_summary(self, result: Dict[str, Any]):
        """Output JSON summary for catchment update."""
        summary = {
            "catchment_summary": {
                "date": datetime.now().strftime('%Y-%m-%d'),
                "catchment_ids_found": result['catchment_ids_found'],
                "properties_marked": result['updated_count'],
                "for_sale_count": len(result['for_sale']),
                "sold_count": len(result['sold']),
                "for_sale": [
                    {"address": p['address'], "suburb": p['suburb'], "price": p['price']}
                    for p in result['for_sale']
                ],
                "sold": [
                    {"address": p['address'], "suburb": p['suburb'], "price": p['price']}
                    for p in result['sold']
                ],
            },
            "status": "success"
        }
        print("---JSON_SUMMARY_START---")
        print(json.dumps(summary))
        print("---JSON_SUMMARY_END---")
        sys.stdout.flush()

    def print_terminal_summary(self):
        today = datetime.now().strftime('%Y-%m-%d')
        changes = self.db.get_daily_changes(today)
        history = self.db.get_daily_history()

        print("\n" + "="*60)
        print(f"DAILY CHANGES SUMMARY ({today})")
        print("Baulkham Hills & Castle Hill Property Tracker")
        print("="*60)

        if history:
            h = history[0]
            print(f"STATS TODAY: {h['new_count']} New, {h['sold_count']} Sold/Gone, {h['adj_count']} Adjusted")
            print("-" * 60)

        if not changes:
            print("No changes detected today.")
        else:
            for c in changes:
                t = c['type']
                d = c['data']
                addr = d['address']
                suburb = d.get('suburb', 'Unknown')
                agent = d.get('agent', 'Unknown')
                beds = d.get('beds', '-')
                baths = d.get('baths', '-')
                cars = d.get('cars', '-')

                print(f"[{t}] {addr} ({suburb})")
                if t == 'NEW':
                    print(f"      Price: {d['price_display']}")
                else:
                    print(f"      Price: {d['old_price']} -> {d['price_display']}")
                    if d['status'] != d['old_status']:
                        print(f"      Status: {d['old_status']} -> {d['status']}")

                print(f"      Specs: {beds}b {baths}b {cars}c")
                print(f"      Agent: {agent}")
                print("-" * 30)
        print("="*60 + "\n")

    def output_json_summary(self):
        """Output structured JSON summary for API parsing.

        Outputs a JSON block between markers that the API can parse
        to extract structured data about the scrape results.
        """
        today = datetime.now().strftime('%Y-%m-%d')
        history = self.db.get_daily_history()
        stats = self.db.get_stats()

        # Get today's daily summary counts
        daily_counts = {"new_count": 0, "sold_count": 0, "adjusted_count": 0}
        if history:
            h = history[0]
            if h.get('date') == today:
                daily_counts = {
                    "new_count": h.get('new_count', 0),
                    "sold_count": h.get('sold_count', 0),
                    "adjusted_count": h.get('adj_count', 0),
                }

        # Get detailed changes for this scrape
        detailed_changes = self.db.get_comprehensive_daily_changes(today)

        # Also get raw adjustments from get_daily_changes for complete picture
        raw_changes = self.db.get_daily_changes(today)

        # Format new listings (simplified for JSON)
        new_listings = []
        for item in detailed_changes.get('new', []):
            new_listings.append({
                "address": item.get('address', ''),
                "suburb": item.get('suburb', ''),
                "price": item.get('price_display', ''),
                "price_value": item.get('price_value', 0),
                "beds": item.get('beds', 0),
                "baths": item.get('baths', 0),
                "cars": item.get('cars', 0),
                "property_type": item.get('property_type', ''),
            })

        # Format sold/disappeared
        sold_gone = []
        for item in detailed_changes.get('sold', []) + detailed_changes.get('disappeared', []):
            sold_gone.append({
                "address": item.get('address', ''),
                "suburb": item.get('suburb', ''),
                "price": item.get('price_display', ''),
                "price_value": item.get('price_value', 0),
                "type": "sold" if item in detailed_changes.get('sold', []) else "disappeared",
            })

        # Format price changes
        price_changes = []
        for item in detailed_changes.get('price_changes', []):
            price_changes.append({
                "address": item.get('address', ''),
                "suburb": item.get('suburb', ''),
                "old_price": item.get('old_price', ''),
                "new_price": item.get('price_display', ''),
                "old_value": item.get('old_price_value', 0),
                "new_value": item.get('price_value', 0),
                "diff": item.get('price_diff', 0),
            })

        # Format guide revealed
        guides_revealed = []
        for item in detailed_changes.get('guide_revealed', []):
            guides_revealed.append({
                "address": item.get('address', ''),
                "suburb": item.get('suburb', ''),
                "old_price": item.get('old_price', ''),
                "new_price": item.get('price_display', ''),
                "price_value": item.get('price_value', 0),
            })

        # Format ALL adjustments from raw changes (includes things like agent/status text changes)
        all_adjustments = []
        for change in raw_changes:
            if change.get('type') == 'ADJUSTMENT':
                data = change.get('data', {})
                all_adjustments.append({
                    "address": data.get('address', ''),
                    "suburb": data.get('suburb', ''),
                    "old_price": data.get('old_price', ''),
                    "new_price": data.get('price_display', ''),
                    "old_status": data.get('old_status', ''),
                    "new_status": data.get('status', ''),
                })

        # Build summary object
        summary = {
            "scraper_summary": {
                "date": today,
                "daily_changes": daily_counts,
                "current_stats": {
                    "total_for_sale": stats.get('count_sale', 0),
                    "avg_price": stats.get('avg_price_sale', 0),
                    "total_tracked": stats.get('total_tracked', 0),
                    "baulkham_hills_count": stats.get('baulkham_hills_count', 0),
                    "castle_hill_count": stats.get('castle_hill_count', 0),
                    "excelsior_catchment_sale": stats.get('excelsior_catchment_sale', 0),
                },
                "details": {
                    "new_listings": new_listings,
                    "sold_gone": sold_gone,
                    "price_changes": price_changes,
                    "guides_revealed": guides_revealed,
                    "all_adjustments": all_adjustments,
                },
                "status": "success"
            }
        }

        # Output with markers for API parsing
        print("---JSON_SUMMARY_START---")
        print(json.dumps(summary))
        print("---JSON_SUMMARY_END---")
        sys.stdout.flush()  # Force flush to ensure subprocess captures output

    def generate_all_reports(self):
        self.generate_html_report('sale')
        self.generate_html_report('sold')
        self.generate_summary_report()
        self.generate_timeline_report()

    def generate_html_report(self, mode: str):
        recent_listings = self.db.get_latest_listings(mode)
        filename = f"baulkandcastle_{mode}_matches.html"

        html = f"""
        <html><head><title>Baulkham Hills & Castle Hill - {mode.title()}</title>
        <style>
            body {{ font-family: sans-serif; background: #f4f4f9; padding: 20px; }}
            .container {{ background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
            th, td {{ padding: 10px; border-bottom: 1px solid #ddd; text-align: left; }}
            th {{ background: #eee; position: sticky; top: 0; }}
            .price {{ font-weight: bold; color: green; }}
            .ppm2 {{ color: #666; font-size: 0.9em; }}
            .new {{ color: blue; font-weight: bold; font-size: 0.8em; }}
            .suburb-bh {{ background: #e3f2fd; }}
            .suburb-ch {{ background: #fff3e0; }}
            .catchment-yes {{ color: #34a853; font-weight: bold; }}
            .catchment-no {{ color: #999; }}
            .filter-controls {{ margin: 15px 0; padding: 10px; background: #f8f9fa; border-radius: 5px; display: flex; align-items: center; gap: 15px; }}
            .filter-controls label {{ cursor: pointer; user-select: none; }}
            .filter-controls input[type="checkbox"] {{ margin-right: 5px; }}
            tr.hidden {{ display: none; }}
        </style>
        <script>
            function toggleCatchmentFilter() {{
                const checkbox = document.getElementById('catchmentFilter');
                const rows = document.querySelectorAll('tbody tr');
                rows.forEach(row => {{
                    if (checkbox.checked) {{
                        const catchmentCell = row.querySelector('.catchment-cell');
                        if (catchmentCell && catchmentCell.dataset.catchment === '0') {{
                            row.classList.add('hidden');
                        }}
                    }} else {{
                        row.classList.remove('hidden');
                    }}
                }});
                updateCount();
            }}
            function updateCount() {{
                const visibleRows = document.querySelectorAll('tbody tr:not(.hidden)').length;
                const totalRows = document.querySelectorAll('tbody tr').length;
                document.getElementById('rowCount').textContent = `Showing ${{visibleRows}} of ${{totalRows}} properties`;
            }}
            window.onload = function() {{ updateCount(); }};
        </script>
        </head>
        <body><div class="container">
            <h1>Baulkham Hills & Castle Hill: {mode.title()}</h1>
            <p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            <div class="filter-controls">
                <label><input type="checkbox" id="catchmentFilter" onchange="toggleCatchmentFilter()"> Show only Excelsior catchment</label>
                <span id="rowCount"></span>
            </div>
            <table><thead><tr>
                <th>Suburb</th><th>Excelsior</th><th>Address</th><th>Type</th><th>Price (First Seen)</th><th>Price (Latest)</th><th>$ / m2</th><th>Beds</th><th>Baths</th><th>Cars</th>
                <th>Land</th><th>Agent</th>{"<th>Sold Date</th>" if mode=='sold' else ""}
                <th>XGBoost Predict</th>
                <th>Domain Estimate</th>
                <th>Domain Profile</th>
                <th>First Seen</th><th>Latest Scrape</th><th>Link</th>
            </tr></thead><tbody>"""

        # If sold, order by date descending
        if mode == 'sold':
            def parse_sort_date(date_str):
                if not date_str: return datetime.min
                try:
                    if 'T' in date_str: return datetime.fromisoformat(date_str.split('T')[0])
                    return datetime.strptime(date_str, "%d %b %Y")
                except: return datetime.min

            recent_listings.sort(key=lambda x: parse_sort_date(x['sold_date']), reverse=True)

        for l in recent_listings:
            is_new = " <span class='new'>[NEW]</span>" if l['first_seen'] == datetime.now().strftime('%Y-%m-%d') else ""

            # Highlight if price changed
            price_style = "color: green; font-weight: bold;"
            if l['first_price'] and l['first_price'] != l['price_display']:
                price_style = "color: #d93025; font-weight: bold;" # Red for adjustment

            # Suburb styling
            suburb = l.get('suburb', 'Unknown')
            suburb_class = "suburb-bh" if "BAULKHAM" in suburb else "suburb-ch"
            suburb_display = "Baulkham Hills" if "BAULKHAM" in suburb else "Castle Hill"

            # Property type display
            prop_type = l.get('property_type') or '-'

            # XGBoost Prediction
            if l.get('xgboost_predicted_price'):
                xgboost_date = ""
                if l.get('xgboost_predicted_at'):
                    try:
                        pred_date = l['xgboost_predicted_at'][:10]
                        xgboost_date = f"<br><span style='font-size:0.8em;color:#666;'>({pred_date})</span>"
                    except:
                        pass
                xgboost_prediction = f"${l['xgboost_predicted_price']:,}{xgboost_date}"
            else:
                xgboost_prediction = "-"

            # Domain Estimate
            if l.get('domain_estimate_mid'):
                domain_date = ""
                if l.get('domain_scraped_at'):
                    try:
                        scraped = l['domain_scraped_at'][:10]
                        domain_date = f"<br><span style='font-size:0.8em;color:#666;'>({scraped})</span>"
                    except:
                        pass
                domain_estimate = f"${l['domain_estimate_mid']:,}{domain_date}"
            else:
                domain_estimate = "-"

            # Domain Profile Link
            if l.get('domain_profile_url'):
                domain_profile_link = f"<a href='{l['domain_profile_url']}' target='_blank'>View Profile</a>"
            else:
                domain_profile_link = "-"

            # Excelsior catchment flag
            in_catchment = l.get('in_excelsior_catchment', 0)
            catchment_display = "<span class='catchment-yes'>&#10003;</span>" if in_catchment else "<span class='catchment-no'>-</span>"

            html += f"""
            <tr class="{suburb_class}">
                <td>{suburb_display}</td>
                <td class="catchment-cell" data-catchment="{in_catchment}">{catchment_display}</td>
                <td>{l['address']}{is_new}</td>
                <td>{prop_type}</td>
                <td>{l['first_price'] or l['price_display']}</td>
                <td style="{price_style}">{l['price_display']}</td>
                <td class="ppm2">{f"${l['price_per_m2']:,.2f}" if l.get('price_per_m2') else "-"}</td>
                <td>{l['beds']}</td><td>{l['baths']}</td><td>{l['cars']}</td>
                <td>{l['land_size']}</td>
                <td>{l['agent']}</td>
                {"<td>"+(l['sold_date'] or '-')+"</td>" if mode=='sold' else ""}
                <td>{xgboost_prediction}</td>
                <td>{domain_estimate}</td>
                <td>{domain_profile_link}</td>
                <td>{l['first_seen']}</td>
                <td>{l['scraped_at'][:16].replace('T', ' ')}</td>
                <td><a href="{l['url']}" target="_blank">View</a></td>
            </tr>"""

        html += "</tbody></table></div></body></html>"
        with open(filename, 'w', encoding='utf-8') as f: f.write(html)
        print(f"Generated {filename}")

    def generate_summary_report(self):
        stats = self.db.get_stats()
        filename = "baulkandcastle_summary.html"

        html = f"""
        <html><head><title>Baulkham Hills & Castle Hill Property Market Dashboard</title>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            * {{ margin: 0; padding: 0; box-sizing: border-box; }}
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                padding: 20px;
                line-height: 1.6;
            }}
            .dashboard {{
                width: 90%;
                max-width: 1400px;
                margin: 0 auto;
                background: white;
                border-radius: 15px;
                box-shadow: 0 20px 40px rgba(0,0,0,0.1);
                overflow: hidden;
            }}
            .header {{
                background: linear-gradient(135deg, #1a73e8 0%, #4285f4 100%);
                color: white;
                padding: 30px 40px;
                text-align: center;
            }}
            .header h1 {{
                font-size: 2.5em;
                margin-bottom: 10px;
                font-weight: 300;
                text-shadow: 0 2px 4px rgba(0,0,0,0.3);
            }}
            .header p {{
                font-size: 1.1em;
                opacity: 0.9;
                margin-bottom: 0;
            }}
            .content {{ padding: 40px; }}
            .stats-grid {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 25px;
                margin-bottom: 40px;
            }}
            .stat-card {{
                background: linear-gradient(135deg, #f8f9ff 0%, #e3f2fd 100%);
                padding: 25px;
                border-radius: 12px;
                border-left: 5px solid #1a73e8;
                box-shadow: 0 4px 15px rgba(0,0,0,0.08);
                transition: transform 0.3s ease;
            }}
            .stat-card:hover {{ transform: translateY(-2px); }}
            .stat-card.bh {{ border-left-color: #2196f3; }}
            .stat-card.ch {{ border-left-color: #ff9800; }}
            .stat-card.excelsior {{ border-left-color: #34a853; }}
            .stat-card.excelsior .stat-value {{ color: #34a853; }}
            .stat-card .stat-breakdown {{ font-size: 0.75em; color: #666; margin-top: 8px; }}
            .stat-label {{
                font-weight: 600;
                color: #555;
                font-size: 0.9em;
                text-transform: uppercase;
                letter-spacing: 0.5px;
                margin-bottom: 10px;
            }}
            .stat-value {{
                font-size: 2.2em;
                font-weight: 700;
                color: #1a73e8;
                line-height: 1;
            }}
            .section {{
                margin-bottom: 50px;
                background: #fafbfc;
                border-radius: 12px;
                padding: 30px;
                border: 1px solid #e1e8ed;
            }}
            .section-title {{
                font-size: 1.8em;
                color: #1a73e8;
                margin-bottom: 25px;
                font-weight: 600;
                display: flex;
                align-items: center;
            }}
            .section-title:before {{
                content: '';
                width: 4px;
                height: 30px;
                background: #1a73e8;
                margin-right: 15px;
                border-radius: 2px;
            }}
            .summary-table {{
                width: 100%;
                border-collapse: collapse;
                margin-top: 15px;
                background: white;
                border-radius: 8px;
                overflow: hidden;
                box-shadow: 0 4px 15px rgba(0,0,0,0.05);
            }}
            .summary-table th {{
                background: linear-gradient(135deg, #1a73e8 0%, #4285f4 100%);
                color: white;
                padding: 15px 12px;
                text-align: center;
                font-weight: 600;
                font-size: 0.9em;
                border: none;
            }}
            .summary-table td {{
                padding: 12px;
                text-align: center;
                border-bottom: 1px solid #e1e8ed;
                font-size: 0.85em;
                vertical-align: top;
            }}
            .summary-table tr:hover {{ background: #f8f9ff; }}
            .summary-table tr:last-child td {{ border-bottom: none; }}
            .btn-container {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
                gap: 20px;
                margin-top: 40px;
            }}
            .btn {{
                display: block;
                text-align: center;
                padding: 15px 25px;
                color: white;
                text-decoration: none;
                border-radius: 8px;
                font-weight: 600;
                transition: all 0.3s ease;
                box-shadow: 0 4px 15px rgba(0,0,0,0.2);
            }}
            .btn:hover {{
                transform: translateY(-2px);
                box-shadow: 0 8px 25px rgba(0,0,0,0.3);
            }}
            .btn-primary {{ background: linear-gradient(135deg, #1a73e8 0%, #4285f4 100%); }}
            .btn-success {{ background: linear-gradient(135deg, #34a853 0%, #66bb6a 100%); }}
            .btn-purple {{ background: linear-gradient(135deg, #9c27b0 0%, #ba68c8 100%); }}
            .footer {{
                text-align: center;
                padding: 20px;
                color: #666;
                font-size: 0.9em;
                background: #f8f9fa;
                border-top: 1px solid #e1e8ed;
            }}
            .legend {{
                margin-top: 20px;
                padding: 15px;
                background: #fff3cd;
                border: 1px solid #ffeaa7;
                border-radius: 8px;
                font-size: 0.85em;
                color: #856404;
                line-height: 1.5;
            }}
        </style></head>
        <body>
        <div class="dashboard">
            <div class="header">
                <h1>Baulkham Hills & Castle Hill Market Dashboard</h1>
                <p>Real-time property market insights for postcodes 2153 & 2154</p>
            </div>
            <div class="content">
                <div class="stats-grid">
                    <div class="stat-card">
                        <div class="stat-label">Properties Tracked</div>
                        <div class="stat-value">{stats['total_tracked']}</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-label">Currently For Sale</div>
                        <div class="stat-value">{stats['count_sale']}</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-label">Average Sale Price</div>
                        <div class="stat-value">${stats['avg_price_sale']:,}</div>
                    </div>
                    <div class="stat-card bh">
                        <div class="stat-label">Baulkham Hills</div>
                        <div class="stat-value">{stats['baulkham_hills_count']}</div>
                    </div>
                    <div class="stat-card ch">
                        <div class="stat-label">Castle Hill</div>
                        <div class="stat-value">{stats['castle_hill_count']}</div>
                    </div>
                    <div class="stat-card excelsior">
                        <div class="stat-label">Excelsior Catchment</div>
                        <div class="stat-value">{stats['excelsior_catchment_count']}</div>
                        <div class="stat-breakdown">{stats['excelsior_catchment_sale']} for sale | {stats['excelsior_catchment_sold']} sold</div>
                    </div>
                </div>
                <div class="section">
                    <h2 class="section-title">ML Price Predictions by Configuration</h2>
                    {self._build_ml_predictions_table()}
                </div>

                <div class="section">
                    <h2 class="section-title">Daily History Tracker</h2>
                    {self._build_daily_history_table()}
                </div>

                <div class="section">
                    <h2 class="section-title">Daily Changes ({datetime.now().strftime('%Y-%m-%d')})</h2>
                    {self._build_daily_changes_section()}
                </div>

                <div class="section">
                    <h2 class="section-title">Prediction Accuracy Report</h2>
                    <p style="color: #666; margin-bottom: 15px;">Comparing XGBoost, Domain Estimates, and Listed Prices against actual sold prices</p>
                    {self._build_prediction_accuracy_section()}
                </div>

                <div class="section">
                    <h2 class="section-title">Enhanced Sold Market Summary</h2>
                    {self._build_sold_summary_table()}
                </div>

                <div class="btn-container">
                    <a href="baulkandcastle_sale_matches.html" class="btn btn-primary">View For Sale Listings</a>
                    <a href="baulkandcastle_sold_matches.html" class="btn btn-success">View Sold Listings</a>
                    <a href="baulkandcastle_timeline.html" class="btn btn-purple">Market Timeline</a>
                    <a href="http://127.0.0.1:5000/predictor" class="btn btn-purple">XGBoost Predictor</a>
                </div>
            </div>
            <div class="footer">
                <p>Reports last updated: {datetime.now().strftime('%Y-%m-%d %H:%M')} | Baulkham Hills & Castle Hill Property Market Dashboard</p>
            </div>
        </div></body></html>"""

        with open(filename, 'w', encoding='utf-8') as f: f.write(html)
        print(f"Generated {filename}")

    def _build_ml_predictions_table(self) -> str:
        """Build ML predictions table for typical property configurations."""
        try:
            # Suppress XGBoost UserWarning about feature names during import
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", category=UserWarning, module="xgboost")
                from ml.valuation_predictor import PropertyValuationModel
                model = PropertyValuationModel()
                if not model.load():
                    return "<p>ML model not trained yet. Run: <code>python ml/train_model.py</code></p>"
        except Exception as e:
            return f"<p>ML model not available: {e}</p>"

        # Get model metrics
        mape = model.metadata.get('metrics', {}).get('mape', 15)
        r2 = model.metadata.get('metrics', {}).get('r2', 0)
        trained_at = model.metadata.get('trained_at', 'Unknown')[:10]

        # Define configurations to predict
        configs = [
            # Houses
            {'type': 'House', 'beds': 3, 'baths': 2, 'cars': 1, 'land': 450, 'property_type': 'house'},
            {'type': 'House', 'beds': 4, 'baths': 2, 'cars': 2, 'land': 550, 'property_type': 'house'},
            {'type': 'House', 'beds': 4, 'baths': 2, 'cars': 2, 'land': 700, 'property_type': 'house'},
            {'type': 'House', 'beds': 5, 'baths': 3, 'cars': 2, 'land': 800, 'property_type': 'house'},
            # Townhouses
            {'type': 'Townhouse', 'beds': 2, 'baths': 1, 'cars': 1, 'land': 150, 'property_type': 'townhouse'},
            {'type': 'Townhouse', 'beds': 3, 'baths': 2, 'cars': 1, 'land': 200, 'property_type': 'townhouse'},
            {'type': 'Townhouse', 'beds': 4, 'baths': 2, 'cars': 2, 'land': 250, 'property_type': 'townhouse'},
            # Units
            {'type': 'Unit', 'beds': 1, 'baths': 1, 'cars': 1, 'land': None, 'property_type': 'unit'},
            {'type': 'Unit', 'beds': 2, 'baths': 1, 'cars': 1, 'land': None, 'property_type': 'unit'},
            {'type': 'Unit', 'beds': 2, 'baths': 2, 'cars': 1, 'land': None, 'property_type': 'unit'},
            {'type': 'Unit', 'beds': 3, 'baths': 2, 'cars': 2, 'land': None, 'property_type': 'unit'},
        ]

        suburbs = ['CASTLE HILL', 'BAULKHAM HILLS']

        html = f'''
        <p style="margin-bottom: 15px; color: #666;">
            Model trained: {trained_at} | R² Score: {r2:.2%} | MAPE: {mape:.1f}%
        </p>
        <table class="summary-table">
            <thead>
                <tr>
                    <th>Property Type</th>
                    <th>Beds</th>
                    <th>Baths</th>
                    <th>Cars</th>
                    <th>Land Size</th>
                    <th>Castle Hill</th>
                    <th>Baulkham Hills</th>
                    <th>Difference</th>
                </tr>
            </thead>
            <tbody>
        '''

        for cfg in configs:
            predictions = {}
            for suburb in suburbs:
                try:
                    result = model.predict(
                        land_size=cfg['land'],
                        beds=cfg['beds'],
                        bathrooms=cfg['baths'],
                        car_spaces=cfg['cars'],
                        suburb=suburb,
                        property_type=cfg['property_type']
                    )
                    predictions[suburb] = result['predicted_price']
                except Exception:
                    predictions[suburb] = 0

            ch_price = predictions['CASTLE HILL']
            bh_price = predictions['BAULKHAM HILLS']
            diff = ch_price - bh_price
            diff_pct = (diff / bh_price * 100) if bh_price > 0 else 0

            land_display = f"{cfg['land']}m²" if cfg['land'] else "N/A"
            diff_color = "#34a853" if diff > 0 else "#d93025"

            html += f'''
                <tr>
                    <td><strong>{cfg['type']}</strong></td>
                    <td>{cfg['beds']}</td>
                    <td>{cfg['baths']}</td>
                    <td>{cfg['cars']}</td>
                    <td>{land_display}</td>
                    <td style="font-weight: bold; color: #1a73e8;">${ch_price:,.0f}</td>
                    <td style="font-weight: bold; color: #ff9800;">${bh_price:,.0f}</td>
                    <td style="color: {diff_color};">{diff_pct:+.1f}%</td>
                </tr>
            '''

        html += '''
            </tbody>
        </table>
        <div class="legend" style="margin-top: 15px;">
            <strong>Note:</strong> Predictions based on trained ML model. Castle Hill typically commands a premium.
            Land size shown is typical for each configuration. Units don't use land size (strata title).
        </div>
        '''
        return html

    def _build_daily_history_table(self) -> str:
        history = self.db.get_daily_history()
        if not history:
            return "<p>No history data available yet.</p>"

        html = '<table class="summary-table"><thead><tr><th>Date</th><th>New</th><th>Sold / Gone</th><th>Adjusted</th></tr></thead><tbody>'
        for h in history:
            html += f"<tr><td>{h['date']}</td><td>{h['new_count']}</td><td>{h['sold_count']}</td><td>{h['adj_count']}</td></tr>"
        html += '</tbody></table>'
        return html

    def _build_daily_changes_section(self) -> str:
        today = datetime.now().strftime('%Y-%m-%d')
        changes = self.db.get_comprehensive_daily_changes(today)

        total_changes = sum(len(v) for v in changes.values())
        if total_changes == 0:
            return "<p>No changes detected today.</p>"

        html = '''
        <style>
            .change-badge { padding: 3px 8px; border-radius: 4px; font-size: 0.75em; font-weight: bold; color: white; }
            .badge-sold { background: #d93025; }
            .badge-new { background: #1a73e8; }
            .badge-price-up { background: #ea4335; }
            .badge-price-down { background: #34a853; }
            .badge-guide { background: #9c27b0; }
            .badge-gone { background: #666; }
            .price-up { color: #d93025; font-weight: bold; }
            .price-down { color: #34a853; font-weight: bold; }
        </style>
        '''

        def build_table(rows, change_type):
            if not rows:
                return ""
            table = '<table class="summary-table"><thead><tr><th>Suburb</th><th>Address</th><th>Details</th><th>Specs</th><th>Agent</th><th>Link</th></tr></thead><tbody>'
            for d in rows:
                suburb = d.get('suburb', 'Unknown')
                suburb_display = "Baulkham Hills" if "BAULKHAM" in suburb else "Castle Hill"
                address = d.get('address', 'Unknown')
                url = d.get('url', '#')
                specs = f"{d.get('beds', '-')}bd {d.get('baths', '-')}ba {d.get('cars', '-')}car"
                agent = d.get('agent', '-')

                if change_type == 'sold':
                    old_price = d.get('old_price', 'N/A')
                    sold_price = d.get('price_display', 'N/A')
                    sold_date = d.get('sold_date', '')
                    details = f"<strong>Was:</strong> {old_price}<br><strong>Sold:</strong> {sold_price}"
                    if sold_date:
                        details += f"<br><em>({sold_date})</em>"
                elif change_type == 'price':
                    old_price = d.get('old_price', 'N/A')
                    new_price = d.get('price_display', 'N/A')
                    diff = d.get('price_diff', 0)
                    if diff > 0:
                        diff_str = f"<span class='price-up'>+${diff:,}</span>"
                    elif diff < 0:
                        diff_str = f"<span class='price-down'>-${abs(diff):,}</span>"
                    else:
                        diff_str = ""
                    details = f"{old_price} &rarr; {new_price} {diff_str}"
                elif change_type == 'guide':
                    old_price = d.get('old_price', 'N/A')
                    new_price = d.get('price_display', 'N/A')
                    details = f"<strong>Was:</strong> {old_price}<br><strong>Guide:</strong> {new_price}"
                elif change_type == 'new':
                    details = f"Listed at <strong>{d.get('price_display', 'N/A')}</strong>"
                elif change_type == 'gone':
                    details = f"Last seen at {d.get('price_display', 'N/A')}"
                else:
                    details = d.get('price_display', '-')

                table += f'''<tr>
                    <td>{suburb_display}</td>
                    <td><a href="{url}" target="_blank">{address}</a></td>
                    <td>{details}</td>
                    <td>{specs}</td>
                    <td>{agent}</td>
                    <td><a href="{url}" target="_blank">View</a></td>
                </tr>'''
            table += '</tbody></table>'
            return table

        # SOLD section
        if changes['sold']:
            html += f'''
            <h3 style="margin-top: 20px; color: #d93025;">
                <span class="change-badge badge-sold">SOLD</span> {len(changes['sold'])} Properties Sold
            </h3>
            {build_table(changes['sold'], 'sold')}
            '''

        # PRICE CHANGES section
        if changes['price_changes']:
            # Sort by absolute price diff
            changes['price_changes'].sort(key=lambda x: abs(x.get('price_diff', 0)), reverse=True)
            html += f'''
            <h3 style="margin-top: 20px; color: #ff9800;">
                <span class="change-badge badge-price-down">PRICE</span> {len(changes['price_changes'])} Price Changes
            </h3>
            {build_table(changes['price_changes'], 'price')}
            '''

        # GUIDE REVEALED section
        if changes['guide_revealed']:
            html += f'''
            <h3 style="margin-top: 20px; color: #9c27b0;">
                <span class="change-badge badge-guide">GUIDE</span> {len(changes['guide_revealed'])} Auction Guides Revealed
            </h3>
            {build_table(changes['guide_revealed'], 'guide')}
            '''

        # NEW LISTINGS section
        if changes['new']:
            html += f'''
            <h3 style="margin-top: 20px; color: #1a73e8;">
                <span class="change-badge badge-new">NEW</span> {len(changes['new'])} New Listings
            </h3>
            {build_table(changes['new'], 'new')}
            '''

        # DISAPPEARED section
        if changes['disappeared']:
            html += f'''
            <h3 style="margin-top: 20px; color: #666;">
                <span class="change-badge badge-gone">GONE</span> {len(changes['disappeared'])} Listings Removed
            </h3>
            <p style="font-size: 0.85em; color: #666; margin-bottom: 10px;">Properties that were listed yesterday but no longer appear (may be sold, withdrawn, or relisted)</p>
            {build_table(changes['disappeared'], 'gone')}
            '''

        return html

    def _build_prediction_accuracy_section(self) -> str:
        """Build the prediction accuracy comparison section for the summary report."""
        report = self.db.get_prediction_accuracy_report()
        comparisons = report['comparisons']
        stats = report['stats']

        if not comparisons:
            return "<p>No sold properties with predictions/estimates to compare yet.</p>"

        # Summary stats cards - format values first
        listed_mape = f"{stats['listed']['mape']:.1f}%" if stats['listed']['mape'] is not None else "N/A"
        xgboost_mape = f"{stats['xgboost']['mape']:.1f}%" if stats['xgboost']['mape'] is not None else "N/A"
        domain_mape = f"{stats['domain']['mape']:.1f}%" if stats['domain']['mape'] is not None else "N/A"

        html = f'''
        <style>
            .accuracy-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin-bottom: 25px; }}
            .accuracy-card {{ padding: 20px; border-radius: 8px; text-align: center; }}
            .accuracy-card.listed {{ background: linear-gradient(135deg, #e3f2fd 0%, #bbdefb 100%); border-left: 4px solid #1976d2; }}
            .accuracy-card.xgboost {{ background: linear-gradient(135deg, #fff3e0 0%, #ffe0b2 100%); border-left: 4px solid #f57c00; }}
            .accuracy-card.domain {{ background: linear-gradient(135deg, #e8f5e9 0%, #c8e6c9 100%); border-left: 4px solid #388e3c; }}
            .accuracy-card .title {{ font-size: 0.85em; color: #666; text-transform: uppercase; margin-bottom: 8px; }}
            .accuracy-card .mape {{ font-size: 2em; font-weight: bold; }}
            .accuracy-card .detail {{ font-size: 0.8em; color: #888; margin-top: 5px; }}
            .accuracy-card.listed .mape {{ color: #1976d2; }}
            .accuracy-card.xgboost .mape {{ color: #f57c00; }}
            .accuracy-card.domain .mape {{ color: #388e3c; }}
            .error-positive {{ color: #d32f2f; }}
            .error-negative {{ color: #388e3c; }}
            .winner {{ background: #c8e6c9 !important; font-weight: bold; }}
        </style>

        <div class="accuracy-grid">
            <div class="accuracy-card listed">
                <div class="title">Listed Price</div>
                <div class="mape">{listed_mape}</div>
                <div class="detail">MAPE | {stats['listed']['count']} properties</div>
            </div>
            <div class="accuracy-card xgboost">
                <div class="title">XGBoost Model</div>
                <div class="mape">{xgboost_mape}</div>
                <div class="detail">MAPE | {stats['xgboost']['count']} properties</div>
            </div>
            <div class="accuracy-card domain">
                <div class="title">Domain Estimate</div>
                <div class="mape">{domain_mape}</div>
                <div class="detail">MAPE | {stats['domain']['count']} properties</div>
            </div>
        </div>
        '''

        # Comparison table
        html += '''
        <p style="font-size: 0.85em; color: #666; margin-bottom: 15px;">
            <strong>MAPE</strong> = Mean Absolute Percentage Error (lower is better).
            Green background indicates the most accurate prediction for each property.
        </p>
        <table class="summary-table">
            <thead>
                <tr>
                    <th>Address</th>
                    <th>Sold Date</th>
                    <th>Sold Price</th>
                    <th>Listed Price</th>
                    <th>XGBoost</th>
                    <th>Domain Est.</th>
                    <th>Best</th>
                </tr>
            </thead>
            <tbody>
        '''

        for c in comparisons[:20]:  # Limit to 20 most recent
            sold_price = c['sold_price']
            sold_fmt = f"${sold_price:,}"

            # Format listed price
            if c['listed_price']:
                err = c['listed_error_pct']
                err_class = "error-positive" if err > 0 else "error-negative"
                listed_fmt = f"${c['listed_price']:,}<br><span class='{err_class}'>({err:+.1f}%)</span>"
            else:
                listed_fmt = c['listed_display'] or "-"

            # Format XGBoost
            if c['xgboost_price']:
                err = c['xgboost_error_pct']
                err_class = "error-positive" if err > 0 else "error-negative"
                xgb_fmt = f"${c['xgboost_price']:,}<br><span class='{err_class}'>({err:+.1f}%)</span>"
            else:
                xgb_fmt = "-"

            # Format Domain
            if c['domain_estimate']:
                err = c['domain_error_pct']
                err_class = "error-positive" if err > 0 else "error-negative"
                domain_fmt = f"${c['domain_estimate']:,}<br><span class='{err_class}'>({err:+.1f}%)</span>"
            else:
                domain_fmt = "-"

            # Determine winner (lowest absolute error)
            errors = []
            if c['listed_error_pct'] is not None:
                errors.append(('Listed', abs(c['listed_error_pct'])))
            if c['xgboost_error_pct'] is not None:
                errors.append(('XGBoost', abs(c['xgboost_error_pct'])))
            if c['domain_error_pct'] is not None:
                errors.append(('Domain', abs(c['domain_error_pct'])))

            winner = min(errors, key=lambda x: x[1])[0] if errors else "-"
            winner_class = {
                'Listed': 'listed',
                'XGBoost': 'xgboost',
                'Domain': 'domain'
            }.get(winner, '')

            html += f'''
                <tr>
                    <td style="text-align: left;">{c['address']}<br><small>{c['beds']}bd {c['baths']}ba {c['cars']}car</small></td>
                    <td>{c['sold_date'] or '-'}</td>
                    <td style="font-weight: bold;">{sold_fmt}</td>
                    <td class="{'winner' if winner == 'Listed' else ''}">{listed_fmt}</td>
                    <td class="{'winner' if winner == 'XGBoost' else ''}">{xgb_fmt}</td>
                    <td class="{'winner' if winner == 'Domain' else ''}">{domain_fmt}</td>
                    <td><strong>{winner}</strong></td>
                </tr>
            '''

        html += '</tbody></table>'

        # Add legend
        html += '''
        <div class="legend" style="margin-top: 15px;">
            <strong>Legend:</strong>
            <span class="error-positive">+X%</span> = overestimated (predicted higher than sold) |
            <span class="error-negative">-X%</span> = underestimated (predicted lower than sold)
        </div>
        '''

        return html

    def _build_sold_summary_table(self) -> str:
        """Calculates and builds the monthly sold summary table with enhanced market insights."""
        # Query for all sold properties
        query = '''
            SELECT beds, price_value, price_per_m2, sold_date
            FROM listing_history
            WHERE status = 'sold' AND price_value > 0
        '''
        data = {}
        overall_data = {}

        with sqlite3.connect(self.db.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(query).fetchall()

            for row in rows:
                # Parse sold_date: "DD MMM YYYY" or "YYYY-MM-DD..."
                date_str = row['sold_date']
                if not date_str: continue

                try:
                    if 'T' in date_str: dt = datetime.fromisoformat(date_str.split('T')[0])
                    else: dt = datetime.strptime(date_str, "%d %b %Y")
                    month_key = dt.strftime("%Y-%m") # e.g. "2023-12"
                except: continue

                beds = row['beds']
                price = row['price_value']
                ppm2 = row['price_per_m2']

                # Per bedroom data
                if beds not in data: data[beds] = {}
                if month_key not in data[beds]: data[beds][month_key] = {'prices': [], 'ppm2s': []}

                data[beds][month_key]['prices'].append(price)
                if ppm2:
                    data[beds][month_key]['ppm2s'].append(ppm2)

                # Overall data (all bedrooms combined)
                if month_key not in overall_data: overall_data[month_key] = {'prices': [], 'ppm2s': []}
                overall_data[month_key]['prices'].append(price)
                if ppm2:
                    overall_data[month_key]['ppm2s'].append(ppm2)

        if not data: return "<p>No sold data available for summary.</p>"

        # Get all unique months and sort them
        all_months = sorted(list(set(m for b in data for m in data[b])), reverse=True)
        beds_cats = sorted(data.keys())

        # Calculate month-to-month changes
        def calculate_change(current_vals, prev_vals):
            if not current_vals or not prev_vals:
                return None
            current_avg = sum(current_vals) / len(current_vals)
            prev_avg = sum(prev_vals) / len(prev_vals)
            return ((current_avg - prev_avg) / prev_avg) * 100

        html = '''<table class="summary-table">
                <thead>
                    <tr>
                        <th rowspan="2">Month</th>
                        <th rowspan="2">Overall<br><small>Count | Avg Price | Price Change %<br>High-Low | Avg $/m2 | $/m2 Change %</small></th>'''

        for b in beds_cats:
            html += f'<th>{b} Bed<br><small>Count | Avg | Change %<br>High-Low | Avg $/m2 | Change %</small></th>'
        html += '</tr></thead><tbody>'

        prev_overall = None
        prev_bedroom = {b: None for b in beds_cats}

        for i, month in enumerate(all_months):
            html += f'<tr><td><strong>{month}</strong></td>'

            # Overall stats
            overall_stats = overall_data.get(month)
            if overall_stats and overall_stats['prices']:
                count = len(overall_stats['prices'])
                avg_p = sum(overall_stats['prices']) / count
                min_p = min(overall_stats['prices'])
                max_p = max(overall_stats['prices'])

                # Price change
                price_change = ""
                if prev_overall:
                    change = calculate_change(overall_stats['prices'], prev_overall['prices'])
                    if change is not None:
                        price_change = f" ({change:+.1f}%)"

                # Price per m2 stats
                ppm2_info = ""
                ppm2_change = ""
                if overall_stats['ppm2s']:
                    avg_ppm2 = sum(overall_stats['ppm2s']) / len(overall_stats['ppm2s'])
                    ppm2_info = f"${avg_ppm2:,.0f}"
                    if prev_overall and prev_overall.get('ppm2s'):
                        ppm2_chg = calculate_change(overall_stats['ppm2s'], prev_overall['ppm2s'])
                        if ppm2_chg is not None:
                            ppm2_change = f" ({ppm2_chg:+.1f}%)"
                else:
                    ppm2_info = "-"

                html += f'''<td><strong>{count}</strong> | ${avg_p/1000:,.0f}k{price_change}<br>
                           ${min_p/1000:,.0f}k-${max_p/1000:,.0f}k | {ppm2_info}{ppm2_change}</td>'''
                prev_overall = overall_stats
            else:
                html += '<td>-</td>'
                prev_overall = None

            # Per bedroom stats
            for b in beds_cats:
                stats = data[b].get(month)
                if stats and stats['prices']:
                    count = len(stats['prices'])
                    avg_p = sum(stats['prices']) / count
                    min_p = min(stats['prices'])
                    max_p = max(stats['prices'])

                    # Price change
                    price_change = ""
                    if prev_bedroom[b]:
                        change = calculate_change(stats['prices'], prev_bedroom[b]['prices'])
                        if change is not None:
                            price_change = f" ({change:+.1f}%)"

                    # Price per m2 stats
                    ppm2_info = ""
                    ppm2_change = ""
                    if stats['ppm2s']:
                        avg_ppm2 = sum(stats['ppm2s']) / len(stats['ppm2s'])
                        ppm2_info = f"${avg_ppm2:,.0f}"
                        if prev_bedroom[b] and prev_bedroom[b].get('ppm2s'):
                            ppm2_chg = calculate_change(stats['ppm2s'], prev_bedroom[b]['ppm2s'])
                            if ppm2_chg is not None:
                                ppm2_change = f" ({ppm2_chg:+.1f}%)"
                    else:
                        ppm2_info = "-"

                    html += f'''<td>{count} | ${avg_p/1000:,.0f}k{price_change}<br>
                               ${min_p/1000:,.0f}k-${max_p/1000:,.0f}k | {ppm2_info}{ppm2_change}</td>'''
                    prev_bedroom[b] = stats
                else:
                    html += '<td>-</td>'
                    prev_bedroom[b] = None

            html += '</tr>'

        html += '''</tbody></table>
        <div class="legend">
            <strong>Legend:</strong> <strong>Count</strong> = Number of properties sold | <strong>Avg</strong> = Average price |
            <strong>Change %</strong> = Month-to-month price change | <strong>High-Low</strong> = Price range |
            <strong>$/m2</strong> = Average price per square meter
        </div>'''
        return html

    def _get_timeline_data(self) -> List[Dict]:
        """Extract all sold properties with dates, prices, categories, price_per_m²."""
        query = '''
            SELECT h.sold_date_iso, h.price_value, h.price_per_m2,
                   h.property_type, h.beds, h.baths, h.cars, h.land_size,
                   p.suburb, p.address, p.url
            FROM listing_history h
            JOIN properties p ON h.property_id = p.property_id
            WHERE h.status = 'sold' AND h.price_value > 0
              AND h.sold_date_iso IS NOT NULL
            ORDER BY h.sold_date_iso
        '''
        with sqlite3.connect(self.db.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(query).fetchall()
            return [dict(r) for r in rows]

    def _normalize_property_type(self, prop_type: str) -> str:
        """Normalize property types into main categories."""
        if not prop_type:
            return 'Other'
        prop_type = prop_type.lower()
        # Check townhouse BEFORE house (since 'house' is substring of 'townhouse')
        if 'townhouse' in prop_type or 'town-house' in prop_type or 'terrace' in prop_type:
            return 'Townhouse'
        elif 'house' in prop_type or 'free-standing' in prop_type or 'duplex' in prop_type:
            return 'House'
        elif 'apartment' in prop_type or 'unit' in prop_type or 'flat' in prop_type:
            return 'Apartment'
        elif 'semi' in prop_type:
            return 'Semi-detached'
        elif 'villa' in prop_type:
            return 'Villa'
        elif 'land' in prop_type or 'vacant' in prop_type:
            return 'Land'
        else:
            return 'Other'

    def _aggregate_by_week(self, data: List[Dict]) -> Dict:
        """Group data by week and property type."""
        weekly = {}
        for row in data:
            try:
                dt = datetime.fromisoformat(row['sold_date_iso'])
                # ISO week format: YYYY-WNN
                week_key = dt.strftime('%Y-W%W')
                week_start = dt - timedelta(days=dt.weekday())
                week_start_str = week_start.strftime('%Y-%m-%d')
            except:
                continue

            prop_type = self._normalize_property_type(row['property_type'])

            if week_key not in weekly:
                weekly[week_key] = {
                    'week_start': week_start_str,
                    'by_type': {},
                    'all_prices': [],
                    'all_ppm2': []
                }

            if prop_type not in weekly[week_key]['by_type']:
                weekly[week_key]['by_type'][prop_type] = {
                    'count': 0,
                    'prices': [],
                    'ppm2': []
                }

            weekly[week_key]['by_type'][prop_type]['count'] += 1
            weekly[week_key]['by_type'][prop_type]['prices'].append(row['price_value'])
            weekly[week_key]['all_prices'].append(row['price_value'])

            if row['price_per_m2']:
                weekly[week_key]['by_type'][prop_type]['ppm2'].append(row['price_per_m2'])
                weekly[week_key]['all_ppm2'].append(row['price_per_m2'])

        return weekly

    def _calculate_linear_trend(self, x_values: List[float], y_values: List[float]) -> Dict:
        """Calculate linear regression manually (no numpy required)."""
        if len(x_values) < 2 or len(y_values) < 2:
            return {'slope': 0, 'intercept': 0, 'r2': 0}

        n = len(x_values)
        sum_x = sum(x_values)
        sum_y = sum(y_values)
        sum_xy = sum(x * y for x, y in zip(x_values, y_values))
        sum_x2 = sum(x * x for x in x_values)
        sum_y2 = sum(y * y for y in y_values)

        # Calculate slope and intercept
        denominator = n * sum_x2 - sum_x * sum_x
        if denominator == 0:
            return {'slope': 0, 'intercept': sum_y / n if n > 0 else 0, 'r2': 0}

        slope = (n * sum_xy - sum_x * sum_y) / denominator
        intercept = (sum_y - slope * sum_x) / n

        # Calculate R²
        y_mean = sum_y / n
        ss_tot = sum((y - y_mean) ** 2 for y in y_values)
        ss_res = sum((y - (slope * x + intercept)) ** 2 for x, y in zip(x_values, y_values))
        r2 = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0

        return {'slope': slope, 'intercept': intercept, 'r2': max(0, r2)}

    def _generate_insights(self, data: List[Dict], weekly_data: Dict) -> Dict:
        """Generate natural language market insights."""
        if not data or not weekly_data:
            return {'summary': 'Insufficient data for insights.', 'trends': []}

        # Get sorted weeks
        sorted_weeks = sorted(weekly_data.keys())
        if len(sorted_weeks) < 2:
            return {'summary': 'Need more data for trend analysis.', 'trends': []}

        # Current month vs previous month
        today = datetime.now()
        current_month = today.strftime('%Y-%m')
        prev_month = (today.replace(day=1) - timedelta(days=1)).strftime('%Y-%m')

        current_month_data = [d for d in data if d['sold_date_iso'][:7] == current_month]
        prev_month_data = [d for d in data if d['sold_date_iso'][:7] == prev_month]

        insights = {
            'current_month': {
                'count': len(current_month_data),
                'avg_price': sum(d['price_value'] for d in current_month_data) / len(current_month_data) if current_month_data else 0
            },
            'prev_month': {
                'count': len(prev_month_data),
                'avg_price': sum(d['price_value'] for d in prev_month_data) / len(prev_month_data) if prev_month_data else 0
            },
            'trends': []
        }

        # Volume change
        if insights['prev_month']['count'] > 0:
            vol_change = ((insights['current_month']['count'] - insights['prev_month']['count']) / insights['prev_month']['count']) * 100
            insights['volume_change'] = vol_change
        else:
            insights['volume_change'] = 0

        # Price change
        if insights['prev_month']['avg_price'] > 0:
            price_change = ((insights['current_month']['avg_price'] - insights['prev_month']['avg_price']) / insights['prev_month']['avg_price']) * 100
            insights['price_change'] = price_change
        else:
            insights['price_change'] = 0

        # Per-category trends
        categories = ['House', 'Apartment', 'Townhouse']
        for cat in categories:
            cat_data = [d for d in data if self._normalize_property_type(d['property_type']) == cat]
            if len(cat_data) >= 5:
                # Calculate trend over all data
                x_vals = []
                y_vals = []
                start_date = datetime.fromisoformat(cat_data[0]['sold_date_iso'])
                for d in cat_data:
                    dt = datetime.fromisoformat(d['sold_date_iso'])
                    days = (dt - start_date).days
                    x_vals.append(days)
                    y_vals.append(d['price_value'])

                trend = self._calculate_linear_trend(x_vals, y_vals)
                monthly_change = trend['slope'] * 30  # Price change per month

                insights['trends'].append({
                    'category': cat,
                    'direction': 'upward' if trend['slope'] > 0 else 'downward',
                    'monthly_change': monthly_change,
                    'r2': trend['r2'],
                    'count': len(cat_data)
                })

        # Build summary text
        direction = "rising" if insights.get('price_change', 0) > 0 else "falling"
        summary_parts = [
            f"Market Overview: Prices are {direction} with {insights['current_month']['count']} sales this month"
        ]

        if insights['current_month']['avg_price'] > 0:
            summary_parts.append(f"averaging ${insights['current_month']['avg_price']:,.0f}")

        insights['summary'] = ' '.join(summary_parts) + '.'

        return insights

    def generate_timeline_report(self):
        """Generate interactive timeline dashboard with Plotly.js charts and filters."""
        # Get data
        data = self._get_timeline_data()
        if not data:
            print("No sold data available for timeline report.")
            return

        # Normalize property types and add to data
        for row in data:
            row['normalized_type'] = self._normalize_property_type(row['property_type'])

        # Get unique values for filters
        all_beds = sorted(set(d['beds'] for d in data if d['beds'] is not None))
        all_baths = sorted(set(d['baths'] for d in data if d['baths'] is not None))
        all_cars = sorted(set(d.get('cars', 0) or 0 for d in data))

        categories = ['House', 'Apartment', 'Townhouse', 'Semi-detached', 'Villa', 'Land', 'Other']
        category_colors = {
            'House': '#1a73e8',
            'Apartment': '#34a853',
            'Townhouse': '#fbbc04',
            'Semi-detached': '#ea4335',
            'Villa': '#9c27b0',
            'Land': '#00bcd4',
            'Other': '#9e9e9e'
        }

        # Prepare raw data for JavaScript (with normalized type)
        raw_data = []
        for row in data:
            raw_data.append({
                'x': row['sold_date_iso'],
                'y': row['price_value'],
                'type': row['normalized_type'],
                'address': row['address'],
                'beds': row['beds'],
                'baths': row['baths'],
                'cars': row.get('cars', 0) or 0,
                'suburb': row['suburb'],
                'url': row['url'],
                'ppm2': row['price_per_m2']
            })

        today_str = datetime.now().strftime('%Y-%m-%d')

        html = f"""
<!DOCTYPE html>
<html><head>
    <title>Baulkham Hills & Castle Hill - Market Timeline</title>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
            line-height: 1.6;
        }}
        .dashboard {{
            width: 95%;
            max-width: 1600px;
            margin: 0 auto;
            background: white;
            border-radius: 15px;
            box-shadow: 0 20px 40px rgba(0,0,0,0.1);
            overflow: hidden;
        }}
        .header {{
            background: linear-gradient(135deg, #1a73e8 0%, #4285f4 100%);
            color: white;
            padding: 30px 40px;
            text-align: center;
        }}
        .header h1 {{
            font-size: 2.5em;
            margin-bottom: 10px;
            font-weight: 300;
            text-shadow: 0 2px 4px rgba(0,0,0,0.3);
        }}
        .header p {{
            font-size: 1.1em;
            opacity: 0.9;
        }}
        .content {{ padding: 30px 40px; }}

        /* Filter Panel Styles */
        .filter-panel {{
            background: linear-gradient(135deg, #f0f4ff 0%, #e8eeff 100%);
            padding: 25px;
            border-radius: 12px;
            margin-bottom: 30px;
            border: 2px solid #1a73e8;
            box-shadow: 0 4px 15px rgba(26, 115, 232, 0.15);
        }}
        .filter-panel h3 {{
            color: #1a73e8;
            margin-bottom: 20px;
            font-size: 1.2em;
            display: flex;
            align-items: center;
            gap: 10px;
        }}
        .filter-row {{
            display: flex;
            flex-wrap: wrap;
            gap: 20px;
            align-items: flex-end;
        }}
        .filter-group {{
            flex: 1;
            min-width: 150px;
        }}
        .filter-group label {{
            display: block;
            font-weight: 600;
            color: #333;
            margin-bottom: 8px;
            font-size: 0.9em;
        }}
        .filter-group select {{
            width: 100%;
            padding: 10px 12px;
            border: 2px solid #ddd;
            border-radius: 8px;
            font-size: 1em;
            background: white;
            cursor: pointer;
            transition: border-color 0.3s;
        }}
        .filter-group select:focus {{
            outline: none;
            border-color: #1a73e8;
        }}
        .filter-group select:hover {{
            border-color: #1a73e8;
        }}
        .filter-btn {{
            padding: 10px 25px;
            background: linear-gradient(135deg, #ea4335 0%, #ff6b6b 100%);
            color: white;
            border: none;
            border-radius: 8px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s;
        }}
        .filter-btn:hover {{
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(234, 67, 53, 0.3);
        }}
        .filter-status {{
            margin-top: 15px;
            padding: 10px 15px;
            background: white;
            border-radius: 6px;
            font-size: 0.9em;
            color: #666;
        }}
        .filter-status strong {{
            color: #1a73e8;
        }}

        .insights-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 15px;
            margin-bottom: 30px;
        }}
        .insight-card {{
            background: linear-gradient(135deg, #f8f9ff 0%, #e3f2fd 100%);
            padding: 18px;
            border-radius: 12px;
            border-left: 5px solid #1a73e8;
            box-shadow: 0 4px 15px rgba(0,0,0,0.08);
        }}
        .insight-card.positive {{ border-left-color: #34a853; }}
        .insight-card.negative {{ border-left-color: #ea4335; }}
        .insight-label {{
            font-weight: 600;
            color: #555;
            font-size: 0.8em;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 6px;
        }}
        .insight-value {{
            font-size: 1.5em;
            font-weight: 700;
            color: #1a73e8;
        }}
        .insight-value.positive {{ color: #34a853; }}
        .insight-value.negative {{ color: #ea4335; }}
        .insight-detail {{
            font-size: 0.75em;
            color: #666;
            margin-top: 4px;
        }}
        .chart-section {{
            margin-bottom: 40px;
            background: #fafbfc;
            border-radius: 12px;
            padding: 25px;
            border: 1px solid #e1e8ed;
        }}
        .chart-title {{
            font-size: 1.4em;
            color: #1a73e8;
            margin-bottom: 15px;
            font-weight: 600;
            display: flex;
            align-items: center;
        }}
        .chart-title:before {{
            content: '';
            width: 4px;
            height: 24px;
            background: #1a73e8;
            margin-right: 12px;
            border-radius: 2px;
        }}
        .chart-container {{
            width: 100%;
            height: 400px;
        }}
        .chart-container.tall {{
            height: 500px;
        }}
        .category-stats {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
            gap: 12px;
            margin-bottom: 30px;
        }}
        .cat-stat {{
            background: white;
            padding: 12px;
            border-radius: 8px;
            text-align: center;
            box-shadow: 0 2px 8px rgba(0,0,0,0.05);
            border-top: 3px solid #1a73e8;
            cursor: pointer;
            transition: all 0.3s;
        }}
        .cat-stat:hover {{
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0,0,0,0.1);
        }}
        .cat-stat.selected {{
            background: linear-gradient(135deg, #e3f2fd 0%, #bbdefb 100%);
            border-top-width: 4px;
        }}
        .cat-stat-name {{
            font-weight: 600;
            font-size: 0.85em;
            color: #333;
            margin-bottom: 4px;
        }}
        .cat-stat-value {{
            font-size: 1.1em;
            font-weight: 700;
            color: #1a73e8;
        }}
        .cat-stat-detail {{
            font-size: 0.7em;
            color: #666;
        }}
        .trend-summary {{
            background: #e8f5e9;
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 30px;
            border-left: 4px solid #34a853;
        }}
        .trend-summary.declining {{
            background: #ffebee;
            border-left-color: #ea4335;
        }}
        .trend-summary h3 {{
            color: #1b5e20;
            margin-bottom: 10px;
        }}
        .trend-summary.declining h3 {{
            color: #c62828;
        }}
        .btn-container {{
            display: flex;
            gap: 15px;
            margin-top: 30px;
            flex-wrap: wrap;
        }}
        .btn {{
            display: inline-block;
            padding: 12px 25px;
            color: white;
            text-decoration: none;
            border-radius: 8px;
            font-weight: 600;
            transition: all 0.3s ease;
            box-shadow: 0 4px 15px rgba(0,0,0,0.2);
        }}
        .btn:hover {{
            transform: translateY(-2px);
            box-shadow: 0 8px 25px rgba(0,0,0,0.3);
        }}
        .btn-primary {{ background: linear-gradient(135deg, #1a73e8 0%, #4285f4 100%); }}
        .btn-secondary {{ background: linear-gradient(135deg, #5f6368 0%, #80868b 100%); }}
        .footer {{
            text-align: center;
            padding: 20px;
            color: #666;
            font-size: 0.9em;
            background: #f8f9fa;
            border-top: 1px solid #e1e8ed;
        }}
        .legend-inline {{
            display: flex;
            flex-wrap: wrap;
            gap: 15px;
            margin-top: 10px;
            padding: 10px;
            background: #f5f5f5;
            border-radius: 6px;
        }}
        .legend-item {{
            display: flex;
            align-items: center;
            gap: 6px;
            font-size: 0.85em;
        }}
        .legend-color {{
            width: 16px;
            height: 16px;
            border-radius: 3px;
        }}
    </style>
</head>
<body>
<div class="dashboard">
    <div class="header">
        <h1>Market Timeline Dashboard</h1>
        <p>Property Sales Trends for Baulkham Hills & Castle Hill | Interactive Analysis</p>
    </div>
    <div class="content">
        <!-- Filter Panel -->
        <div class="filter-panel">
            <h3>🔍 Filter Data</h3>
            <div class="filter-row">
                <div class="filter-group">
                    <label>Property Type</label>
                    <select id="filter-type">
                        <option value="all">All Types</option>
                        {''.join(f'<option value="{cat}">{cat}</option>' for cat in categories)}
                    </select>
                </div>
                <div class="filter-group">
                    <label>Bedrooms</label>
                    <select id="filter-beds">
                        <option value="all">Any</option>
                        {''.join(f'<option value="{b}">{b} bed{"s" if b != 1 else ""}</option>' for b in all_beds)}
                    </select>
                </div>
                <div class="filter-group">
                    <label>Bathrooms</label>
                    <select id="filter-baths">
                        <option value="all">Any</option>
                        {''.join(f'<option value="{b}">{b} bath{"s" if b != 1 else ""}</option>' for b in all_baths)}
                    </select>
                </div>
                <div class="filter-group">
                    <label>Car Spaces</label>
                    <select id="filter-cars">
                        <option value="all">Any</option>
                        {''.join(f'<option value="{c}">{c} car{"s" if c != 1 else ""}</option>' for c in all_cars)}
                    </select>
                </div>
                <button class="filter-btn" onclick="resetFilters()">Reset All</button>
            </div>
            <div class="filter-status" id="filter-status">
                Showing <strong id="filtered-count">{len(data)}</strong> of {len(data)} properties
            </div>
        </div>

        <!-- Dynamic Insights Panel -->
        <div id="insights-container"></div>

        <!-- Category Stats (clickable) -->
        <div class="category-stats" id="category-stats"></div>

        <div class="chart-section">
            <h2 class="chart-title">Sales Volume by Week</h2>
            <div id="volume-chart" class="chart-container"></div>
        </div>

        <div class="chart-section">
            <h2 class="chart-title">Average Price Trends by Property Type</h2>
            <div id="price-chart" class="chart-container"></div>
        </div>

        <div class="chart-section">
            <h2 class="chart-title">Price per m² Trends (Land-Based Properties)</h2>
            <div id="ppm2-chart" class="chart-container"></div>
        </div>

        <div class="chart-section">
            <h2 class="chart-title">Individual Sales with Market Trend</h2>
            <div id="scatter-chart" class="chart-container tall"></div>
        </div>

        <div class="btn-container">
            <a href="baulkandcastle_summary.html" class="btn btn-primary">Back to Dashboard</a>
            <a href="baulkandcastle_sold_matches.html" class="btn btn-secondary">View All Sold</a>
        </div>
    </div>
    <div class="footer">
        <p>Timeline generated: {datetime.now().strftime('%Y-%m-%d %H:%M')} | Data: {len(data)} sold properties | Today: {today_str}</p>
    </div>
</div>

<script>
// Raw data and configuration
const rawData = {json.dumps(raw_data)};
const categoryColors = {json.dumps(category_colors)};
const categories = {json.dumps(categories)};
const todayStr = "{today_str}";
const totalCount = {len(data)};

// Current filter state
let currentFilters = {{
    type: 'all',
    beds: 'all',
    baths: 'all',
    cars: 'all'
}};

// Filter data based on current selections
function filterData() {{
    return rawData.filter(d => {{
        if (currentFilters.type !== 'all' && d.type !== currentFilters.type) return false;
        if (currentFilters.beds !== 'all' && d.beds != currentFilters.beds) return false;
        if (currentFilters.baths !== 'all' && d.baths != currentFilters.baths) return false;
        if (currentFilters.cars !== 'all' && d.cars != currentFilters.cars) return false;
        return true;
    }});
}}

// Aggregate data by week
function aggregateByWeek(data) {{
    const weekly = {{}};
    data.forEach(row => {{
        try {{
            const dt = new Date(row.x);
            const dayOfWeek = dt.getDay();
            const mondayOffset = dayOfWeek === 0 ? -6 : 1 - dayOfWeek;
            const weekStart = new Date(dt);
            weekStart.setDate(dt.getDate() + mondayOffset);
            const weekKey = weekStart.toISOString().split('T')[0];

            if (!weekly[weekKey]) {{
                weekly[weekKey] = {{
                    weekStart: weekKey,
                    byType: {{}},
                    allPrices: [],
                    allPpm2: []
                }};
            }}

            const propType = row.type;
            if (!weekly[weekKey].byType[propType]) {{
                weekly[weekKey].byType[propType] = {{ count: 0, prices: [], ppm2: [] }};
            }}

            weekly[weekKey].byType[propType].count++;
            weekly[weekKey].byType[propType].prices.push(row.y);
            weekly[weekKey].allPrices.push(row.y);

            if (row.ppm2) {{
                weekly[weekKey].byType[propType].ppm2.push(row.ppm2);
                weekly[weekKey].allPpm2.push(row.ppm2);
            }}
        }} catch (e) {{}}
    }});
    return weekly;
}}

// Calculate insights from filtered data
function calculateInsights(data) {{
    if (!data.length) return null;

    const now = new Date();
    const currentMonth = now.toISOString().slice(0, 7);
    const prevDate = new Date(now.getFullYear(), now.getMonth() - 1, 1);
    const prevMonth = prevDate.toISOString().slice(0, 7);

    const currentMonthData = data.filter(d => d.x.slice(0, 7) === currentMonth);
    const prevMonthData = data.filter(d => d.x.slice(0, 7) === prevMonth);

    const currentCount = currentMonthData.length;
    const prevCount = prevMonthData.length;
    const currentAvg = currentCount > 0 ? currentMonthData.reduce((s, d) => s + d.y, 0) / currentCount : 0;
    const prevAvg = prevCount > 0 ? prevMonthData.reduce((s, d) => s + d.y, 0) / prevCount : 0;

    const priceChange = prevAvg > 0 ? ((currentAvg - prevAvg) / prevAvg) * 100 : 0;
    const volumeChange = prevCount > 0 ? ((currentCount - prevCount) / prevCount) * 100 : 0;

    // Calculate overall trend
    const sortedData = [...data].sort((a, b) => a.x.localeCompare(b.x));
    let trend = {{ slope: 0, monthlyChange: 0, direction: 'stable' }};
    if (sortedData.length >= 5) {{
        const firstDate = new Date(sortedData[0].x);
        let sumX = 0, sumY = 0, sumXY = 0, sumX2 = 0;
        const n = sortedData.length;
        sortedData.forEach(d => {{
            const x = (new Date(d.x) - firstDate) / (1000 * 60 * 60 * 24);
            sumX += x;
            sumY += d.y;
            sumXY += x * d.y;
            sumX2 += x * x;
        }});
        const slope = (n * sumXY - sumX * sumY) / (n * sumX2 - sumX * sumX);
        trend.slope = slope;
        trend.monthlyChange = slope * 30;
        trend.direction = slope > 0 ? 'upward' : 'downward';
    }}

    // Per-category stats
    const catStats = {{}};
    categories.forEach(cat => {{
        const catData = data.filter(d => d.type === cat);
        if (catData.length > 0) {{
            catStats[cat] = {{
                count: catData.length,
                avgPrice: catData.reduce((s, d) => s + d.y, 0) / catData.length,
                ppm2Count: catData.filter(d => d.ppm2).length
            }};
        }}
    }});

    return {{
        currentMonth: {{ count: currentCount, avgPrice: currentAvg }},
        prevMonth: {{ count: prevCount, avgPrice: prevAvg }},
        priceChange,
        volumeChange,
        trend,
        catStats,
        totalFiltered: data.length
    }};
}}

// Render insights panel
function renderInsights(insights) {{
    if (!insights) {{
        document.getElementById('insights-container').innerHTML = '<p>No data matches the current filters.</p>';
        return;
    }}

    const priceClass = insights.priceChange >= 0 ? 'positive' : 'negative';
    const volClass = insights.volumeChange >= 0 ? 'positive' : 'negative';
    const trendClass = insights.trend.direction === 'upward' ? 'positive' : 'negative';
    const trendSymbol = insights.trend.direction === 'upward' ? '↑' : '↓';

    let html = `
        <div class="insights-grid">
            <div class="insight-card">
                <div class="insight-label">This Month Sales</div>
                <div class="insight-value">${{insights.currentMonth.count}}</div>
                <div class="insight-detail">vs ${{insights.prevMonth.count}} last month</div>
            </div>
            <div class="insight-card ${{priceClass}}">
                <div class="insight-label">Avg Price This Month</div>
                <div class="insight-value">${{insights.currentMonth.avgPrice > 0 ? '$' + insights.currentMonth.avgPrice.toLocaleString('en-US', {{maximumFractionDigits: 0}}) : 'N/A'}}</div>
                <div class="insight-detail ${{priceClass}}">${{insights.priceChange >= 0 ? '+' : ''}}${{insights.priceChange.toFixed(1)}}% vs last month</div>
            </div>
            <div class="insight-card ${{volClass}}">
                <div class="insight-label">Volume Change</div>
                <div class="insight-value ${{volClass}}">${{insights.volumeChange >= 0 ? '+' : ''}}${{insights.volumeChange.toFixed(1)}}%</div>
                <div class="insight-detail">Month-over-month</div>
            </div>
            <div class="insight-card ${{trendClass}}">
                <div class="insight-label">Overall Trend</div>
                <div class="insight-value ${{trendClass}}">${{trendSymbol}} $${{Math.abs(insights.trend.monthlyChange).toLocaleString('en-US', {{maximumFractionDigits: 0}})}}/mo</div>
                <div class="insight-detail">Based on ${{insights.totalFiltered}} sales</div>
            </div>
        </div>
    `;

    // Summary text
    const direction = insights.priceChange >= 0 ? 'rising' : 'falling';
    const summaryClass = insights.priceChange >= 0 ? '' : 'declining';
    html += `
        <div class="trend-summary ${{summaryClass}}">
            <h3>Market Insight</h3>
            <p>Market Overview: Prices are ${{direction}} with ${{insights.currentMonth.count}} sales this month${{insights.currentMonth.avgPrice > 0 ? ' averaging $' + insights.currentMonth.avgPrice.toLocaleString('en-US', {{maximumFractionDigits: 0}}) : ''}}. Total filtered: ${{insights.totalFiltered}} properties.</p>
        </div>
    `;

    document.getElementById('insights-container').innerHTML = html;
}}

// Render category stats (clickable)
function renderCategoryStats(insights) {{
    if (!insights) {{
        document.getElementById('category-stats').innerHTML = '';
        return;
    }}

    let html = '';
    categories.forEach(cat => {{
        if (insights.catStats[cat]) {{
            const isSelected = currentFilters.type === cat;
            html += `
                <div class="cat-stat ${{isSelected ? 'selected' : ''}}"
                     style="border-top-color: ${{categoryColors[cat] || '#1a73e8'}};"
                     onclick="selectCategory('${{cat}}')">
                    <div class="cat-stat-name">${{cat}}</div>
                    <div class="cat-stat-value">${{insights.catStats[cat].count}}</div>
                    <div class="cat-stat-detail">Avg: $${{(insights.catStats[cat].avgPrice/1000).toFixed(0)}}k</div>
                </div>
            `;
        }}
    }});
    document.getElementById('category-stats').innerHTML = html;
}}

// Select category by clicking on stat card
function selectCategory(cat) {{
    const select = document.getElementById('filter-type');
    if (currentFilters.type === cat) {{
        select.value = 'all';
        currentFilters.type = 'all';
    }} else {{
        select.value = cat;
        currentFilters.type = cat;
    }}
    applyFilters();
}}

// Draw all charts
function drawCharts(data) {{
    const weekly = aggregateByWeek(data);
    const sortedWeeks = Object.keys(weekly).sort();

    // Chart 1: Stacked Area - Sales Volume
    const volumeTraces = [];
    categories.forEach(cat => {{
        const yVals = sortedWeeks.map(w => weekly[w].byType[cat]?.count || 0);
        if (yVals.some(v => v > 0)) {{
            volumeTraces.push({{
                x: sortedWeeks,
                y: yVals,
                name: cat,
                type: 'scatter',
                mode: 'lines',
                stackgroup: 'one',
                fillcolor: categoryColors[cat] + '80',
                line: {{ color: categoryColors[cat], width: 1 }}
            }});
        }}
    }});

    Plotly.newPlot('volume-chart', volumeTraces, {{
        xaxis: {{ title: 'Week Starting', tickangle: -45 }},
        yaxis: {{ title: 'Number of Sales' }},
        hovermode: 'x unified',
        showlegend: true,
        legend: {{ orientation: 'h', y: -0.2 }},
        margin: {{ b: 100 }},
        shapes: [{{ type: 'line', x0: todayStr, x1: todayStr, y0: 0, y1: 1, yref: 'paper', line: {{ color: '#ea4335', width: 2, dash: 'dash' }} }}],
        annotations: [{{ x: todayStr, y: 1, yref: 'paper', text: 'NOW', showarrow: false, font: {{ color: '#ea4335', size: 12 }}, yshift: 10 }}]
    }}, {{ responsive: true }});

    // Chart 2: Average Price Trends
    const priceTraces = [];
    categories.forEach(cat => {{
        const xVals = [], yVals = [];
        sortedWeeks.forEach(w => {{
            const prices = weekly[w].byType[cat]?.prices || [];
            if (prices.length > 0) {{
                xVals.push(w);
                yVals.push(prices.reduce((a, b) => a + b, 0) / prices.length);
            }}
        }});
        if (xVals.length > 0) {{
            priceTraces.push({{
                x: xVals, y: yVals, name: cat,
                type: 'scatter', mode: 'lines+markers',
                line: {{ color: categoryColors[cat], width: 2 }},
                marker: {{ size: 6 }},
                hovertemplate: '%{{x}}<br>' + cat + ': $%{{y:,.0f}}<extra></extra>'
            }});
        }}
    }});

    Plotly.newPlot('price-chart', priceTraces, {{
        xaxis: {{ title: 'Week Starting', tickangle: -45 }},
        yaxis: {{ title: 'Average Sale Price ($)', tickformat: ',.0f' }},
        hovermode: 'x unified',
        showlegend: true,
        legend: {{ orientation: 'h', y: -0.2 }},
        margin: {{ b: 100 }},
        shapes: [{{ type: 'line', x0: todayStr, x1: todayStr, y0: 0, y1: 1, yref: 'paper', line: {{ color: '#ea4335', width: 2, dash: 'dash' }} }}]
    }}, {{ responsive: true }});

    // Chart 3: Price per m² Trends
    const ppm2Traces = [];
    const ppm2Cats = ['House', 'Townhouse', 'Land'];
    ppm2Cats.forEach(cat => {{
        const xVals = [], yVals = [];
        sortedWeeks.forEach(w => {{
            const ppm2 = weekly[w].byType[cat]?.ppm2 || [];
            if (ppm2.length > 0) {{
                xVals.push(w);
                yVals.push(ppm2.reduce((a, b) => a + b, 0) / ppm2.length);
            }}
        }});
        if (xVals.length > 0) {{
            ppm2Traces.push({{
                x: xVals, y: yVals, name: cat,
                type: 'scatter', mode: 'lines+markers',
                line: {{ color: categoryColors[cat], width: 2 }},
                marker: {{ size: 6 }},
                hovertemplate: '%{{x}}<br>' + cat + ': $%{{y:,.0f}}/m²<extra></extra>'
            }});
        }}
    }});

    // Overall average ppm2
    const overallX = [], overallY = [];
    sortedWeeks.forEach(w => {{
        if (weekly[w].allPpm2.length > 0) {{
            overallX.push(w);
            overallY.push(weekly[w].allPpm2.reduce((a, b) => a + b, 0) / weekly[w].allPpm2.length);
        }}
    }});
    if (overallX.length > 0) {{
        ppm2Traces.push({{
            x: overallX, y: overallY, name: 'Market Average',
            type: 'scatter', mode: 'lines',
            line: {{ color: '#333', width: 2, dash: 'dot' }},
            hovertemplate: '%{{x}}<br>Market Avg: $%{{y:,.0f}}/m²<extra></extra>'
        }});
    }}

    Plotly.newPlot('ppm2-chart', ppm2Traces, {{
        xaxis: {{ title: 'Week Starting', tickangle: -45 }},
        yaxis: {{ title: 'Average $/m²', tickformat: ',.0f' }},
        hovermode: 'x unified',
        showlegend: true,
        legend: {{ orientation: 'h', y: -0.2 }},
        margin: {{ b: 100 }},
        shapes: [{{ type: 'line', x0: todayStr, x1: todayStr, y0: 0, y1: 1, yref: 'paper', line: {{ color: '#ea4335', width: 2, dash: 'dash' }} }}]
    }}, {{ responsive: true }});

    // Chart 4: Scatter Plot
    const scatterTraces = [];
    const typeGroups = {{}};
    data.forEach(d => {{
        if (!typeGroups[d.type]) typeGroups[d.type] = {{ x: [], y: [], text: [], urls: [] }};
        typeGroups[d.type].x.push(d.x);
        typeGroups[d.type].y.push(d.y);
        typeGroups[d.type].text.push(
            `${{d.address}}<br>${{d.beds}}bed ${{d.baths}}bath ${{d.cars}}car<br>${{d.suburb}}<br>$${{d.y.toLocaleString()}}${{d.ppm2 ? '<br>$' + d.ppm2.toLocaleString() + '/m²' : ''}}`
        );
        typeGroups[d.type].urls.push(d.url);
    }});

    Object.keys(typeGroups).forEach(type => {{
        if (typeGroups[type].x.length > 0) {{
            scatterTraces.push({{
                x: typeGroups[type].x, y: typeGroups[type].y,
                text: typeGroups[type].text, customdata: typeGroups[type].urls,
                name: type, type: 'scatter', mode: 'markers',
                marker: {{ color: categoryColors[type] || '#999', size: 8, opacity: 0.7 }},
                hovertemplate: '%{{text}}<extra></extra>'
            }});
        }}
    }});

    // Trend line
    if (data.length >= 2) {{
        const sorted = [...data].sort((a, b) => a.x.localeCompare(b.x));
        const firstDate = new Date(sorted[0].x);
        const lastDate = new Date(sorted[sorted.length - 1].x);
        let sumX = 0, sumY = 0, sumXY = 0, sumX2 = 0;
        const n = sorted.length;
        sorted.forEach(d => {{
            const x = (new Date(d.x) - firstDate) / (1000 * 60 * 60 * 24);
            sumX += x; sumY += d.y; sumXY += x * d.y; sumX2 += x * x;
        }});
        const slope = (n * sumXY - sumX * sumY) / (n * sumX2 - sumX * sumX);
        const intercept = (sumY - slope * sumX) / n;
        const trendY1 = intercept;
        const trendY2 = intercept + slope * ((lastDate - firstDate) / (1000 * 60 * 60 * 24));
        scatterTraces.push({{
            x: [sorted[0].x, sorted[sorted.length - 1].x], y: [trendY1, trendY2],
            name: 'Market Trend', type: 'scatter', mode: 'lines',
            line: {{ color: '#333', width: 3, dash: 'dash' }}, hoverinfo: 'skip'
        }});
    }}

    Plotly.newPlot('scatter-chart', scatterTraces, {{
        xaxis: {{ title: 'Sold Date', tickangle: -45 }},
        yaxis: {{ title: 'Sale Price ($)', tickformat: ',.0f' }},
        hovermode: 'closest',
        showlegend: true,
        legend: {{ orientation: 'h', y: -0.15 }},
        margin: {{ b: 100 }},
        shapes: [{{ type: 'line', x0: todayStr, x1: todayStr, y0: 0, y1: 1, yref: 'paper', line: {{ color: '#ea4335', width: 2, dash: 'dash' }} }}],
        annotations: [{{ x: todayStr, y: 1, yref: 'paper', text: 'NOW', showarrow: false, font: {{ color: '#ea4335', size: 12 }}, yshift: 10 }}]
    }}, {{ responsive: true }});

    // Click handler
    document.getElementById('scatter-chart').on('plotly_click', function(d) {{
        const url = d.points[0].customdata;
        if (url) window.open(url, '_blank');
    }});
}}

// Apply filters and redraw
function applyFilters() {{
    currentFilters.type = document.getElementById('filter-type').value;
    currentFilters.beds = document.getElementById('filter-beds').value;
    currentFilters.baths = document.getElementById('filter-baths').value;
    currentFilters.cars = document.getElementById('filter-cars').value;

    const filtered = filterData();
    const insights = calculateInsights(filtered);

    document.getElementById('filtered-count').textContent = filtered.length;

    renderInsights(insights);
    renderCategoryStats(insights);
    drawCharts(filtered);
}}

// Reset all filters
function resetFilters() {{
    document.getElementById('filter-type').value = 'all';
    document.getElementById('filter-beds').value = 'all';
    document.getElementById('filter-baths').value = 'all';
    document.getElementById('filter-cars').value = 'all';
    currentFilters = {{ type: 'all', beds: 'all', baths: 'all', cars: 'all' }};
    applyFilters();
}}

// Event listeners for filters
document.getElementById('filter-type').addEventListener('change', applyFilters);
document.getElementById('filter-beds').addEventListener('change', applyFilters);
document.getElementById('filter-baths').addEventListener('change', applyFilters);
document.getElementById('filter-cars').addEventListener('change', applyFilters);

// Initial render
applyFilters();
</script>
</body></html>
"""
        filename = "baulkandcastle_timeline.html"
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(html)
        print(f"Generated {filename}")

    def _build_insights_panel(self, insights: Dict) -> str:
        """Build the insights panel HTML."""
        price_change = insights.get('price_change', 0)
        vol_change = insights.get('volume_change', 0)
        current = insights.get('current_month', {})
        prev = insights.get('prev_month', {})

        # Determine trend direction
        price_class = 'positive' if price_change >= 0 else 'negative'
        vol_class = 'positive' if vol_change >= 0 else 'negative'

        html = f'''
        <div class="insights-grid">
            <div class="insight-card">
                <div class="insight-label">This Month Sales</div>
                <div class="insight-value">{current.get('count', 0)}</div>
                <div class="insight-detail">vs {prev.get('count', 0)} last month</div>
            </div>
            <div class="insight-card {price_class}">
                <div class="insight-label">Avg Price This Month</div>
                <div class="insight-value">${current.get('avg_price', 0):,.0f}</div>
                <div class="insight-detail {price_class}">{price_change:+.1f}% vs last month</div>
            </div>
            <div class="insight-card {vol_class}">
                <div class="insight-label">Volume Change</div>
                <div class="insight-value {vol_class}">{vol_change:+.1f}%</div>
                <div class="insight-detail">Month-over-month</div>
            </div>
        '''

        # Add category trend cards
        for trend in insights.get('trends', [])[:3]:
            direction_class = 'positive' if trend['direction'] == 'upward' else 'negative'
            direction_symbol = '↑' if trend['direction'] == 'upward' else '↓'
            monthly_change = abs(trend['monthly_change'])
            html += f'''
            <div class="insight-card {direction_class}">
                <div class="insight-label">{trend['category']} Trend</div>
                <div class="insight-value {direction_class}">{direction_symbol} ${monthly_change:,.0f}/mo</div>
                <div class="insight-detail">Based on {trend['count']} sales (R²: {trend['r2']:.0%})</div>
            </div>
            '''

        html += '</div>'

        # Add summary text
        if insights.get('summary'):
            trend_class = '' if price_change >= 0 else 'declining'
            html += f'''
            <div class="trend-summary {trend_class}">
                <h3>Market Insight</h3>
                <p>{insights['summary']}</p>
            </div>
            '''

        return html

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding='utf-8')

    parser = argparse.ArgumentParser(description="Baulkham Hills & Castle Hill Property Tracker")
    parser.add_argument("--reports-only", action="store_true", help="Generate reports only without scraping")
    parser.add_argument("--sale-pages", type=int, default=0, help="Number of pages to scrape for sale listings (0=all, default: 0 for full, 1 for daily)")
    parser.add_argument("--sold-pages", type=int, default=30, help="Number of pages to scrape for sold listings (default: 30)")
    parser.add_argument("--daily", action="store_true", help="Quick daily scan (uses --sale-pages and --sold-pages, defaults to 1 each)")
    parser.add_argument("--update-catchment", action="store_true", help="Scrape Excelsior catchment and update property flags only")
    parser.add_argument("--accuracy-report", action="store_true", help="Show prediction accuracy comparison report")

    args = parser.parse_args()

    scraper = BaulkandcastleScraper()

    if args.accuracy_report:
        # Print prediction accuracy report to terminal
        report = scraper.db.get_prediction_accuracy_report()
        comparisons = report['comparisons']
        stats = report['stats']

        print(f"\n{'='*80}")
        print("PREDICTION ACCURACY REPORT")
        print(f"Comparing predictions/estimates against actual sold prices")
        print(f"{'='*80}")

        print(f"\n{'--- SUMMARY STATISTICS ---':^80}")
        print(f"\n{'Model':<20} {'Count':<10} {'MAPE':<15} {'Median Error':<15}")
        print("-" * 60)
        print(f"{'Listed Price':<20} {stats['listed']['count']:<10} {str(stats['listed']['mape'])+'%' if stats['listed']['mape'] else 'N/A':<15} {str(stats['listed']['median_error'])+'%' if stats['listed']['median_error'] else 'N/A':<15}")
        print(f"{'XGBoost':<20} {stats['xgboost']['count']:<10} {str(stats['xgboost']['mape'])+'%' if stats['xgboost']['mape'] else 'N/A':<15} {str(stats['xgboost']['median_error'])+'%' if stats['xgboost']['median_error'] else 'N/A':<15}")
        print(f"{'Domain Estimate':<20} {stats['domain']['count']:<10} {str(stats['domain']['mape'])+'%' if stats['domain']['mape'] else 'N/A':<15} {str(stats['domain']['median_error'])+'%' if stats['domain']['median_error'] else 'N/A':<15}")

        print(f"\n{'--- INDIVIDUAL COMPARISONS ---':^80}")
        print(f"\n{'Address':<45} {'Sold':<12} {'Listed':<12} {'XGBoost':<12} {'Domain':<12} {'Best':<8}")
        print("-" * 100)

        for c in comparisons[:30]:
            addr = c['address'][:43] if len(c['address']) > 43 else c['address']
            sold = f"${c['sold_price']:,}"

            if c['listed_error_pct'] is not None:
                listed = f"{c['listed_error_pct']:+.1f}%"
            else:
                listed = "-"

            if c['xgboost_error_pct'] is not None:
                xgb = f"{c['xgboost_error_pct']:+.1f}%"
            else:
                xgb = "-"

            if c['domain_error_pct'] is not None:
                domain = f"{c['domain_error_pct']:+.1f}%"
            else:
                domain = "-"

            # Find winner
            errors = []
            if c['listed_error_pct'] is not None:
                errors.append(('Listed', abs(c['listed_error_pct'])))
            if c['xgboost_error_pct'] is not None:
                errors.append(('XGBoost', abs(c['xgboost_error_pct'])))
            if c['domain_error_pct'] is not None:
                errors.append(('Domain', abs(c['domain_error_pct'])))
            winner = min(errors, key=lambda x: x[1])[0] if errors else "-"

            print(f"{addr:<45} {sold:<12} {listed:<12} {xgb:<12} {domain:<12} {winner:<8}")

        print(f"\n{'='*80}")
        print(f"Total sold properties analyzed: {stats['total_sold']}")
        print(f"Properties with at least one prediction: {stats['with_comparisons']}")
        print(f"{'='*80}\n")

    elif args.reports_only:
        scraper.generate_all_reports()
        scraper.print_terminal_summary()
        scraper.output_json_summary()
    elif args.update_catchment:
        asyncio.run(scraper.run_update_catchment())
    elif args.daily:
        # Daily mode: default to 1 page each unless overridden
        sale_pages = args.sale_pages if args.sale_pages > 0 else 1
        sold_pages = args.sold_pages if args.sold_pages != 30 else 1  # Default 1 for daily unless explicitly set
        asyncio.run(scraper.run_daily(sale_pages=sale_pages, sold_pages=sold_pages))
    else:
        asyncio.run(scraper.run_all(sold_pages=args.sold_pages))
