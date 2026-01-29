# XGBoost Property Predictor Guide

This guide explains how to use the XGBoost property value predictor for Baulkham Hills & Castle Hill properties.

## Overview

The predictor uses a trained XGBoost machine learning model based on historical sold property data to estimate property values. Predictions are stored in the database with timestamps and displayed in the listings reports.

---

## Quick Start

### 1. Start the API Server

```bash
cd "C:\Tools PHPC\baulkandcastle"
python api_server.py
```

Server starts at `http://127.0.0.1:5000`

### 2. Open the Predictor Interface

Navigate to: **http://127.0.0.1:5000/predictor**

---

## Methods to Generate Predictions

### Method 1: Web Interface (Recommended)

1. Open `http://127.0.0.1:5000/predictor` in your browser
2. **For single property prediction:**
   - Select suburb (Castle Hill or Baulkham Hills)
   - Select property type (House, Townhouse, Unit, etc.)
   - Enter bedrooms, bathrooms, car spaces
   - Enter land size (leave 0 for units)
   - Click "Get Prediction"

3. **For batch predictions (all sale listings):**
   - Scroll to "Batch Prediction - All Listings" section
   - Click "Run Predictions for All Listings"
   - Wait for completion message
   - Predictions are automatically saved to database

### Method 2: API Endpoint

**Predict all sale listings:**
```bash
curl -X POST http://127.0.0.1:5000/api/predict/all-listings \
  -H "Content-Type: application/json" \
  -d '{"status": "sale"}'
```

**Response:**
```json
{
  "status": "success",
  "summary": {
    "total_listings": 150,
    "success_count": 148,
    "error_count": 2,
    "saved_count": 148,
    "model_version": "2024-01-21T...",
    "predicted_at": "2024-01-21T..."
  }
}
```

### Method 3: Python Script

```python
import sys
sys.path.insert(0, 'C:/Tools PHPC/baulkandcastle')

from ml.valuation_predictor import PropertyValuationModel

model = PropertyValuationModel()
model.load()

# Predict all sale listings
db_path = 'C:/Tools PHPC/baulkandcastle/baulkandcastle_properties.db'
predictions, summary = model.predict_all_listings(db_path, status='sale')

print(f"Predicted {summary['success_count']} properties")
print(f"Saved to database: {summary['saved_count']}")
```

### Method 4: Command Line (Single Property)

```bash
# House with land size
python ml/predict_property_value.py 600 4 --bathrooms 2 --car_spaces 2 --suburb "CASTLE HILL" --property_type house

# Unit (no land size needed)
python ml/predict_property_value.py 2 --bathrooms 1 --suburb "BAULKHAM HILLS" --property_type unit
```

---

## Viewing Predictions

### In Reports

After running predictions, regenerate reports to see values:

```bash
python baulkandcastle_scraper.py --reports-only
```

Open `baulkandcastle_sale_matches.html` - the "XGBoost Predict" column shows predicted values.

### In Database

Query the predictions table directly:

```sql
SELECT
    p.address,
    xp.predicted_price,
    xp.price_range_low,
    xp.price_range_high,
    xp.predicted_at
FROM xgboost_predictions xp
JOIN properties p ON xp.property_id = p.property_id
ORDER BY xp.predicted_at DESC;
```

---

## Database Schema

**Table: `xgboost_predictions`**

| Column | Type | Description |
|--------|------|-------------|
| property_id | TEXT | Primary key, links to properties table |
| predicted_price | INTEGER | XGBoost predicted value |
| price_range_low | INTEGER | Lower bound of prediction range |
| price_range_high | INTEGER | Upper bound of prediction range |
| predicted_at | TEXT | ISO timestamp of prediction |
| model_version | TEXT | Model training timestamp |

---

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/predictor` | GET | Interactive web interface |
| `/api/predict` | POST | Single property prediction |
| `/api/predict/batch` | POST | Multiple properties prediction |
| `/api/predict/all-listings` | POST | Predict all sale listings & save to DB |
| `/api/model-info` | GET | Model metadata and metrics |
| `/api/health` | GET | Health check |

---

## Workflow: Daily Predictions

Recommended daily workflow:

```bash
# 1. Run scraper to get latest listings
python baulkandcastle_scraper.py --daily

# 2. Start API server (if not running)
python api_server.py &

# 3. Run predictions for all sale listings
curl -X POST http://127.0.0.1:5000/api/predict/all-listings -H "Content-Type: application/json" -d '{"status": "sale"}'

# 4. Regenerate reports with predictions
python baulkandcastle_scraper.py --reports-only
```

Or use the web interface at `/predictor` and click "Run Predictions for All Listings".

---

## Troubleshooting

**"Model not found" error:**
```bash
python ml/train_model.py
```

**Predictions not showing in reports:**
- Run `python baulkandcastle_scraper.py --reports-only` to regenerate

**API server not responding:**
- Check if running: `curl http://127.0.0.1:5000/api/health`
- Restart: `python api_server.py`

---

## Model Information

- **Algorithm:** XGBoost Regressor
- **Features:** 18 features including beds, baths, cars, land size, suburb, property type, seasonal indicators
- **Training data:** Historical sold properties from database
- **Metrics:** R² score, MAE, MAPE displayed in predictor interface

View current model metrics:
```bash
curl http://127.0.0.1:5000/api/model-info
```
