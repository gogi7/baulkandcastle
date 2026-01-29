# Domain Estimator Property Valuation Skill

Fetch property valuations from Domain.com.au using the agent-browser CLI.

## Overview

Domain.com.au provides property value estimates at URLs like:
`https://www.domain.com.au/property-profile/{address-slug}-{suburb}-nsw-{postcode}`

## Instructions

### Step 1: Start the daemon (if not running)

```bash
cd "$APPDATA/npm/node_modules/agent-browser" && node dist/daemon.js &
```

Or run in background and continue.

### Step 2: Get properties to scrape

Query the database for for-sale properties:

```bash
sqlite3 "C:/Tools PHPC/baulkandcastle/baulkandcastle_properties.db" "
SELECT p.property_id, p.address, p.suburb
FROM properties p
JOIN listing_history h ON p.property_id = h.property_id
WHERE h.status = 'sale'
AND h.date = (SELECT MAX(date) FROM listing_history WHERE property_id = p.property_id)
ORDER BY p.suburb, p.address
LIMIT 10;
"
```

### Step 3: For each property, use agent-browser CLI

```bash
# Generate URL (use domain_estimator_helper.py)
python domain_estimator_helper.py --url-for "ADDRESS HERE"

# Open the page
agent-browser open "https://www.domain.com.au/property-profile/ADDRESS-SLUG"

# Wait for load, then get snapshot
agent-browser snapshot

# Parse the snapshot for estimate values:
# - Look for "estimated to be worth around $X.XXm, with a range from $X.XXm to $X.XXm"
# - Extract beds, baths, parking, land size
# - Extract rental estimate if available
```

### Step 4: Save results to database

Use the helper to save:
```python
from domain_estimator_helper import DomainEstimate, save_estimate

estimate = DomainEstimate(
    property_id="...",
    address="...",
    suburb="...",
    estimate_low=1500000,
    estimate_mid=1740000,
    estimate_high=1980000,
    # ... other fields
)
save_estimate(estimate)
```

### Step 5: Close browser when done

```bash
agent-browser close
```

## Batch Mode (Alternative)

The helper script also supports Playwright-based batch scraping if agent-browser daemon isn't available:

```bash
python domain_estimator_helper.py --batch --limit 10
```

## URL Construction

Postcodes:
- BAULKHAM HILLS: 2153
- CASTLE HILL: 2154

Format: lowercase, spaces to hyphens, remove apostrophes/commas

Example: "12 Smith Street" in Castle Hill → `12-smith-street-castle-hill-nsw-2154`

## Usage Examples

1. `/domain-estimator` - Scrape all for-sale properties
2. `/domain-estimator --limit 5` - Scrape first 5 properties
3. `/domain-estimator 15 Jenner Street Castle Hill` - Single property

## Database Tables

Results saved to:
- `domain_estimates` - Current estimates (upsert)
- `domain_estimates_history` - Historical tracking
