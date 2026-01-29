"""
Unit tests for Domain Estimator parsing and database storage.

Uses the actual snapshot from 4/52-54 Kerrs Road, Castle Hill as the reference test case.

Run tests:
    python test_domain_estimator.py
    python -m pytest test_domain_estimator.py -v
"""

import unittest
import sqlite3
import os
from datetime import datetime
from domain_estimator_helper import (
    parse_snapshot_text,
    parse_price_string,
    address_to_domain_url,
    DomainEstimate,
    save_estimate,
    DB_PATH
)

# Actual snapshot from 4/52-54 Kerrs Road, Castle Hill (captured 2026-01-21)
KERRS_ROAD_SNAPSHOT = """
- document:
  - banner:
    - link "Domain homepage" [ref=e1]:
      - /url: https://www.domain.com.au/
      - img
  - main:
    - text: For sale
    - heading "Just Listed" [ref=e20] [level=2]
    - heading "4/52-54 Kerrs Road, Castle Hill NSW 2154" [ref=e21] [level=1]
    - text: 3 Beds 2 Baths 2 Parking 4,277m² •Townhouse
    - link "View listing" [ref=e22]:
      - /url: https://www.domain.com.au/4-52-54-kerrs-road-castle-hill-nsw-2154-2020510444
    - heading "Property value" [ref=e23] [level=3]
    - heading "Property value estimate" [ref=e24] [level=2]
    - heading "Low" [ref=e25] [level=4]
    - text: $1.33m
    - heading "Mid" [ref=e26] [level=4]
    - text: $1.54m
    - heading "High" [ref=e27] [level=4]
    - text: $1.75m High accuracy
    - button [ref=e28]
    - text: "Updated: 16 Jan, 2026"
    - heading "Rental estimate" [ref=e29] [level=4]
    - button [ref=e30] [nth=1]
    - paragraph: per week
    - paragraph: $860 +2.93% Rental yield
    - text: High accuracy
    - paragraph: "Updated: 15 Jan, 2026"
    - link "agent photo" [ref=e32]:
      - /url: https://www.domain.com.au/real-estate-agent/jack-ho-1898030
      - img "agent photo"
    - link "Jack Ho Lead agent" [ref=e33]:
      - /url: https://www.domain.com.au/real-estate-agent/jack-ho-1898030
    - heading "Property features" [ref=e41] [level=3]
    - list:
      - listitem: Air Conditioning
      - listitem: Alarm System
      - listitem: Built In Robes
      - listitem: Courtyard
      - listitem: Remote Garage
    - heading "Property history" [ref=e42] [level=2]
    - list:
      - listitem:
        - text: Aug 2021
        - figure
        - text: Sold $1.2788m PRIVATE TREATY Sold by
        - link "Cunningham & Co" [ref=e46] [nth=1]:
          - /url: https://www.domain.com.au/real-estate-agencies/cunninghamco-12190
        - text: 8days listed
"""

# Expected values from the manual test (what we saved to DB)
EXPECTED_VALUES = {
    'beds': 3,
    'baths': 2,
    'parking': 2,
    'land_size': '4277',
    'property_type': 'Townhouse',
    'estimate_low': 1330000,
    'estimate_mid': 1540000,
    'estimate_high': 1750000,
    'estimate_accuracy': 'High',
    'rental_weekly': 860,
    'rental_yield': 2.93,
    'last_sold_price': 1278800,
    'last_sold_days_listed': 8,
    'listing_status': 'For Sale - Just Listed',
}


class TestPriceStringParsing(unittest.TestCase):
    """Test the parse_price_string function."""

    def test_millions_shorthand(self):
        self.assertEqual(parse_price_string('$1.33m'), 1330000)
        self.assertEqual(parse_price_string('$1.54m'), 1540000)
        self.assertEqual(parse_price_string('$1.75m'), 1750000)
        self.assertEqual(parse_price_string('$2.5M'), 2500000)

    def test_full_numbers(self):
        self.assertEqual(parse_price_string('$1,278,800'), 1278800)
        self.assertEqual(parse_price_string('$1278800'), 1278800)
        self.assertEqual(parse_price_string('1278800'), 1278800)

    def test_thousands_shorthand(self):
        self.assertEqual(parse_price_string('$860k'), 860000)
        self.assertEqual(parse_price_string('$500K'), 500000)

    def test_edge_cases(self):
        self.assertIsNone(parse_price_string(''))
        self.assertIsNone(parse_price_string(None))


class TestAddressToUrl(unittest.TestCase):
    """Test the address_to_domain_url function."""

    def test_unit_address(self):
        url = address_to_domain_url('4/52-54 Kerrs Road Castle Hill', 'Castle Hill')
        self.assertEqual(url, 'https://www.domain.com.au/property-profile/4-52-54-kerrs-road-castle-hill-nsw-2154')

    def test_simple_address(self):
        url = address_to_domain_url('15 Smith Street', 'Castle Hill')
        self.assertEqual(url, 'https://www.domain.com.au/property-profile/15-smith-street-castle-hill-nsw-2154')

    def test_baulkham_hills(self):
        url = address_to_domain_url('22 Jones Road', 'Baulkham Hills')
        self.assertEqual(url, 'https://www.domain.com.au/property-profile/22-jones-road-baulkham-hills-nsw-2153')

    def test_address_with_suburb_suffix(self):
        # Address already contains suburb name
        url = address_to_domain_url('15 Smith Street Castle Hill', 'Castle Hill')
        self.assertEqual(url, 'https://www.domain.com.au/property-profile/15-smith-street-castle-hill-nsw-2154')


class TestSnapshotParsing(unittest.TestCase):
    """Test the parse_snapshot_text function with real data."""

    def setUp(self):
        self.parsed = parse_snapshot_text(KERRS_ROAD_SNAPSHOT)

    def test_beds_baths_parking(self):
        self.assertEqual(self.parsed.get('beds'), EXPECTED_VALUES['beds'])
        self.assertEqual(self.parsed.get('baths'), EXPECTED_VALUES['baths'])
        self.assertEqual(self.parsed.get('parking'), EXPECTED_VALUES['parking'])

    def test_land_size(self):
        self.assertEqual(self.parsed.get('land_size'), EXPECTED_VALUES['land_size'])

    def test_property_type(self):
        self.assertEqual(self.parsed.get('property_type'), EXPECTED_VALUES['property_type'])

    def test_estimate_low(self):
        self.assertEqual(self.parsed.get('estimate_low'), EXPECTED_VALUES['estimate_low'])

    def test_estimate_mid(self):
        self.assertEqual(self.parsed.get('estimate_mid'), EXPECTED_VALUES['estimate_mid'])

    def test_estimate_high(self):
        self.assertEqual(self.parsed.get('estimate_high'), EXPECTED_VALUES['estimate_high'])

    def test_estimate_accuracy(self):
        self.assertEqual(self.parsed.get('estimate_accuracy'), EXPECTED_VALUES['estimate_accuracy'])

    def test_rental_weekly(self):
        self.assertEqual(self.parsed.get('rental_weekly'), EXPECTED_VALUES['rental_weekly'])

    def test_rental_yield(self):
        self.assertEqual(self.parsed.get('rental_yield'), EXPECTED_VALUES['rental_yield'])

    def test_last_sold_price(self):
        # Note: $1.2788m = 1278800
        self.assertEqual(self.parsed.get('last_sold_price'), EXPECTED_VALUES['last_sold_price'])

    def test_last_sold_days_listed(self):
        self.assertEqual(self.parsed.get('last_sold_days_listed'), EXPECTED_VALUES['last_sold_days_listed'])

    def test_listing_status(self):
        self.assertEqual(self.parsed.get('listing_status'), EXPECTED_VALUES['listing_status'])


class TestDatabaseIntegration(unittest.TestCase):
    """Test that estimates are saved to database correctly."""

    def test_compare_with_saved_record(self):
        """Compare parsed values with what we manually saved."""
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM domain_estimates WHERE property_id = '2020510444'
            ''')
            row = cursor.fetchone()

            if row is None:
                self.skipTest("Reference record not found in database")

            saved = dict(row)

            # Compare key fields
            self.assertEqual(saved['estimate_low'], EXPECTED_VALUES['estimate_low'])
            self.assertEqual(saved['estimate_mid'], EXPECTED_VALUES['estimate_mid'])
            self.assertEqual(saved['estimate_high'], EXPECTED_VALUES['estimate_high'])
            self.assertEqual(saved['beds'], EXPECTED_VALUES['beds'])
            self.assertEqual(saved['baths'], EXPECTED_VALUES['baths'])
            self.assertEqual(saved['parking'], EXPECTED_VALUES['parking'])

    def test_parsed_matches_saved(self):
        """Ensure the parser produces the same values as the saved record."""
        parsed = parse_snapshot_text(KERRS_ROAD_SNAPSHOT)

        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM domain_estimates WHERE property_id = '2020510444'
            ''')
            row = cursor.fetchone()

            if row is None:
                self.skipTest("Reference record not found in database")

            saved = dict(row)

            # These should match
            self.assertEqual(parsed.get('estimate_low'), saved['estimate_low'],
                           f"estimate_low mismatch: parsed={parsed.get('estimate_low')}, saved={saved['estimate_low']}")
            self.assertEqual(parsed.get('estimate_mid'), saved['estimate_mid'],
                           f"estimate_mid mismatch: parsed={parsed.get('estimate_mid')}, saved={saved['estimate_mid']}")
            self.assertEqual(parsed.get('estimate_high'), saved['estimate_high'],
                           f"estimate_high mismatch: parsed={parsed.get('estimate_high')}, saved={saved['estimate_high']}")
            self.assertEqual(parsed.get('beds'), saved['beds'],
                           f"beds mismatch: parsed={parsed.get('beds')}, saved={saved['beds']}")
            self.assertEqual(parsed.get('baths'), saved['baths'],
                           f"baths mismatch: parsed={parsed.get('baths')}, saved={saved['baths']}")
            self.assertEqual(parsed.get('parking'), saved['parking'],
                           f"parking mismatch: parsed={parsed.get('parking')}, saved={saved['parking']}")


def run_quick_validation():
    """Quick validation without full test suite."""
    print("=" * 60)
    print("Domain Estimator Parser Validation")
    print("=" * 60)
    print(f"\nTest case: 4/52-54 Kerrs Road, Castle Hill")
    print("-" * 60)

    parsed = parse_snapshot_text(KERRS_ROAD_SNAPSHOT)

    checks = [
        ('beds', 3),
        ('baths', 2),
        ('parking', 2),
        ('land_size', '4277'),
        ('property_type', 'Townhouse'),
        ('estimate_low', 1330000),
        ('estimate_mid', 1540000),
        ('estimate_high', 1750000),
        ('estimate_accuracy', 'High'),
        ('rental_weekly', 860),
        ('rental_yield', 2.93),
        ('last_sold_price', 1278800),
        ('last_sold_days_listed', 8),
        ('listing_status', 'For Sale - Just Listed'),
    ]

    all_passed = True
    for field, expected in checks:
        actual = parsed.get(field)
        status = "PASS" if actual == expected else "FAIL"
        if actual != expected:
            all_passed = False
        print(f"  [{status}] {field}: {actual} (expected: {expected})")

    print("-" * 60)
    if all_passed:
        print("All checks PASSED")
    else:
        print("Some checks FAILED - parser needs adjustment")
    print("=" * 60)

    return all_passed


if __name__ == '__main__':
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == '--quick':
        # Quick validation mode
        success = run_quick_validation()
        sys.exit(0 if success else 1)
    else:
        # Full test suite
        unittest.main(verbosity=2)
