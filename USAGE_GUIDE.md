# Baulkham Hills & Castle Hill Property Tracker

Complete guide to the property tracking and ML valuation system.

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [Installation](#installation)
3. [Web Scraper](#web-scraper)
4. [Excelsior Catchment Feature](#excelsior-catchment-feature)
5. [ML Valuation System](#ml-valuation-system)
6. [API Server](#api-server)
7. [Database Reference](#database-reference)
8. [Common Workflows](#common-workflows)
9. [Domain Estimator (Browser Automation)](#domain-estimator-browser-automation)

---

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt
crawl4ai-setup

# 2. Run scraper to collect data
python baulkandcastle_scraper.py

# 3. Train the ML model
python ml/train_model.py

# 4. Estimate all for-sale properties
python ml/estimate_for_sale.py

# 5. Predict a specific property value
python ml/predict_property_value.py 600 4 --bathrooms 2 --suburb "CASTLE HILL" --property_type house
```

---

## Installation

### Prerequisites
- Python 3.10+
- pip

### Install Dependencies

```bash
# Install all dependencies
pip install -r requirements.txt

# Setup browser for web scraping
crawl4ai-setup
```

### Dependencies Breakdown

| Package | Purpose |
|---------|---------|
| crawl4ai | Browser automation for scraping |
| beautifulsoup4 | HTML parsing |
| pandas | Data processing |
| numpy | Numerical operations |
| scikit-learn | ML utilities |
| xgboost | ML model |
| joblib | Model persistence |
| flask | API server (optional) |
| flask-cors | API CORS support (optional) |

---

## Web Scraper

Scrapes Domain.com.au for property listings in Baulkham Hills (2153) and Castle Hill (2154).

### Commands

#### Full Scrape (All Pages)
```bash
python baulkandcastle_scraper.py
```
- Scrapes ALL for-sale listings
- Scrapes up to 30 pages of sold listings (configurable)
- Generates HTML reports
- Updates daily statistics

#### Daily Quick Scan (Page 1 Only)
```bash
python baulkandcastle_scraper.py --daily
```
- Fast scan - only page 1 of sale and sold
- Good for daily monitoring
- Still generates all reports

#### Custom Sold Pages
```bash
python baulkandcastle_scraper.py --sold-pages 50
```
- Scrape more historical sold data
- Default is 30 pages

#### Reports Only (No Scraping)
```bash
python baulkandcastle_scraper.py --reports-only
```
- Regenerate HTML reports from existing database
- No web scraping performed
- Useful after database changes

#### Update Catchment Flags Only
```bash
python baulkandcastle_scraper.py --update-catchment
```
- Scrapes Excelsior Public School catchment area
- Updates `in_excelsior_catchment` flag on matching properties
- Regenerates reports with catchment data
- No property scraping performed

### Generated Reports

| File | Description |
|------|-------------|
| `baulkandcastle_summary.html` | Dashboard with stats, daily changes, market summary |
| `baulkandcastle_sale_matches.html` | All current for-sale listings |
| `baulkandcastle_sold_matches.html` | Historical sold listings |

### What Gets Scraped

For each property:
- Address, suburb
- Price (display and numeric value)
- Bedrooms, bathrooms, car spaces
- Land size
- Property type (house, unit, townhouse, etc.)
- Price per m²
- Agent name
- Sold date (for sold properties)
- URL

---

## Excelsior Catchment Feature

Properties within Excelsior Public School catchment zone are automatically identified and flagged.

### Overview

The catchment feature scrapes Domain's school catchment page to get a list of property IDs within the Excelsior Public School catchment area, then marks matching properties in your database.

### How It Works

1. **Scrape Catchment Page** - Fetches all property IDs from Domain's catchment listing
2. **Match Properties** - Compares against your existing property database
3. **Set Flag** - Sets `in_excelsior_catchment = 1` for matching properties
4. **Update Reports** - Regenerates HTML reports with catchment column

### Commands

```bash
# Full scrape (includes catchment update automatically)
python baulkandcastle_scraper.py

# Update catchment flags only (no property scraping)
python baulkandcastle_scraper.py --update-catchment
```

### Report Features

#### For-Sale & Sold Reports
- **Excelsior Column** - Shows checkmark (✓) for catchment properties
- **Filter Toggle** - "Show only Excelsior catchment" checkbox
- **Property Count** - Shows "Showing X of Y properties" when filtered

#### Summary Dashboard
- **Stat Card** - Green "Excelsior Catchment" card showing:
  - Total properties in catchment
  - Breakdown: "X for sale | Y sold"

### Database

The catchment flag is stored in the `properties` table:

| Column | Type | Description |
|--------|------|-------------|
| in_excelsior_catchment | INTEGER | 1 = in catchment, 0 = not in catchment |

### SQL Queries

```sql
-- Properties in Excelsior catchment
SELECT address, suburb FROM properties WHERE in_excelsior_catchment = 1;

-- For-sale properties in catchment
SELECT p.address, h.price_display, h.beds, h.baths
FROM properties p
JOIN listing_history h ON p.property_id = h.property_id
WHERE p.in_excelsior_catchment = 1
AND h.status = 'sale'
AND h.date = (SELECT MAX(date) FROM listing_history WHERE property_id = h.property_id);

-- Count by catchment status
SELECT
    CASE WHEN in_excelsior_catchment = 1 THEN 'In Catchment' ELSE 'Not in Catchment' END as status,
    COUNT(*) as count
FROM properties
GROUP BY in_excelsior_catchment;
```

### Catchment URL

The feature scrapes from Domain's school catchment page:
```
https://www.domain.com.au/school-catchment/excelsior-public-school-nsw-2154-637
```

---

## ML Valuation System

XGBoost-based property valuation with 17 engineered features.

### Step 1: Train the Model

```bash
python ml/train_model.py
```

**Options:**
```bash
# Use a different database
python ml/train_model.py --db path/to/database.db

# Adjust test split
python ml/train_model.py --test-size 0.3
```

**Output:**
- Model saved to: `ml/models/property_valuation_model.pkl`
- Metadata saved to: `ml/models/training_metadata.json`

**Model Performance Targets:**
- R² Score: >= 0.70 (good), >= 0.50 (acceptable)
- MAPE: <= 15% (good), <= 20% (acceptable)

### Step 2: Predict Individual Properties

```bash
python ml/predict_property_value.py [land_size] <beds> [options]
```

**Land Size Handling by Property Type:**

| Property Type | Land Size | Behavior |
|---------------|-----------|----------|
| **House** | Required | Uses provided value; defaults to 450m² if not given |
| **Townhouse** | Recommended | Uses provided value; defaults to 200m² if not given |
| **Unit/Apartment** | Not needed | Ignored (strata title - land size N/A) |

**Examples:**

```bash
# House with known land size (recommended)
python ml/predict_property_value.py 600 4 --bathrooms 2 --suburb "CASTLE HILL" --property_type house

# House without land size (uses default 450m²)
python ml/predict_property_value.py 4 --bathrooms 2 --suburb "CASTLE HILL" --property_type house

# Unit - no land size needed
python ml/predict_property_value.py 2 --bathrooms 1 --suburb "BAULKHAM HILLS" --property_type unit

# Townhouse with land size
python ml/predict_property_value.py 250 3 --bathrooms 2 --suburb "CASTLE HILL" --property_type townhouse

# Townhouse without land size (uses default 200m²)
python ml/predict_property_value.py 3 --bathrooms 2 --property_type townhouse

# JSON output (for scripts/API)
python ml/predict_property_value.py 600 4 --output json

# Using JSON input
python ml/predict_property_value.py --json '{"beds": 4, "bathrooms": 2, "property_type": "house"}'
```

**Options:**
| Option | Default | Description |
|--------|---------|-------------|
| `--land_size` | varies | Land size in m² (optional for units) |
| `--beds` | - | Number of bedrooms |
| `--bathrooms` | 2 | Number of bathrooms |
| `--car_spaces` | 1 | Number of car spaces |
| `--suburb` | CASTLE HILL | CASTLE HILL or BAULKHAM HILLS |
| `--property_type` | house | house, unit, townhouse, apartment, villa, duplex, terrace |
| `--output` | text | text or json |

### Step 3: Estimate All For-Sale Properties

```bash
python ml/estimate_for_sale.py
```

**What it does:**
1. Loads all current for-sale properties from database
2. Archives any existing estimates to history table
3. Runs ML predictions on each property
4. Stores new estimates with timestamp
5. Shows comparison with asking price (where available)

**Options:**
```bash
# Quiet mode (no per-property output)
python ml/estimate_for_sale.py --quiet

# Use different database
python ml/estimate_for_sale.py --db path/to/database.db
```

**Output shows:**
- Address
- Asking price (if known)
- Estimated price
- Difference percentage (+/- from asking)

### Model Features (18 total)

| Feature | Description |
|---------|-------------|
| `land_size_numeric` | Land size in m² (0 for units) |
| `beds` | Number of bedrooms |
| `baths` | Number of bathrooms |
| `cars` | Number of car spaces |
| `bedroom_to_land_ratio` | Beds / land size (0 for units) |
| `bathroom_to_bedroom_ratio` | Baths / beds |
| `suburb_castle_hill` | 1 if Castle Hill, 0 if Baulkham Hills |
| `property_type_house` | 1 if house |
| `property_type_unit` | 1 if unit/apartment |
| `property_type_townhouse` | 1 if townhouse |
| `is_house_large_land` | 1 if house with real land data >500m² |
| `has_real_land_size` | 1 if land size from scraped data, 0 if imputed/N/A |
| `is_spring` | 1 if sale in Sep/Oct/Nov |
| `is_summer` | 1 if sale in Dec/Jan/Feb |
| `is_autumn` | 1 if sale in Mar/Apr/May |
| `is_winter` | 1 if sale in Jun/Jul/Aug |
| `years_since_sale` | Years from sale date to now |
| `rolling_avg_price_per_m2` | 6-month rolling avg $/m² for suburb |

---

## API Server

REST API for property valuations (optional).

### Start Server

```bash
python api_server.py
```

**Options:**
```bash
# Custom host/port
python api_server.py --host 0.0.0.0 --port 8080

# Debug mode
python api_server.py --debug
```

### API Endpoints

#### Health Check
```bash
GET /api/health
```

#### Model Info
```bash
GET /api/model-info
```
Returns model metrics, feature importance, training date.

#### Single Prediction
```bash
POST /api/predict
Content-Type: application/json

{
    "land_size": 600,
    "beds": 4,
    "bathrooms": 2,
    "car_spaces": 2,
    "suburb": "CASTLE HILL",
    "property_type": "house"
}
```

**Response:**
```json
{
    "status": "success",
    "prediction": {
        "predicted_price": 2156000,
        "price_range_low": 1858000,
        "price_range_high": 2454000,
        "confidence_level": "Based on MAPE: 13.8%",
        "input_features": {...}
    }
}
```

#### Batch Prediction
```bash
POST /api/predict/batch
Content-Type: application/json

{
    "properties": [
        {"land_size": 600, "beds": 4, "bathrooms": 2},
        {"land_size": 80, "beds": 2, "bathrooms": 1, "property_type": "unit"}
    ]
}
```

### Example API Calls (curl)

```bash
# Health check
curl http://localhost:5000/api/health

# Single prediction
curl -X POST http://localhost:5000/api/predict \
  -H "Content-Type: application/json" \
  -d '{"land_size": 600, "beds": 4, "bathrooms": 2, "suburb": "CASTLE HILL"}'

# Batch prediction
curl -X POST http://localhost:5000/api/predict/batch \
  -H "Content-Type: application/json" \
  -d '{"properties": [{"land_size": 600, "beds": 4}, {"land_size": 200, "beds": 3}]}'
```

---

## Database Reference

SQLite database: `baulkandcastle_properties.db`

### Tables

#### properties
Core property records (static info).

| Column | Type | Description |
|--------|------|-------------|
| property_id | TEXT | Primary key (Domain ID) |
| address | TEXT | Full address |
| suburb | TEXT | BAULKHAM HILLS or CASTLE HILL |
| first_seen | TEXT | Date first scraped |
| url | TEXT | Domain.com.au URL |
| in_excelsior_catchment | INTEGER | 1 if in Excelsior catchment, 0 otherwise |

#### listing_history
Property snapshots over time.

| Column | Type | Description |
|--------|------|-------------|
| property_id | TEXT | Foreign key |
| date | TEXT | Snapshot date |
| status | TEXT | 'sale' or 'sold' |
| price_display | TEXT | Display price (e.g., "$1,500,000") |
| price_value | INTEGER | Numeric price |
| beds | INTEGER | Bedrooms |
| baths | INTEGER | Bathrooms |
| cars | INTEGER | Car spaces |
| land_size | TEXT | Land size string (e.g., "600m²") |
| property_type | TEXT | house, unit, townhouse, etc. |
| agent | TEXT | Listing agent |
| scraped_at | TEXT | Scrape timestamp |
| sold_date | TEXT | Sold date (DD MMM YYYY format) |
| sold_date_iso | TEXT | Sold date (YYYY-MM-DD format) |
| price_per_m2 | REAL | Price per square meter |

#### daily_summary
Daily scraping statistics.

| Column | Type | Description |
|--------|------|-------------|
| date | TEXT | Primary key |
| new_count | INTEGER | New listings |
| sold_count | INTEGER | Sold/removed listings |
| adj_count | INTEGER | Price adjustments |

#### property_estimates
Current ML estimates for for-sale properties.

| Column | Type | Description |
|--------|------|-------------|
| property_id | TEXT | Primary key |
| estimated_price | INTEGER | ML predicted price |
| price_range_low | INTEGER | Low estimate |
| price_range_high | INTEGER | High estimate |
| estimate_date | TEXT | When estimate was made |
| model_mape | REAL | Model error rate used |
| input_* | various | Input features used |

#### property_estimates_history
Archived previous estimates.

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key |
| property_id | TEXT | Property reference |
| estimated_price | INTEGER | Historical estimate |
| estimate_date | TEXT | Original estimate date |
| archived_at | TEXT | When moved to history |
| ... | ... | Same fields as property_estimates |

#### property_valuations
External valuations (PropertyValue.com.au).

| Column | Type | Description |
|--------|------|-------------|
| property_id | TEXT | Primary key |
| latest_low | INTEGER | Low valuation |
| latest_high | INTEGER | High valuation |
| propertyvalue_url | TEXT | Source URL |
| last_updated | TEXT | Last update date |

### Useful SQL Queries

```sql
-- Count properties by suburb
SELECT suburb, COUNT(*) FROM properties GROUP BY suburb;

-- Current for-sale listings
SELECT p.address, h.price_display, h.beds, h.baths
FROM listing_history h
JOIN properties p ON h.property_id = p.property_id
WHERE h.status = 'sale'
AND h.date = (SELECT MAX(date) FROM listing_history WHERE property_id = h.property_id);

-- Recent sold properties
SELECT p.address, h.price_value, h.sold_date
FROM listing_history h
JOIN properties p ON h.property_id = p.property_id
WHERE h.status = 'sold'
ORDER BY h.sold_date_iso DESC
LIMIT 20;

-- Price changes for a property
SELECT date, price_display
FROM listing_history
WHERE property_id = '2019392466'
ORDER BY date;

-- Compare asking vs estimated price
SELECT
    p.address,
    h.price_value as asking,
    e.estimated_price as estimate,
    e.estimated_price - h.price_value as difference,
    ROUND((e.estimated_price - h.price_value) * 100.0 / h.price_value, 1) as diff_pct
FROM property_estimates e
JOIN properties p ON e.property_id = p.property_id
JOIN listing_history h ON e.property_id = h.property_id
WHERE h.status = 'sale' AND h.price_value > 0
ORDER BY diff_pct DESC;

-- Estimate history for a property
SELECT estimated_price, estimate_date, archived_at
FROM property_estimates_history
WHERE property_id = '2019392466'
ORDER BY estimate_date;

-- Average prices by property type
SELECT property_type,
       COUNT(*) as count,
       ROUND(AVG(price_value)) as avg_price
FROM listing_history
WHERE status = 'sold' AND price_value > 0
GROUP BY property_type;
```

---

## Common Workflows

### Daily Monitoring
```bash
# Quick daily scan
python baulkandcastle_scraper.py --daily

# Update estimates
python ml/estimate_for_sale.py --quiet
```

### Weekly Full Update
```bash
# Full scrape
python baulkandcastle_scraper.py

# Retrain model with new sold data
python ml/train_model.py

# Update all estimates
python ml/estimate_for_sale.py
```

### Research a Specific Property
```bash
# Predict value for a property you're interested in
python ml/predict_property_value.py 550 4 --bathrooms 2 --car_spaces 2 --suburb "CASTLE HILL" --property_type house
```

### Database Migration (First Time)
```bash
# Add sold_date_iso column for ML model
sqlite3 baulkandcastle_properties.db < migrations/add_sold_date_iso.sql
```

### Check Model Performance
```bash
# Retrain and see metrics
python ml/train_model.py

# Or check saved metadata
type ml\models\training_metadata.json
```

---

## File Structure

```
baulkandcastle/
├── baulkandcastle_scraper.py      # Main scraper
├── baulkandcastle_properties.db   # SQLite database
├── api_server.py                  # Flask API server
├── domain_estimator_helper.py     # Domain Estimator URL generator
├── requirements.txt               # Python dependencies
├── USAGE_GUIDE.md                 # This file
├── .mcp.json                      # MCP server configuration
│
├── .claude/                       # Claude Code configuration
│   ├── settings.json              # Permissions
│   └── commands/
│       └── domain-estimator.md    # Domain Estimator skill
│
├── ml/                            # ML Pipeline
│   ├── __init__.py
│   ├── valuation_predictor.py     # Core ML class
│   ├── train_model.py             # Training script
│   ├── predict_property_value.py  # CLI prediction
│   ├── estimate_for_sale.py       # Batch estimator
│   ├── requirements.txt           # ML-specific deps
│   └── models/
│       ├── property_valuation_model.pkl   # Trained model
│       └── training_metadata.json         # Model metrics
│
├── migrations/
│   └── add_sold_date_iso.sql      # Database migration
│
└── Generated Reports/
    ├── baulkandcastle_summary.html
    ├── baulkandcastle_sale_matches.html
    └── baulkandcastle_sold_matches.html
```

---

## Domain Estimator (Browser Automation)

Fetch property value estimates from Domain.com.au's Property Profile pages using browser automation.

### Overview

Domain.com.au provides automated property value estimates on their Property Profile pages. The Domain Estimator scrapes these estimates and stores them in your database.

### Two Ways to Use

| Method | Requires Claude? | Best For |
|--------|------------------|----------|
| **Standalone Script** (`--batch`) | No | Automated batch scraping, scheduled tasks, cron jobs |
| **Claude Code Skill** (`/domain-estimator`) | Yes | Interactive single-property lookups, ad-hoc queries |

### Installation

```bash
# Install globally via npm
npm install -g agent-browser
```

### Method 1: Standalone Batch Scraping (No Claude Required)

The standalone script uses `agent-browser` CLI to scrape all for-sale properties automatically.

#### Basic Usage

```bash
# Scrape ALL for-sale properties
python domain_estimator_helper.py --batch

# Limit to first 10 properties
python domain_estimator_helper.py --batch --limit 10

# Filter by suburb only
python domain_estimator_helper.py --batch --suburb "Castle Hill"

# Custom delay between requests (default: 3 seconds)
python domain_estimator_helper.py --batch --delay 5
```

#### Scheduling (Automated Daily/Weekly)

**Windows Task Scheduler:**
```
Program: C:\Tools PHPC\baulkandcastle\.venv\Scripts\python.exe
Arguments: domain_estimator_helper.py --batch --delay 5
Start in: C:\Tools PHPC\baulkandcastle
```

**Linux/Mac Cron:**
```bash
# Run weekly on Sunday at 2am
0 2 * * 0 cd /path/to/baulkandcastle && .venv/bin/python domain_estimator_helper.py --batch
```

#### Output Example

```
============================================================
Domain Estimator Batch Scrape
============================================================
Properties to scrape: 274
Delay between requests: 3s
============================================================

[1/274] 15 Smith Street, Castle Hill
  Scraping: 15 Smith Street
  URL: https://www.domain.com.au/property-profile/15-smith-street-castle-hill-nsw-2154
  Estimate: $1,330,000 - $1,540,000 - $1,750,000
  ✓ Saved to database

[2/274] 22 Jones Road, Baulkham Hills
  ...

============================================================
Batch Scrape Complete
============================================================
Success: 268
Errors:  6
============================================================
```

### Method 2: Claude Code Skill (Requires Claude)

For interactive, single-property lookups within Claude Code.

```bash
# In Claude Code terminal
/domain-estimator 15 Smith Street Castle Hill

# Or without address to query database
/domain-estimator
```

The skill uses the same `agent-browser` CLI under the hood but is guided by Claude to:
1. Parse the address
2. Navigate to Domain's property profile
3. Extract and format the estimate data
4. Save to database
5. Present results in a formatted table

### Helper Script Commands

```bash
# List all property URLs to scrape (no scraping)
python domain_estimator_helper.py --list-urls

# Limit listing
python domain_estimator_helper.py --list-urls --limit 10

# Filter by suburb
python domain_estimator_helper.py --list-urls --suburb "Castle Hill"

# Generate URL for a specific address
python domain_estimator_helper.py --url-for "15 Smith Street Castle Hill"

# Show help
python domain_estimator_helper.py --help
```

### Direct Agent Browser Commands

```bash
# Open a property profile page
agent-browser open https://www.domain.com.au/property-profile/15-smith-street-castle-hill-nsw-2154

# Get page snapshot (accessibility tree)
agent-browser snapshot

# Take screenshot
agent-browser screenshot property.png

# Close browser
agent-browser close
```

### URL Format

Domain Property Profile URLs follow this pattern:
```
https://www.domain.com.au/property-profile/{address-slug}-{suburb-slug}-nsw-{postcode}
```

Examples:
- `https://www.domain.com.au/property-profile/15-smith-street-castle-hill-nsw-2154`
- `https://www.domain.com.au/property-profile/4-52-54-kerrs-road-castle-hill-nsw-2154`

### Database Schema

The Domain Estimator uses dedicated tables (separate from ML estimates):

#### domain_estimates
Current Domain.com.au estimates for properties.

| Column | Type | Description |
|--------|------|-------------|
| property_id | TEXT | Primary key (Domain ID) |
| address | TEXT | Full formatted address |
| suburb | TEXT | Castle Hill or Baulkham Hills |
| property_type | TEXT | Townhouse, House, Unit, etc. |
| beds | INTEGER | Number of bedrooms |
| baths | INTEGER | Number of bathrooms |
| parking | INTEGER | Car spaces |
| land_size | TEXT | Land size in m² |
| **estimate_low** | INTEGER | Low value estimate |
| **estimate_mid** | INTEGER | Mid/median estimate |
| **estimate_high** | INTEGER | High value estimate |
| estimate_accuracy | TEXT | High, Medium, or Low |
| estimate_date | TEXT | Date shown on Domain |
| rental_weekly | INTEGER | Weekly rental estimate |
| rental_yield | REAL | Rental yield percentage |
| rental_accuracy | TEXT | Rental estimate accuracy |
| rental_estimate_date | TEXT | Rental estimate date |
| last_sold_date | TEXT | Previous sale date |
| last_sold_price | INTEGER | Previous sale price |
| last_sold_agent | TEXT | Previous sale agent |
| last_sold_days_listed | INTEGER | Days on market |
| listing_status | TEXT | For Sale, Just Listed, etc. |
| listing_agent | TEXT | Current agent name |
| listing_agency | TEXT | Current agency name |
| features | TEXT | Comma-separated features |
| domain_url | TEXT | Full Domain profile URL |
| **scraped_at** | TEXT | Timestamp of scrape |

#### domain_estimates_history
Historical Domain estimates over time (for tracking changes).

Same columns as `domain_estimates` plus auto-increment `id`.

### HTML Reports Integration

The `baulkandcastle_sale_matches.html` report automatically displays the **Domain Estimate** column showing:
- Mid estimate value (e.g., `$1,540,000`)
- Scrape date in smaller text below

To regenerate reports after scraping:
```bash
python baulkandcastle_scraper.py --reports-only
```

### Useful SQL Queries

```sql
-- Properties with Domain estimates
SELECT p.address, p.suburb,
       de.estimate_low, de.estimate_mid, de.estimate_high,
       de.scraped_at
FROM domain_estimates de
JOIN properties p ON de.property_id = p.property_id
ORDER BY de.scraped_at DESC;

-- Compare asking price vs Domain estimate
SELECT
    p.address,
    h.price_value as asking_price,
    de.estimate_mid as domain_estimate,
    de.estimate_mid - h.price_value as difference,
    ROUND((de.estimate_mid - h.price_value) * 100.0 / h.price_value, 1) as diff_pct
FROM domain_estimates de
JOIN properties p ON de.property_id = p.property_id
JOIN listing_history h ON de.property_id = h.property_id
WHERE h.status = 'sale' AND h.price_value > 0
ORDER BY diff_pct DESC;

-- Compare ML estimate vs Domain estimate
SELECT p.address,
       pe.estimated_price as ml_estimate,
       de.estimate_mid as domain_estimate,
       de.estimate_mid - pe.estimated_price as difference
FROM property_estimates pe
JOIN domain_estimates de ON pe.property_id = de.property_id
JOIN properties p ON pe.property_id = p.property_id
ORDER BY ABS(difference) DESC;

-- Domain estimate history for a property
SELECT estimate_low, estimate_mid, estimate_high, scraped_at
FROM domain_estimates_history
WHERE property_id = '2020510444'
ORDER BY scraped_at;

-- Properties with high rental yield
SELECT address, estimate_mid, rental_weekly, rental_yield
FROM domain_estimates
WHERE rental_yield > 3.0
ORDER BY rental_yield DESC;
```

### Rate Limiting

Domain.com.au may rate-limit requests. Recommendations:
- Default delay is 3 seconds between requests
- Use `--delay 5` for safer scraping
- Run during off-peak hours (late night/early morning)
- For large batches, use `--limit` to scrape in chunks

### Testing the Parser

The parser is tested against a reference property (4/52-54 Kerrs Road, Castle Hill) to ensure batch scraping produces consistent results.

#### Quick Validation
```bash
python test_domain_estimator.py --quick
```

Output:
```
============================================================
Domain Estimator Parser Validation
============================================================

Test case: 4/52-54 Kerrs Road, Castle Hill
------------------------------------------------------------
  [PASS] beds: 3 (expected: 3)
  [PASS] baths: 2 (expected: 2)
  [PASS] estimate_low: 1330000 (expected: 1330000)
  [PASS] estimate_mid: 1540000 (expected: 1540000)
  [PASS] estimate_high: 1750000 (expected: 1750000)
  ... (14 fields total)
------------------------------------------------------------
All checks PASSED
============================================================
```

#### Full Test Suite
```bash
python -m pytest test_domain_estimator.py -v
```

**Test Coverage (22 tests):**

| Test Class | Tests | Description |
|------------|-------|-------------|
| `TestPriceStringParsing` | 4 | Price parsing ($1.33m, $1,278,800, $860k) |
| `TestAddressToUrl` | 4 | URL generation for different address formats |
| `TestSnapshotParsing` | 12 | All fields extracted from browser snapshot |
| `TestDatabaseIntegration` | 2 | Parsed data matches saved database record |

#### When to Run Tests

- After modifying `parse_snapshot_text()` in `domain_estimator_helper.py`
- If Domain.com.au changes their page structure
- Before running large batch scrapes

### File Structure

```
baulkandcastle/
├── domain_estimator_helper.py         # Standalone batch scraper & helpers
├── test_domain_estimator.py           # Unit tests (22 tests)
│
├── .claude/
│   └── commands/
│       └── domain-estimator.md        # Claude Code skill definition
```

---

## Troubleshooting

### "Model not found"
```bash
python ml/train_model.py
```

### "crawl4ai not installed"
```bash
pip install crawl4ai
crawl4ai-setup
```

### Scraper returns no data
- Domain.com.au may have changed their HTML structure
- Check your internet connection
- Try running with fewer pages first

### Low model accuracy
- Need more sold data (run full scrape with `--sold-pages 50`)
- Check data quality in database
- Consider retraining after more sales

### Agent Browser issues
```bash
# Reinstall agent-browser
npm install -g agent-browser
agent-browser install

# Check version
agent-browser --version
```

### MCP server not loading
- Restart Claude Code after adding `.mcp.json`
- Check that npm/npx is in your PATH
- Verify `.mcp.json` syntax is valid JSON

### Domain rate limiting
- Add delays between requests (2-5 seconds)
- Reduce batch size to 10-20 properties
- Try again later if blocked

---

## Command Summary

| Command | Description |
|---------|-------------|
| `python baulkandcastle_scraper.py` | Full scrape (sale + sold + catchment) |
| `python baulkandcastle_scraper.py --daily` | Quick daily scan (page 1 only) |
| `python baulkandcastle_scraper.py --sold-pages 50` | Full scrape with more sold pages |
| `python baulkandcastle_scraper.py --reports-only` | Regenerate reports only |
| `python baulkandcastle_scraper.py --update-catchment` | Update Excelsior catchment flags only |
| `python ml/train_model.py` | Train/retrain ML model |
| `python ml/predict_property_value.py 600 4` | Predict single property |
| `python ml/estimate_for_sale.py` | Estimate all for-sale |
| `python api_server.py` | Start REST API |
| **Domain Estimator (Standalone - No Claude)** | |
| `python domain_estimator_helper.py --batch` | Batch scrape all for-sale properties |
| `python domain_estimator_helper.py --batch --limit 10` | Scrape first 10 properties |
| `python domain_estimator_helper.py --batch --suburb "Castle Hill"` | Scrape Castle Hill only |
| `python domain_estimator_helper.py --list-urls` | List Domain profile URLs |
| `agent-browser open <url>` | Open URL in automated browser |
| `agent-browser snapshot` | Get page accessibility tree |
| **Domain Estimator (Claude Code)** | |
| `/domain-estimator` | Interactive estimate lookup (requires Claude) |
| `/domain-estimator 15 Smith St Castle Hill` | Lookup specific address (requires Claude) |
| **Testing** | |
| `python test_domain_estimator.py --quick` | Quick parser validation |
| `python -m pytest test_domain_estimator.py -v` | Full test suite (22 tests) |
