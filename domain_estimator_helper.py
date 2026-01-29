"""
Domain Estimator Helper
Utilities for generating Domain Property Profile URLs and storing estimate data.

Usage with Claude Code:
    /domain-estimator  - Fetches estimates using agent-browser MCP

Standalone usage:
    python domain_estimator_helper.py --batch                    # Estimate only new/unestimated properties (default)
    python domain_estimator_helper.py --batch --mode today-new   # Only today's new listings
    python domain_estimator_helper.py --batch --mode all         # Re-estimate ALL for-sale properties
    python domain_estimator_helper.py --stats                    # Show estimate coverage stats
    python domain_estimator_helper.py --list-urls                # Show URLs to scrape

Modes:
    new-only   - Only estimate properties that have never been estimated (DEFAULT)
    today-new  - Only estimate properties first seen today (new listings)
    all        - Re-estimate all for-sale properties (updates existing estimates)
"""

import re
import sqlite3
import time
import json
from datetime import datetime
from typing import Optional, List, Tuple, Dict, Any
from dataclasses import dataclass, asdict

# Playwright for direct browser control
try:
    from playwright.sync_api import sync_playwright, Page, Browser
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    print("WARNING: Playwright not installed. Run: pip install playwright && playwright install chromium")

DB_PATH = "C:/Tools PHPC/baulkandcastle/baulkandcastle_properties.db"

POSTCODES = {
    "BAULKHAM HILLS": "2153",
    "CASTLE HILL": "2154"
}


@dataclass
class DomainEstimate:
    """Full Domain estimate data structure."""
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


def address_to_domain_url(address: str, suburb: str) -> str:
    """Convert property address to Domain Property Profile URL.

    Domain format: property-profile/{street-number}-{street-name}-{suburb}-nsw-{postcode}
    Example: property-profile/12-smith-street-castle-hill-nsw-2154
    """
    addr_clean = address.lower().strip()

    # Remove suburb name if it appears at the end of address
    suburb_lower = suburb.lower()
    for sub_variant in [suburb_lower, suburb_lower.replace(" ", "-")]:
        if addr_clean.endswith(sub_variant):
            addr_clean = addr_clean[:-len(sub_variant)].strip()
            addr_clean = addr_clean.rstrip(',').strip()

    # Clean special characters
    addr_slug = addr_clean.replace("'", "")
    addr_slug = addr_slug.replace(",", "")
    addr_slug = addr_slug.replace("/", "-")
    addr_slug = re.sub(r'\s+', '-', addr_slug)
    addr_slug = re.sub(r'-+', '-', addr_slug)
    addr_slug = addr_slug.strip('-')

    suburb_slug = suburb.lower().replace(" ", "-")
    postcode = POSTCODES.get(suburb.upper(), "2153")

    return f"https://www.domain.com.au/property-profile/{addr_slug}-{suburb_slug}-nsw-{postcode}"


def get_for_sale_properties(mode: str = 'all') -> List[Tuple[str, str, str, str]]:
    """Get current for-sale properties from database.

    Args:
        mode: 'all' - all for-sale properties
              'new-only' - only properties without existing estimates
              'today-new' - only properties first seen today (brand new listings)
    """
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()

        if mode == 'new-only':
            # Properties for sale that have never been estimated
            cursor.execute('''
                SELECT DISTINCT p.property_id, p.address, p.suburb, p.url
                FROM properties p
                JOIN listing_history h ON p.property_id = h.property_id
                WHERE h.status = 'sale'
                AND h.date = (SELECT MAX(date) FROM listing_history WHERE property_id = p.property_id)
                AND p.property_id NOT IN (SELECT property_id FROM domain_estimates)
                ORDER BY p.suburb, p.address
            ''')
        elif mode == 'today-new':
            # Only properties first seen today
            today = datetime.now().strftime('%Y-%m-%d')
            cursor.execute('''
                SELECT DISTINCT p.property_id, p.address, p.suburb, p.url
                FROM properties p
                JOIN listing_history h ON p.property_id = h.property_id
                WHERE h.status = 'sale'
                AND h.date = (SELECT MAX(date) FROM listing_history WHERE property_id = p.property_id)
                AND p.first_seen = ?
                ORDER BY p.suburb, p.address
            ''', (today,))
        else:
            # All for-sale properties
            cursor.execute('''
                SELECT DISTINCT p.property_id, p.address, p.suburb, p.url
                FROM properties p
                JOIN listing_history h ON p.property_id = h.property_id
                WHERE h.status = 'sale'
                AND h.date = (SELECT MAX(date) FROM listing_history WHERE property_id = p.property_id)
                ORDER BY p.suburb, p.address
            ''')
        return cursor.fetchall()


def get_estimate_stats() -> Dict[str, int]:
    """Get statistics about estimate coverage."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()

        # Total for sale
        cursor.execute('''
            SELECT COUNT(DISTINCT p.property_id)
            FROM properties p
            JOIN listing_history h ON p.property_id = h.property_id
            WHERE h.status = 'sale'
            AND h.date = (SELECT MAX(date) FROM listing_history WHERE property_id = p.property_id)
        ''')
        total_for_sale = cursor.fetchone()[0]

        # Already estimated
        cursor.execute('''
            SELECT COUNT(DISTINCT p.property_id)
            FROM properties p
            JOIN listing_history h ON p.property_id = h.property_id
            JOIN domain_estimates de ON p.property_id = de.property_id
            WHERE h.status = 'sale'
            AND h.date = (SELECT MAX(date) FROM listing_history WHERE property_id = p.property_id)
        ''')
        with_estimates = cursor.fetchone()[0]

        # New today without estimates
        today = datetime.now().strftime('%Y-%m-%d')
        cursor.execute('''
            SELECT COUNT(DISTINCT p.property_id)
            FROM properties p
            JOIN listing_history h ON p.property_id = h.property_id
            WHERE h.status = 'sale'
            AND h.date = (SELECT MAX(date) FROM listing_history WHERE property_id = p.property_id)
            AND p.first_seen = ?
            AND p.property_id NOT IN (SELECT property_id FROM domain_estimates)
        ''', (today,))
        new_today = cursor.fetchone()[0]

        return {
            'total_for_sale': total_for_sale,
            'with_estimates': with_estimates,
            'without_estimates': total_for_sale - with_estimates,
            'new_today_without_estimates': new_today
        }


def parse_price_string(price_str: str) -> Optional[int]:
    """Parse a price string like '$1.33m' or '$1,330,000' to integer."""
    if not price_str:
        return None

    price_str = price_str.strip().lower()

    # Handle millions shorthand ($1.33m)
    if 'm' in price_str:
        match = re.search(r'\$?([\d.]+)\s*m', price_str)
        if match:
            return int(float(match.group(1)) * 1_000_000)

    # Handle thousands shorthand ($800k)
    if 'k' in price_str:
        match = re.search(r'\$?([\d.]+)\s*k', price_str)
        if match:
            return int(float(match.group(1)) * 1_000)

    # Handle full numbers ($1,330,000)
    clean = re.sub(r'[^\d]', '', price_str)
    if clean:
        return int(clean)

    return None


def parse_snapshot_text(snapshot_text: str) -> Dict[str, Any]:
    """Parse agent-browser snapshot output to extract estimate data."""
    data = {}

    # Property type and details (e.g., "3 Beds 2 Baths 2 Parking 4,277m² •Townhouse")
    beds_match = re.search(r'(\d+)\s*Beds?', snapshot_text)
    baths_match = re.search(r'(\d+)\s*Baths?', snapshot_text)
    parking_match = re.search(r'(\d+)\s*Parking', snapshot_text)
    land_match = re.search(r'([\d,]+)m²', snapshot_text)
    type_match = re.search(r'•\s*(\w+)', snapshot_text)

    if beds_match:
        data['beds'] = int(beds_match.group(1))
    if baths_match:
        data['baths'] = int(baths_match.group(1))
    if parking_match:
        data['parking'] = int(parking_match.group(1))
    if land_match:
        data['land_size'] = land_match.group(1).replace(',', '')
    if type_match:
        data['property_type'] = type_match.group(1)

    # Property value estimates
    low_match = re.search(r'heading "Low".*?text:\s*(\$[\d.]+[mk]?)', snapshot_text, re.IGNORECASE | re.DOTALL)
    mid_match = re.search(r'heading "Mid".*?text:\s*(\$[\d.]+[mk]?)', snapshot_text, re.IGNORECASE | re.DOTALL)
    high_match = re.search(r'heading "High".*?text:\s*(\$[\d.]+[mk]?)', snapshot_text, re.IGNORECASE | re.DOTALL)

    if low_match:
        data['estimate_low'] = parse_price_string(low_match.group(1))
    if mid_match:
        data['estimate_mid'] = parse_price_string(mid_match.group(1))
    if high_match:
        data['estimate_high'] = parse_price_string(high_match.group(1))

    # Accuracy
    if 'High accuracy' in snapshot_text:
        data['estimate_accuracy'] = 'High'
    elif 'Medium accuracy' in snapshot_text:
        data['estimate_accuracy'] = 'Medium'
    elif 'Low accuracy' in snapshot_text:
        data['estimate_accuracy'] = 'Low'

    # Estimate date
    date_match = re.search(r'Updated:\s*(\d+\s+\w+,?\s+\d{4})', snapshot_text)
    if date_match:
        data['estimate_date'] = date_match.group(1)

    # Rental estimate - format: "paragraph: $860 +2.93% Rental yield"
    # or "$860/week" or "$860 per week"
    rental_match = re.search(r'\$(\d+)(?:\s*(?:\+|-)[\d.]+%)?\s*(?:Rental yield|per week|/week)', snapshot_text)
    if not rental_match:
        # Try alternate format: just "$XXX" near "Rental yield"
        rental_match = re.search(r'paragraph:\s*\$(\d+)', snapshot_text)
    yield_match = re.search(r'([\d.]+)%\s*Rental yield', snapshot_text)

    if rental_match:
        data['rental_weekly'] = int(rental_match.group(1))
    if yield_match:
        data['rental_yield'] = float(yield_match.group(1))

    # Sale history - format: "text: Sold $1.2788m PRIVATE TREATY"
    # or "Sold $1,278,800"
    sold_price_match = re.search(r'Sold\s+(\$[\d.,]+[mk]?)', snapshot_text, re.IGNORECASE)
    if sold_price_match:
        data['last_sold_price'] = parse_price_string(sold_price_match.group(1))

    # Sale date - format: "text: Aug 2021" before "Sold"
    sold_date_match = re.search(r'text:\s*(\w{3}\s+\d{4})\s*\n.*?Sold', snapshot_text, re.DOTALL)
    if sold_date_match:
        data['last_sold_date'] = sold_date_match.group(1)

    days_match = re.search(r'(\d+)\s*days?\s*listed', snapshot_text)
    if days_match:
        data['last_sold_days_listed'] = int(days_match.group(1))

    agent_match = re.search(r'Sold by.*?link "([^"]+)"', snapshot_text)
    if agent_match:
        data['last_sold_agent'] = agent_match.group(1)

    # Current listing
    if 'For sale' in snapshot_text or 'For Sale' in snapshot_text:
        data['listing_status'] = 'For Sale'
        if 'Just Listed' in snapshot_text:
            data['listing_status'] = 'For Sale - Just Listed'

    # Features
    features = []
    feature_section = re.search(r'Property features.*?heading', snapshot_text, re.DOTALL)
    if feature_section:
        for feat in re.findall(r'listitem:\s*([^\n]+)', feature_section.group(0)):
            features.append(feat.strip())
    if features:
        data['features'] = ','.join(features)

    return data


def scrape_property_with_page(page: Page, property_id: str, address: str, suburb: str, delay: float = 3.0) -> Optional[DomainEstimate]:
    """Scrape a single property using an existing Playwright page."""
    domain_url = address_to_domain_url(address, suburb)

    print(f"  Scraping: {address}")
    print(f"  URL: {domain_url}")

    try:
        # Navigate to the page (use domcontentloaded - networkidle is too strict for Domain)
        page.goto(domain_url, wait_until='domcontentloaded', timeout=60000)

        # Wait for content to render
        time.sleep(3)

        # Get all visible text content
        visible_text = page.inner_text('body')

        # Parse the content
        parsed = parse_page_content(page, visible_text)

        if not parsed.get('estimate_mid'):
            print(f"  WARNING: No estimate found for {address}")

        estimate = DomainEstimate(
            property_id=property_id,
            address=address,
            suburb=suburb,
            domain_url=domain_url,
            scraped_at=datetime.now().isoformat(),
            **parsed
        )

        low = parsed.get('estimate_low', 0) or 0
        mid = parsed.get('estimate_mid', 0) or 0
        high = parsed.get('estimate_high', 0) or 0
        print(f"  Estimate: ${low:,} - ${mid:,} - ${high:,}")

        # Delay between requests
        time.sleep(delay)

        return estimate

    except Exception as e:
        print(f"  ERROR: {e}")
        return None


def parse_page_content(page: Page, text: str) -> Dict[str, Any]:
    """Parse Domain property page content using Playwright selectors."""
    data = {}

    try:
        # Try to get estimate values directly from the page
        # Domain uses specific selectors for estimate values

        # Property details (beds, baths, parking, land size)
        beds_match = re.search(r'(\d+)\s*Beds?', text)
        baths_match = re.search(r'(\d+)\s*Baths?', text)
        parking_match = re.search(r'(\d+)\s*Parking', text)
        land_match = re.search(r'([\d,]+)\s*m²', text)

        if beds_match:
            data['beds'] = int(beds_match.group(1))
        if baths_match:
            data['baths'] = int(baths_match.group(1))
        if parking_match:
            data['parking'] = int(parking_match.group(1))
        if land_match:
            data['land_size'] = land_match.group(1).replace(',', '')

        # Property type
        for ptype in ['House', 'Townhouse', 'Unit', 'Apartment', 'Villa', 'Land', 'Acreage']:
            if ptype in text:
                data['property_type'] = ptype
                break

        # Estimate values - Domain has a summary like:
        # "estimated to be worth around $1.78m, with a range from $1.54m to $2.02m"
        summary_match = re.search(
            r'estimated to be worth around (\$[\d.,]+[mk]?)[,.]? with a range from (\$[\d.,]+[mk]?) to (\$[\d.,]+[mk]?)',
            text, re.IGNORECASE
        )

        if summary_match:
            data['estimate_mid'] = parse_price_string(summary_match.group(1))
            data['estimate_low'] = parse_price_string(summary_match.group(2))
            data['estimate_high'] = parse_price_string(summary_match.group(3))
        else:
            # Fallback: look for first three prices (usually Low, Mid, High in order)
            prices = re.findall(r'\$[\d.,]+[mk]', text, re.IGNORECASE)
            if len(prices) >= 3:
                data['estimate_low'] = parse_price_string(prices[0])
                data['estimate_mid'] = parse_price_string(prices[1])
                data['estimate_high'] = parse_price_string(prices[2])

        # Accuracy
        if 'High accuracy' in text:
            data['estimate_accuracy'] = 'High'
        elif 'Medium accuracy' in text:
            data['estimate_accuracy'] = 'Medium'
        elif 'Low accuracy' in text:
            data['estimate_accuracy'] = 'Low'

        # Rental estimate
        rental_match = re.search(r'\$(\d+)\s*(?:/week|per week|pw)', text, re.IGNORECASE)
        if rental_match:
            data['rental_weekly'] = int(rental_match.group(1))

        yield_match = re.search(r'([\d.]+)%\s*(?:Rental yield|yield)', text, re.IGNORECASE)
        if yield_match:
            data['rental_yield'] = float(yield_match.group(1))

        # Last sold
        sold_match = re.search(r'Sold[^\$]*(\$[\d.,]+[mk]?)', text, re.IGNORECASE)
        if sold_match:
            data['last_sold_price'] = parse_price_string(sold_match.group(1))

        date_match = re.search(r'(\w{3}\s+\d{4})\s*(?:Sold|sold)', text)
        if date_match:
            data['last_sold_date'] = date_match.group(1)

        # Listing status
        if 'For sale' in text or 'For Sale' in text:
            data['listing_status'] = 'For Sale'

    except Exception as e:
        print(f"    Parse error: {e}")

    return data


def scrape_property(property_id: str, address: str, suburb: str, delay: float = 3.0) -> Optional[DomainEstimate]:
    """Scrape a single property (standalone mode - creates new browser)."""
    if not PLAYWRIGHT_AVAILABLE:
        print("ERROR: Playwright not available")
        return None

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        result = scrape_property_with_page(page, property_id, address, suburb, delay)
        browser.close()
        return result


def save_estimate(estimate: DomainEstimate):
    """Save a Domain estimate to the database."""
    now = datetime.now().isoformat()

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()

        # Insert/update current estimate
        cursor.execute('''
            INSERT OR REPLACE INTO domain_estimates (
                property_id, address, suburb, property_type, beds, baths, parking, land_size,
                estimate_low, estimate_mid, estimate_high, estimate_accuracy, estimate_date,
                rental_weekly, rental_yield, rental_accuracy, rental_estimate_date,
                last_sold_date, last_sold_price, last_sold_agent, last_sold_days_listed,
                listing_status, listing_agent, listing_agency, features, domain_url, scraped_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            estimate.property_id, estimate.address, estimate.suburb, estimate.property_type,
            estimate.beds, estimate.baths, estimate.parking, estimate.land_size,
            estimate.estimate_low, estimate.estimate_mid, estimate.estimate_high,
            estimate.estimate_accuracy, estimate.estimate_date,
            estimate.rental_weekly, estimate.rental_yield, estimate.rental_accuracy,
            estimate.rental_estimate_date, estimate.last_sold_date, estimate.last_sold_price,
            estimate.last_sold_agent, estimate.last_sold_days_listed, estimate.listing_status,
            estimate.listing_agent, estimate.listing_agency, estimate.features,
            estimate.domain_url, now
        ))

        # Also insert into history
        cursor.execute('''
            INSERT INTO domain_estimates_history (
                property_id, address, suburb, property_type, beds, baths, parking, land_size,
                estimate_low, estimate_mid, estimate_high, estimate_accuracy, estimate_date,
                rental_weekly, rental_yield, rental_accuracy, rental_estimate_date,
                last_sold_date, last_sold_price, last_sold_agent, last_sold_days_listed,
                listing_status, listing_agent, listing_agency, features, domain_url, scraped_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            estimate.property_id, estimate.address, estimate.suburb, estimate.property_type,
            estimate.beds, estimate.baths, estimate.parking, estimate.land_size,
            estimate.estimate_low, estimate.estimate_mid, estimate.estimate_high,
            estimate.estimate_accuracy, estimate.estimate_date,
            estimate.rental_weekly, estimate.rental_yield, estimate.rental_accuracy,
            estimate.rental_estimate_date, estimate.last_sold_date, estimate.last_sold_price,
            estimate.last_sold_agent, estimate.last_sold_days_listed, estimate.listing_status,
            estimate.listing_agent, estimate.listing_agency, estimate.features,
            estimate.domain_url, now
        ))

        conn.commit()


def batch_scrape(limit: Optional[int] = None, suburb: Optional[str] = None, delay: float = 3.0, headless: bool = True, mode: str = 'all'):
    """Batch scrape for-sale properties using Playwright.

    Args:
        limit: Maximum number of properties to scrape
        suburb: Filter by suburb name
        delay: Seconds between requests
        headless: Run browser in headless mode
        mode: 'all' - scrape all for-sale properties
              'new-only' - only properties without existing estimates
              'today-new' - only properties first seen today
    """
    if not PLAYWRIGHT_AVAILABLE:
        print("ERROR: Playwright not available. Install with: pip install playwright && playwright install chromium")
        return

    # Show stats first
    stats = get_estimate_stats()
    print(f"\n{'='*60}")
    print(f"Domain Estimator - Current Stats")
    print(f"{'='*60}")
    print(f"Total for sale:        {stats['total_for_sale']}")
    print(f"Already estimated:     {stats['with_estimates']}")
    print(f"Without estimates:     {stats['without_estimates']}")
    print(f"New today (no est):    {stats['new_today_without_estimates']}")
    print(f"{'='*60}\n")

    properties = get_for_sale_properties(mode=mode)

    if suburb:
        properties = [p for p in properties if suburb.upper() in p[2].upper()]

    if limit:
        properties = properties[:limit]

    mode_desc = {
        'all': 'All for-sale properties',
        'new-only': 'Only properties without estimates',
        'today-new': 'Only new listings from today'
    }

    print(f"\n{'='*60}")
    print(f"Domain Estimator Batch Scrape (Playwright)")
    print(f"{'='*60}")
    print(f"Mode: {mode} - {mode_desc.get(mode, mode)}")
    print(f"Properties to scrape: {len(properties)}")
    print(f"Delay between requests: {delay}s")
    print(f"Headless: {headless}")
    print(f"{'='*60}\n")

    success_count = 0
    error_count = 0

    with sync_playwright() as p:
        print("Launching browser...")
        browser = p.chromium.launch(headless=headless)
        page = browser.new_page()

        try:
            for i, (prop_id, address, prop_suburb, url) in enumerate(properties, 1):
                print(f"\n[{i}/{len(properties)}] {address}, {prop_suburb}")

                estimate = scrape_property_with_page(page, prop_id, address, prop_suburb, delay)

                if estimate and estimate.estimate_mid:
                    save_estimate(estimate)
                    success_count += 1
                    print(f"  [OK] Saved to database")
                else:
                    error_count += 1
                    print(f"  [SKIP] No estimate found")

        except KeyboardInterrupt:
            print("\n\nInterrupted by user!")
        finally:
            print("\nClosing browser...")
            browser.close()

    print(f"\n{'='*60}")
    print(f"Batch Scrape Complete")
    print(f"{'='*60}")
    print(f"Success: {success_count}")
    print(f"Errors:  {error_count}")
    print(f"{'='*60}\n")


def get_estimate_for_property(property_id: str) -> Optional[Dict[str, Any]]:
    """Get the latest Domain estimate for a property."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM domain_estimates WHERE property_id = ?
        ''', (property_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


def generate_url_list(limit: Optional[int] = None, suburb: Optional[str] = None) -> List[dict]:
    """Generate list of properties with their Domain URLs."""
    properties = get_for_sale_properties()

    if suburb:
        properties = [p for p in properties if suburb.upper() in p[2].upper()]

    if limit:
        properties = properties[:limit]

    return [
        {
            "property_id": p[0],
            "address": p[1],
            "suburb": p[2],
            "domain_url": address_to_domain_url(p[1], p[2])
        }
        for p in properties
    ]


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Domain Estimator Helper")
    parser.add_argument("--batch", action="store_true", help="Batch scrape for-sale properties")
    parser.add_argument("--mode", type=str, default="new-only", choices=["all", "new-only", "today-new"],
                        help="Estimation mode: 'all' = all properties, 'new-only' = only unestimated (default), 'today-new' = only today's new listings")
    parser.add_argument("--list-urls", action="store_true", help="List all URLs to scrape")
    parser.add_argument("--limit", type=int, help="Limit number of properties")
    parser.add_argument("--suburb", type=str, help="Filter by suburb")
    parser.add_argument("--delay", type=float, default=3.0, help="Delay between requests (seconds)")
    parser.add_argument("--url-for", type=str, help="Generate URL for specific address")
    parser.add_argument("--headed", action="store_true", help="Show browser window (not headless)")
    parser.add_argument("--stats", action="store_true", help="Show estimate coverage statistics")

    args = parser.parse_args()

    if args.stats:
        stats = get_estimate_stats()
        print(f"\n{'='*60}")
        print(f"Domain Estimator - Coverage Statistics")
        print(f"{'='*60}")
        print(f"Total for sale:           {stats['total_for_sale']}")
        print(f"Already estimated:        {stats['with_estimates']} ({stats['with_estimates']*100//max(stats['total_for_sale'],1)}%)")
        print(f"Without estimates:        {stats['without_estimates']}")
        print(f"New today (no estimate):  {stats['new_today_without_estimates']}")
        print(f"{'='*60}\n")

    elif args.batch:
        batch_scrape(limit=args.limit, suburb=args.suburb, delay=args.delay, headless=not args.headed, mode=args.mode)

    elif args.url_for:
        suburb = "CASTLE HILL" if "CASTLE" in args.url_for.upper() else "BAULKHAM HILLS"
        url = address_to_domain_url(args.url_for, suburb)
        print(f"URL: {url}")

    elif args.list_urls:
        urls = generate_url_list(limit=args.limit, suburb=args.suburb)
        print(f"Found {len(urls)} properties:\n")
        for item in urls:
            print(f"  {item['address']}, {item['suburb']}")
            print(f"    -> {item['domain_url']}\n")

    else:
        stats = get_estimate_stats()
        print(f"\n{'='*60}")
        print(f"Domain Estimator Helper")
        print(f"{'='*60}")
        print(f"For-sale properties:     {stats['total_for_sale']}")
        print(f"Already estimated:       {stats['with_estimates']}")
        print(f"Need estimates:          {stats['without_estimates']}")
        print(f"New today (no estimate): {stats['new_today_without_estimates']}")
        print(f"{'='*60}")
        print("\nUsage:")
        print("  --batch                  Batch scrape properties")
        print("  --mode MODE              Estimation mode:")
        print("                             'new-only' (default) - only unestimated properties")
        print("                             'today-new' - only today's new listings")
        print("                             'all' - re-estimate all for-sale")
        print("  --stats                  Show estimate coverage statistics")
        print("  --list-urls              Show Domain URLs")
        print("  --limit N                Limit to N properties")
        print("  --suburb NAME            Filter by suburb")
        print("  --delay SECS             Delay between requests (default: 3)")
        print("  --headed                 Show browser window (default: headless)")
        print("\nExamples:")
        print("  python domain_estimator_helper.py --batch                # Estimate new properties only")
        print("  python domain_estimator_helper.py --batch --mode all     # Re-estimate all")
        print("  python domain_estimator_helper.py --batch --mode today-new  # Today's new listings only")
        print("  python domain_estimator_helper.py --stats                # Show coverage stats")
