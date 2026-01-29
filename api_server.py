#!/usr/bin/env python
"""
Property Valuation API Server

Flask-based REST API for property value predictions.

Usage:
    python api_server.py
    python api_server.py --port 5000 --host 0.0.0.0

Endpoints:
    POST /api/predict - Predict property value
    GET  /api/health  - Health check
    GET  /api/model-info - Model metadata
"""

import argparse
import json
import sys
from pathlib import Path

try:
    from flask import Flask, request, jsonify
    from flask_cors import CORS
except ImportError:
    print("Error: Flask not installed. Run: pip install flask flask-cors")
    sys.exit(1)

# Add current directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from ml.valuation_predictor import PropertyValuationModel

# Serve React frontend from dist/ if it exists
import os
frontend_dir = os.environ.get('BAULKANDCASTLE_FRONTEND_DIR', 'frontend/dist')
if os.path.isdir(frontend_dir):
    app = Flask(__name__, static_folder=frontend_dir, static_url_path='')
else:
    app = Flask(__name__)
CORS(app)


@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve_frontend(path):
    """Serve React frontend (SPA fallback)."""
    if path.startswith('api/'):
        return jsonify({'error': 'Not found'}), 404
    if app.static_folder:
        file_path = os.path.join(app.static_folder, path)
        if os.path.isfile(file_path):
            return app.send_static_file(path)
        # SPA fallback — serve index.html for client-side routing
        index = os.path.join(app.static_folder, 'index.html')
        if os.path.isfile(index):
            return app.send_static_file('index.html')
    return jsonify({'error': 'Not found'}), 404

# Global model instance
model = None


def get_model():
    """Lazy-load the model."""
    global model
    if model is None:
        model = PropertyValuationModel()
        if not model.load():
            raise RuntimeError("Model not found. Run 'python ml/train_model.py' first.")
    return model


@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    try:
        m = get_model()
        return jsonify({
            'status': 'healthy',
            'model_loaded': True,
            'trained_at': m.metadata.get('trained_at', 'unknown')
        })
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'model_loaded': False,
            'error': str(e)
        }), 503


@app.route('/api/model-info', methods=['GET'])
def model_info():
    """Get model metadata and performance metrics."""
    try:
        m = get_model()
        return jsonify({
            'status': 'success',
            'metadata': {
                'trained_at': m.metadata.get('trained_at'),
                'metrics': m.metadata.get('metrics'),
                'feature_importance': m.metadata.get('feature_importance'),
                'type_distribution': m.metadata.get('type_distribution'),
                'suburb_distribution': m.metadata.get('suburb_distribution'),
            }
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500


@app.route('/api/predict', methods=['POST'])
def predict():
    """
    Predict property value.

    Request body (JSON):
    {
        "land_size": 600,
        "beds": 4,
        "bathrooms": 2,
        "car_spaces": 2,
        "suburb": "CASTLE HILL",
        "property_type": "house"
    }

    Response:
    {
        "status": "success",
        "prediction": {
            "predicted_price": 1850000,
            "price_range_low": 1600000,
            "price_range_high": 2100000,
            ...
        }
    }
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({
                'status': 'error',
                'error': 'Request body must be JSON'
            }), 400

        # Validate required fields - only beds is required, land_size is optional for units
        if 'beds' not in data:
            return jsonify({
                'status': 'error',
                'error': 'Missing required field: beds'
            }), 400

        # Extract parameters with defaults
        params = {
            'beds': int(data['beds']),
            'bathrooms': int(data.get('bathrooms', 2)),
            'car_spaces': int(data.get('car_spaces', 1)),
            'suburb': data.get('suburb', 'CASTLE HILL'),
            'property_type': data.get('property_type', 'house'),
        }

        # Add land_size only if provided and > 0
        if data.get('land_size') and float(data['land_size']) > 0:
            params['land_size'] = float(data['land_size'])

        # Get prediction
        m = get_model()
        result = m.predict(**params)

        return jsonify({
            'status': 'success',
            'prediction': result
        })

    except ValueError as e:
        return jsonify({
            'status': 'error',
            'error': f'Invalid input: {str(e)}'
        }), 400
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500


@app.route('/api/predict/batch', methods=['POST'])
def predict_batch():
    """
    Predict values for multiple properties.

    Request body (JSON):
    {
        "properties": [
            {"land_size": 600, "beds": 4, ...},
            {"land_size": 150, "beds": 2, ...}
        ]
    }
    """
    try:
        data = request.get_json()

        if not data or 'properties' not in data:
            return jsonify({
                'status': 'error',
                'error': 'Request body must contain "properties" array'
            }), 400

        properties = data['properties']
        if not isinstance(properties, list):
            return jsonify({
                'status': 'error',
                'error': '"properties" must be an array'
            }), 400

        m = get_model()
        results = m.predict_batch(properties)

        return jsonify({
            'status': 'success',
            'predictions': results
        })

    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500


@app.route('/api/predict/all-listings', methods=['POST'])
def predict_all_listings():
    """
    Run XGBoost predictions for all current sale listings and save to database.

    Request body (optional JSON):
    {
        "status": "sale"  // or "sold"
    }

    Response:
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
    """
    try:
        data = request.get_json() or {}
        listing_status = data.get('status', 'sale')

        if listing_status not in ('sale', 'sold'):
            return jsonify({
                'status': 'error',
                'error': 'status must be "sale" or "sold"'
            }), 400

        m = get_model()
        db_path = Path(__file__).parent / 'baulkandcastle_properties.db'

        predictions, summary = m.predict_all_listings(str(db_path), listing_status)

        return jsonify({
            'status': 'success',
            'summary': summary
        })

    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500


@app.route('/api/docs', methods=['GET'])
def api_docs():
    """API documentation."""
    return jsonify({
        'name': 'Property Valuation API',
        'version': '1.0.0',
        'description': 'XGBoost-based property valuation for Baulkham Hills & Castle Hill',
        'endpoints': {
            'GET /api/health': 'Health check',
            'GET /api/model-info': 'Get model metadata',
            'GET /predictor': 'Interactive prediction interface',
            'POST /api/predict': 'Predict single property value',
            'POST /api/predict/batch': 'Predict multiple property values',
            'POST /api/predict/all-listings': 'Predict all sale listings and save to DB',
        },
        'example_request': {
            'url': 'POST /api/predict',
            'body': {
                'land_size': 600,
                'beds': 4,
                'bathrooms': 2,
                'car_spaces': 2,
                'suburb': 'CASTLE HILL',
                'property_type': 'house'
            }
        }
    })


@app.route('/predictor', methods=['GET'])
def predictor_interface():
    """Interactive HTML interface for property value predictions."""
    try:
        m = get_model()
        model_info = {
            'trained_at': m.metadata.get('trained_at', 'Unknown')[:10] if m.metadata.get('trained_at') else 'Unknown',
            'r2': m.metadata.get('metrics', {}).get('r2', 0),
            'mape': m.metadata.get('metrics', {}).get('mape', 15),
        }
    except Exception:
        model_info = {'trained_at': 'Model not loaded', 'r2': 0, 'mape': 0}

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>XGBoost Property Predictor - Baulkham Hills & Castle Hill</title>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            * {{ margin: 0; padding: 0; box-sizing: border-box; }}
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                padding: 20px;
            }}
            .container {{
                max-width: 800px;
                margin: 0 auto;
                background: white;
                border-radius: 15px;
                box-shadow: 0 20px 40px rgba(0,0,0,0.2);
                overflow: hidden;
            }}
            .header {{
                background: linear-gradient(135deg, #1a73e8 0%, #4285f4 100%);
                color: white;
                padding: 25px 30px;
                text-align: center;
            }}
            .header h1 {{ font-size: 1.8em; margin-bottom: 8px; }}
            .header p {{ opacity: 0.9; font-size: 0.95em; }}
            .model-info {{
                background: rgba(255,255,255,0.1);
                padding: 10px 15px;
                border-radius: 8px;
                margin-top: 15px;
                font-size: 0.85em;
            }}
            .content {{ padding: 30px; }}
            .form-grid {{
                display: grid;
                grid-template-columns: repeat(2, 1fr);
                gap: 20px;
            }}
            .form-group {{
                display: flex;
                flex-direction: column;
            }}
            .form-group.full-width {{
                grid-column: span 2;
            }}
            .form-group label {{
                font-weight: 600;
                color: #333;
                margin-bottom: 8px;
                font-size: 0.9em;
            }}
            .form-group input, .form-group select {{
                padding: 12px 15px;
                border: 2px solid #e1e8ed;
                border-radius: 8px;
                font-size: 1em;
                transition: border-color 0.3s;
            }}
            .form-group input:focus, .form-group select:focus {{
                outline: none;
                border-color: #1a73e8;
            }}
            .form-group .hint {{
                font-size: 0.8em;
                color: #666;
                margin-top: 5px;
            }}
            .btn {{
                background: linear-gradient(135deg, #1a73e8 0%, #4285f4 100%);
                color: white;
                padding: 15px 30px;
                border: none;
                border-radius: 8px;
                font-size: 1.1em;
                font-weight: 600;
                cursor: pointer;
                transition: transform 0.2s, box-shadow 0.2s;
                width: 100%;
                margin-top: 20px;
            }}
            .btn:hover {{
                transform: translateY(-2px);
                box-shadow: 0 8px 25px rgba(26, 115, 232, 0.4);
            }}
            .btn:disabled {{
                background: #ccc;
                cursor: not-allowed;
                transform: none;
                box-shadow: none;
            }}
            .result {{
                margin-top: 30px;
                padding: 25px;
                background: linear-gradient(135deg, #f8f9ff 0%, #e3f2fd 100%);
                border-radius: 12px;
                border-left: 5px solid #1a73e8;
                display: none;
            }}
            .result.show {{ display: block; }}
            .result h3 {{
                color: #1a73e8;
                margin-bottom: 15px;
                font-size: 1.3em;
            }}
            .result .price {{
                font-size: 2.5em;
                font-weight: 700;
                color: #34a853;
                margin: 15px 0;
            }}
            .result .range {{
                color: #666;
                font-size: 1.1em;
                margin-bottom: 15px;
            }}
            .result .details {{
                font-size: 0.9em;
                color: #555;
                background: white;
                padding: 15px;
                border-radius: 8px;
                margin-top: 15px;
            }}
            .result .details p {{ margin: 5px 0; }}
            .error {{
                background: #fee;
                border-left-color: #d93025;
            }}
            .error h3 {{ color: #d93025; }}
            .batch-section {{
                margin-top: 40px;
                padding-top: 30px;
                border-top: 2px solid #e1e8ed;
            }}
            .batch-section h3 {{
                color: #333;
                margin-bottom: 15px;
            }}
            .batch-section p {{
                color: #666;
                margin-bottom: 15px;
            }}
            .btn-batch {{
                background: linear-gradient(135deg, #34a853 0%, #66bb6a 100%);
            }}
            .btn-batch:hover {{
                box-shadow: 0 8px 25px rgba(52, 168, 83, 0.4);
            }}
            .batch-result {{
                margin-top: 15px;
                padding: 15px;
                background: #f0fff4;
                border-radius: 8px;
                border-left: 5px solid #34a853;
                display: none;
            }}
            .batch-result.show {{ display: block; }}
            @media (max-width: 600px) {{
                .form-grid {{ grid-template-columns: 1fr; }}
                .form-group.full-width {{ grid-column: span 1; }}
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>XGBoost Property Predictor</h1>
                <p>Baulkham Hills & Castle Hill Property Valuation</p>
                <div class="model-info">
                    Model trained: {model_info['trained_at']} | R&sup2;: {model_info['r2']:.2%} | MAPE: {model_info['mape']:.1f}%
                </div>
            </div>
            <div class="content">
                <form id="predictForm">
                    <div class="form-grid">
                        <div class="form-group">
                            <label for="suburb">Suburb</label>
                            <select id="suburb" name="suburb" required>
                                <option value="CASTLE HILL">Castle Hill</option>
                                <option value="BAULKHAM HILLS">Baulkham Hills</option>
                            </select>
                        </div>
                        <div class="form-group">
                            <label for="property_type">Property Type</label>
                            <select id="property_type" name="property_type" required>
                                <option value="house">House</option>
                                <option value="townhouse">Townhouse</option>
                                <option value="unit">Unit/Apartment</option>
                                <option value="villa">Villa</option>
                                <option value="duplex">Duplex</option>
                            </select>
                        </div>
                        <div class="form-group">
                            <label for="beds">Bedrooms</label>
                            <input type="number" id="beds" name="beds" value="4" min="1" max="10" required>
                        </div>
                        <div class="form-group">
                            <label for="bathrooms">Bathrooms</label>
                            <input type="number" id="bathrooms" name="bathrooms" value="2" min="1" max="10" required>
                        </div>
                        <div class="form-group">
                            <label for="car_spaces">Car Spaces</label>
                            <input type="number" id="car_spaces" name="car_spaces" value="2" min="0" max="10" required>
                        </div>
                        <div class="form-group">
                            <label for="land_size">Land Size (m&sup2;)</label>
                            <input type="number" id="land_size" name="land_size" value="600" min="0" max="10000">
                            <span class="hint">Leave 0 or empty for units (strata title)</span>
                        </div>
                    </div>
                    <button type="submit" class="btn" id="predictBtn">Get Prediction</button>
                </form>

                <div id="result" class="result">
                    <h3>Predicted Value</h3>
                    <div class="price" id="predictedPrice">$0</div>
                    <div class="range" id="priceRange">Range: $0 - $0</div>
                    <div class="details" id="resultDetails"></div>
                </div>

                <div class="batch-section">
                    <h3>Batch Prediction - All Listings</h3>
                    <p>Run XGBoost predictions for all current sale listings and save to the database.</p>
                    <button class="btn btn-batch" id="batchBtn" onclick="runBatchPrediction()">
                        Run Predictions for All Listings
                    </button>
                    <div id="batchResult" class="batch-result"></div>
                </div>
            </div>
        </div>

        <script>
            document.getElementById('predictForm').addEventListener('submit', async function(e) {{
                e.preventDefault();
                const btn = document.getElementById('predictBtn');
                const result = document.getElementById('result');
                btn.disabled = true;
                btn.textContent = 'Predicting...';
                result.classList.remove('show', 'error');

                const formData = {{
                    suburb: document.getElementById('suburb').value,
                    property_type: document.getElementById('property_type').value,
                    beds: parseInt(document.getElementById('beds').value),
                    bathrooms: parseInt(document.getElementById('bathrooms').value),
                    car_spaces: parseInt(document.getElementById('car_spaces').value),
                    land_size: parseInt(document.getElementById('land_size').value) || 0
                }};

                try {{
                    const response = await fetch('/api/predict', {{
                        method: 'POST',
                        headers: {{ 'Content-Type': 'application/json' }},
                        body: JSON.stringify(formData)
                    }});
                    const data = await response.json();

                    if (data.status === 'success') {{
                        const pred = data.prediction;
                        document.getElementById('predictedPrice').textContent =
                            '$' + pred.predicted_price.toLocaleString();
                        document.getElementById('priceRange').textContent =
                            'Range: $' + pred.price_range_low.toLocaleString() +
                            ' - $' + pred.price_range_high.toLocaleString();

                        const inputs = pred.input_features;
                        let details = '<p><strong>Input Features:</strong></p>';
                        details += '<p>Suburb: ' + inputs.suburb + '</p>';
                        details += '<p>Type: ' + inputs.property_type_consolidated + '</p>';
                        details += '<p>Beds: ' + inputs.beds + ' | Baths: ' + inputs.bathrooms + ' | Cars: ' + inputs.car_spaces + '</p>';
                        if (inputs.property_type_consolidated !== 'unit') {{
                            details += '<p>Land: ' + inputs.land_size_used + 'm&sup2;' +
                                (inputs.has_real_land_size ? ' (provided)' : ' (estimated)') + '</p>';
                        }}
                        details += '<p><em>' + pred.confidence_level + '</em></p>';
                        document.getElementById('resultDetails').innerHTML = details;
                        result.classList.remove('error');
                    }} else {{
                        document.getElementById('predictedPrice').textContent = 'Error';
                        document.getElementById('priceRange').textContent = data.error;
                        document.getElementById('resultDetails').innerHTML = '';
                        result.classList.add('error');
                    }}
                }} catch (err) {{
                    document.getElementById('predictedPrice').textContent = 'Error';
                    document.getElementById('priceRange').textContent = err.message;
                    document.getElementById('resultDetails').innerHTML = '';
                    result.classList.add('error');
                }}

                result.classList.add('show');
                btn.disabled = false;
                btn.textContent = 'Get Prediction';
            }});

            async function runBatchPrediction() {{
                const btn = document.getElementById('batchBtn');
                const result = document.getElementById('batchResult');
                btn.disabled = true;
                btn.textContent = 'Running predictions...';
                result.classList.remove('show');

                try {{
                    const response = await fetch('/api/predict/all-listings', {{
                        method: 'POST',
                        headers: {{ 'Content-Type': 'application/json' }},
                        body: JSON.stringify({{ status: 'sale' }})
                    }});
                    const data = await response.json();

                    if (data.status === 'success') {{
                        const s = data.summary;
                        result.innerHTML = '<strong>Batch Prediction Complete!</strong><br>' +
                            'Total listings: ' + s.total_listings + '<br>' +
                            'Successfully predicted: ' + s.success_count + '<br>' +
                            'Errors: ' + s.error_count + '<br>' +
                            'Saved to database: ' + s.saved_count + '<br>' +
                            '<small>Model version: ' + s.model_version + '</small>';
                        result.style.borderLeftColor = '#34a853';
                        result.style.background = '#f0fff4';
                    }} else {{
                        result.innerHTML = '<strong>Error:</strong> ' + data.error;
                        result.style.borderLeftColor = '#d93025';
                        result.style.background = '#fee';
                    }}
                }} catch (err) {{
                    result.innerHTML = '<strong>Error:</strong> ' + err.message;
                    result.style.borderLeftColor = '#d93025';
                    result.style.background = '#fee';
                }}

                result.classList.add('show');
                btn.disabled = false;
                btn.textContent = 'Run Predictions for All Listings';
            }}

            // Update land size hint based on property type
            document.getElementById('property_type').addEventListener('change', function() {{
                const landInput = document.getElementById('land_size');
                const hint = landInput.nextElementSibling;
                if (this.value === 'unit') {{
                    landInput.value = 0;
                    hint.textContent = 'Not applicable for units (strata title)';
                }} else if (this.value === 'townhouse') {{
                    if (landInput.value == 0) landInput.value = 200;
                    hint.textContent = 'Typical: 150-300m² for townhouses';
                }} else {{
                    if (landInput.value == 0) landInput.value = 600;
                    hint.textContent = 'Typical: 400-800m² for houses';
                }}
            }});
        </script>
    </body>
    </html>
    """
    return html


def main():
    parser = argparse.ArgumentParser(description="Property Valuation API Server")
    parser.add_argument('--host', type=str, default='127.0.0.1', help='Host to bind to')
    parser.add_argument('--port', type=int, default=5000, help='Port to listen on')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')

    args = parser.parse_args()

    print("=" * 60)
    print("PROPERTY VALUATION API SERVER")
    print("Baulkham Hills & Castle Hill")
    print("=" * 60)
    print(f"\nStarting server on http://{args.host}:{args.port}")
    print("\nEndpoints:")
    print("  GET  /                     - API documentation")
    print("  GET  /predictor            - Interactive prediction UI")
    print("  GET  /api/health           - Health check")
    print("  GET  /api/model-info       - Model metadata")
    print("  POST /api/predict          - Predict single property")
    print("  POST /api/predict/batch    - Batch predictions")
    print("  POST /api/predict/all-listings - Predict all sale listings")
    print("\nPress Ctrl+C to stop the server")
    print("=" * 60)

    app.run(host=args.host, port=args.port, debug=args.debug)


if __name__ == '__main__':
    main()
