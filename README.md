# Baulkham Hills & Castle Hill Property Tracker

A comprehensive property tracking and valuation system for Domain.com.au listings in Baulkham Hills (2153) and Castle Hill (2154).

## Features

### Core Scraping
- **For Sale Listings** - Scrapes all current listings with prices, specs, and agent info
- **Sold Listings** - Historical sold data (up to 1 year) with sale prices and dates
- **Daily Change Detection** - Tracks new listings, price adjustments, and removed/sold properties
- **Excelsior Catchment** - Flags properties within Excelsior Public School catchment zone

### Valuation & Estimation
- **ML Valuation Model** - XGBoost-based property value predictions trained on sold data
- **Domain Estimator** - Browser automation to fetch Domain's official property estimates
- **REST API** - Flask server for programmatic access to valuations

### Reports & Analytics
- **For-Sale Report** - Interactive HTML table with filtering and sorting
- **Sold Report** - Historical sales with date-sorted entries
- **Summary Dashboard** - Market analytics, ML predictions, daily changes

## Coverage

| Suburb | Postcode |
|--------|----------|
| Baulkham Hills | 2153 |
| Castle Hill | 2154 |

**Property Types:** Apartments, townhouses, villas, houses, duplexes, terraces, vacant land, development sites, and more.

---

## Quick Start

### 1. Installation

```bash
# Clone or download the repository
cd baulkandcastle

# Create and activate virtual environment
python -m venv .venv

# Windows
.venv\Scripts\activate

# Linux/Mac
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# First-time crawl4ai setup (downloads browser)
crawl4ai-setup
```

### 2. Run Full Scrape

```bash
python baulkandcastle_scraper.py
```

This will:
1. Scrape all for-sale listings
2. Scrape recent sold listings (30 pages)
3. Update Excelsior catchment flags
4. Generate HTML reports

### 3. View Reports

Open in browser:
- `baulkandcastle_summary.html` - Dashboard
- `baulkandcastle_sale_matches.html` - For-sale listings
- `baulkandcastle_sold_matches.html` - Sold listings

---

## Command Reference

### Main Scraper

```bash
# Full scrape (sale + sold + catchment)
python baulkandcastle_scraper.py

# Custom sold pages (default: 30)
python baulkandcastle_scraper.py --sold-pages 50

# Quick daily scan (page 1 only)
python baulkandcastle_scraper.py --daily

# Reports only (no scraping)
python baulkandcastle_scraper.py --reports-only

# Update catchment flags only
python baulkandcastle_scraper.py --update-catchment
```

### ML Model

```bash
# Train model on sold data
python ml/train_model.py

# Predict single property value
python ml/predict_property_value.py 600 4 --property_type house
python ml/predict_property_value.py 2 --property_type unit

# Run estimates on all for-sale properties
python ml/estimate_for_sale.py
```

### Domain Estimator (Browser Automation)

```bash
# Install browser automation (one-time)
pip install playwright && playwright install chromium

# Batch scrape all for-sale properties
python domain_estimator_helper.py --batch

# Limit to first N properties
python domain_estimator_helper.py --batch --limit 10

# Filter by suburb
python domain_estimator_helper.py --batch --suburb "Castle Hill"

# List URLs without scraping
python domain_estimator_helper.py --list-urls
```

### API Server

```bash
# Start Flask API server
python api_server.py
python api_server.py --port 8080 --host 0.0.0.0

# Example API call
curl -X POST http://localhost:5000/api/predict \
  -H "Content-Type: application/json" \
  -d '{"land_size": 600, "beds": 4, "bathrooms": 2, "property_type": "house"}'
```

### Testing

```bash
# Quick domain estimator validation
python test_domain_estimator.py --quick

# Full test suite
python -m pytest test_domain_estimator.py -v
```

---

## Workflow Examples

### Daily Monitoring

```bash
# Quick morning check (fast, page 1 only)
python baulkandcastle_scraper.py --daily
```

### Weekly Full Update

```bash
# Full scrape with extended sold history
python baulkandcastle_scraper.py --sold-pages 50

# Train fresh ML model
python ml/train_model.py

# Run ML estimates on for-sale
python ml/estimate_for_sale.py

# Fetch Domain estimates
python domain_estimator_helper.py --batch
```

### Property Research

```bash
# Get ML prediction for specific property
python ml/predict_property_value.py 550 4 --bathrooms 2 --suburb "CASTLE HILL" --property_type house

# JSON output for scripting
python ml/predict_property_value.py --json '{"beds": 4, "bathrooms": 2, "property_type": "house"}' --output json
```

---

## Output Files

| File | Description |
|------|-------------|
| `baulkandcastle_properties.db` | SQLite database with all property data |
| `baulkandcastle_sale_matches.html` | For-sale listings with filters |
| `baulkandcastle_sold_matches.html` | Sold properties sorted by date |
| `baulkandcastle_summary.html` | Dashboard with analytics |
| `ml/models/` | Trained ML model files |

---

## Database Schema

### Core Tables

**properties** - Static property information
```
property_id TEXT PRIMARY KEY
address TEXT
suburb TEXT (BAULKHAM HILLS | CASTLE HILL)
first_seen TEXT
url TEXT
in_excelsior_catchment INTEGER (0 or 1)
```

**listing_history** - Price/status snapshots over time
```
property_id TEXT
date TEXT
status TEXT (sale | sold)
price_display TEXT, price_value INTEGER
beds INTEGER, baths INTEGER, cars INTEGER
land_size TEXT, property_type TEXT
agent TEXT, sold_date TEXT
PRIMARY KEY (property_id, date, status)
```

**daily_summary** - Daily change counts
```
date TEXT PRIMARY KEY
new_count INTEGER, sold_count INTEGER, adj_count INTEGER
```

### Valuation Tables

**property_valuations** - PropertyValue.com estimates (if scraped)
**domain_estimates** - Domain Property Profile estimates
**property_estimates** - ML model predictions
**property_estimates_history** - Historical ML predictions

---

## Report Features

### For-Sale & Sold Reports
- **Suburb column** - Color-coded (blue=Baulkham Hills, orange=Castle Hill)
- **Excelsior column** - Checkmark for catchment properties
- **Catchment filter** - Toggle to show only Excelsior catchment
- **Price tracking** - First seen price vs current price
- **Valuation columns** - PropertyValue, Domain Estimate, ML prediction

### Summary Dashboard
- **Stats cards** - Total tracked, for sale count, average price, by suburb
- **Excelsior catchment** - Count with breakdown (for sale | sold)
- **ML predictions table** - Typical property configurations
- **Daily history** - New, sold, adjusted counts per day
- **Sold summary** - Monthly stats by bedroom count

---

## Excelsior Catchment Feature

Properties within Excelsior Public School catchment zone are automatically flagged.

### How It Works
1. Scrapes Domain's school catchment page for property IDs
2. Matches against existing properties in database
3. Sets `in_excelsior_catchment = 1` for matching properties
4. Updates automatically during full scrape

### Reports
- **Column**: "Excelsior" shows checkmark for catchment properties
- **Filter**: "Show only Excelsior catchment" checkbox
- **Dashboard**: Green stat card with breakdown

### Standalone Update
```bash
python baulkandcastle_scraper.py --update-catchment
```

---

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | API documentation |
| `/api/health` | GET | Health check |
| `/api/model-info` | GET | Model metadata & metrics |
| `/api/predict` | POST | Single property prediction |
| `/api/predict/batch` | POST | Multiple property predictions |

### Example Request
```json
POST /api/predict
{
  "land_size": 600,
  "beds": 4,
  "bathrooms": 2,
  "car_spaces": 2,
  "suburb": "CASTLE HILL",
  "property_type": "house"
}
```

### Example Response
```json
{
  "status": "success",
  "prediction": {
    "predicted_price": 1850000,
    "price_range_low": 1600000,
    "price_range_high": 2100000,
    "confidence_level": "Model confidence: Good"
  }
}
```

---

## Scheduling

### Windows Task Scheduler

```
Program: C:\Tools PHPC\baulkandcastle\.venv\Scripts\python.exe
Arguments: baulkandcastle_scraper.py
Start in: C:\Tools PHPC\baulkandcastle
Schedule: Daily at 8:00 AM
```

### Linux/Mac Cron

```bash
# Daily at 8 AM
0 8 * * * cd /path/to/baulkandcastle && .venv/bin/python baulkandcastle_scraper.py

# Weekly full scrape on Sunday
0 6 * * 0 cd /path/to/baulkandcastle && .venv/bin/python baulkandcastle_scraper.py --sold-pages 50
```

---

## Requirements

- **Python 3.10+**
- **crawl4ai** - Web scraping with browser automation
- **beautifulsoup4** - HTML parsing
- **pandas, numpy, scikit-learn, xgboost** - ML pipeline
- **flask, flask-cors** - API server (optional)
- **playwright** - Domain estimator browser automation (optional)

---

## Project Structure

```
baulkandcastle/
├── baulkandcastle_scraper.py    # Main scraper
├── domain_estimator_helper.py   # Domain estimate scraper
├── api_server.py                # Flask REST API
├── test_domain_estimator.py     # Test suite
├── requirements.txt             # Python dependencies
├── README.md                    # This file
├── USAGE_GUIDE.md              # Detailed usage guide
│
├── ml/                          # Machine learning module
│   ├── train_model.py          # Model training
│   ├── predict_property_value.py # CLI predictions
│   ├── estimate_for_sale.py    # Batch estimation
│   ├── valuation_predictor.py  # Core ML class
│   └── models/                 # Saved model files
│
├── .claude/                     # Claude Code integration
│   └── commands/
│       └── domain-estimator.md # Claude skill definition
│
└── Generated files:
    ├── baulkandcastle_properties.db
    ├── baulkandcastle_sale_matches.html
    ├── baulkandcastle_sold_matches.html
    └── baulkandcastle_summary.html
```

---

## License

For personal use only.
