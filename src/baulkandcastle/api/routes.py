"""
API Routes for Property Valuation Service

Provides REST API endpoints for:
- Property value predictions
- Property data queries
- Dashboard statistics
- Model information
- Tool management and execution
"""

from datetime import datetime, timedelta
from typing import Dict, Any

from flask import Blueprint, request, jsonify

from baulkandcastle.config import get_config
from baulkandcastle.core.database import get_connection, fetch_all, fetch_one
from baulkandcastle.exceptions import (
    ModelNotFoundError,
    PredictionError,
    ValidationError,
)
from baulkandcastle.logging_config import get_logger
from baulkandcastle.utils.price_parser import format_price
from baulkandcastle.api.tools import (
    init_tools_tables,
    get_tool_definitions,
    get_execution_history,
    get_execution,
    start_tool_execution,
    cancel_execution,
)

logger = get_logger(__name__)

# Create blueprint
api = Blueprint("api", __name__, url_prefix="/api")

# Global model instance (lazy loaded)
_model = None


def get_model():
    """Lazy-load the ML model."""
    global _model
    if _model is None:
        from baulkandcastle.ml.valuation_predictor import PropertyValuationModel
        _model = PropertyValuationModel()
        if not _model.load():
            raise ModelNotFoundError(str(get_config().ml.model_path))
    return _model


# Health & Model Info Endpoints
@api.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint."""
    try:
        m = get_model()
        return jsonify({
            "status": "healthy",
            "model_loaded": True,
            "trained_at": m.metadata.get("trained_at", "unknown"),
        })
    except Exception as e:
        logger.warning("Health check failed: %s", e)
        return jsonify({
            "status": "unhealthy",
            "model_loaded": False,
            "error": str(e),
        }), 503


@api.route("/model-info", methods=["GET"])
def model_info():
    """Get model metadata and performance metrics."""
    try:
        m = get_model()
        return jsonify({
            "status": "success",
            "metadata": {
                "trained_at": m.metadata.get("trained_at"),
                "metrics": m.metadata.get("metrics"),
                "feature_importance": m.metadata.get("feature_importance"),
                "type_distribution": m.metadata.get("type_distribution"),
                "suburb_distribution": m.metadata.get("suburb_distribution"),
            },
        })
    except Exception as e:
        logger.error("Model info error: %s", e)
        return jsonify({"status": "error", "error": str(e)}), 500


# Prediction Endpoints
@api.route("/predict", methods=["POST"])
def predict():
    """Predict property value."""
    try:
        data = request.get_json()

        if not data:
            return jsonify({
                "status": "error",
                "error": "Request body must be JSON",
            }), 400

        if "beds" not in data:
            return jsonify({
                "status": "error",
                "error": "Missing required field: beds",
            }), 400

        params = {
            "beds": int(data["beds"]),
            "bathrooms": int(data.get("bathrooms", 2)),
            "car_spaces": int(data.get("car_spaces", 1)),
            "suburb": data.get("suburb", "CASTLE HILL"),
            "property_type": data.get("property_type", "house"),
        }

        if data.get("land_size") and float(data["land_size"]) > 0:
            params["land_size"] = float(data["land_size"])

        m = get_model()
        result = m.predict(**params)

        return jsonify({
            "status": "success",
            "prediction": result,
        })
    except (ModelNotFoundError, PredictionError) as e:
        logger.error("Prediction error: %s", e)
        return jsonify({"status": "error", "error": str(e)}), 500
    except (ValueError, TypeError) as e:
        return jsonify({"status": "error", "error": f"Invalid input: {e}"}), 400


# Property Data Endpoints
@api.route("/properties", methods=["GET"])
def get_properties():
    """Get all for-sale properties."""
    try:
        extended = request.args.get("extended", "false").lower() == "true"

        with get_connection() as conn:
            if extended:
                # Extended query with domain estimates, xgboost predictions, and daily changes
                properties = fetch_all(conn, """
                    SELECT DISTINCT
                        p.property_id,
                        p.address,
                        p.suburb,
                        p.first_seen,
                        p.url,
                        p.in_excelsior_catchment,
                        h.price_display,
                        h.price_value,
                        h.beds,
                        h.baths,
                        h.cars,
                        h.land_size,
                        h.property_type,
                        h.agent,
                        de.estimate_low as domain_estimate_low,
                        de.estimate_mid as domain_estimate_mid,
                        de.estimate_high as domain_estimate_high,
                        de.scraped_at as domain_scraped_at,
                        xp.predicted_price as xgboost_predicted_price,
                        xp.price_range_low as xgboost_price_low,
                        xp.price_range_high as xgboost_price_high,
                        xp.predicted_at as xgboost_predicted_at,
                        h.scraped_at as listing_scraped_at,
                        CAST(julianday('now') - julianday(p.first_seen) AS INTEGER) as days_on_market,
                        (
                            SELECT price_value
                            FROM listing_history
                            WHERE property_id = p.property_id AND status = 'sale' AND price_value > 0
                            ORDER BY date ASC
                            LIMIT 1
                        ) as initial_price,
                        (
                            SELECT COUNT(DISTINCT price_value)
                            FROM listing_history
                            WHERE property_id = p.property_id AND status = 'sale' AND price_value > 0
                        ) as price_change_count
                    FROM properties p
                    JOIN listing_history h ON p.property_id = h.property_id
                    LEFT JOIN domain_estimates de ON p.property_id = de.property_id
                    LEFT JOIN xgboost_predictions xp ON p.property_id = xp.property_id
                    WHERE h.status = 'sale'
                    AND h.date = (
                        SELECT MAX(date)
                        FROM listing_history
                        WHERE property_id = p.property_id AND status = 'sale'
                    )
                    ORDER BY p.first_seen DESC
                """)
            else:
                # Standard query for performance
                properties = fetch_all(conn, """
                    SELECT DISTINCT
                        p.property_id,
                        p.address,
                        p.suburb,
                        p.first_seen,
                        p.url,
                        p.in_excelsior_catchment,
                        h.price_display,
                        h.price_value,
                        h.beds,
                        h.baths,
                        h.cars,
                        h.land_size,
                        h.property_type,
                        h.agent
                    FROM properties p
                    JOIN listing_history h ON p.property_id = h.property_id
                    WHERE h.status = 'sale'
                    AND h.date = (
                        SELECT MAX(date)
                        FROM listing_history
                        WHERE property_id = p.property_id AND status = 'sale'
                    )
                    ORDER BY p.first_seen DESC
                """)

        return jsonify({
            "status": "success",
            "count": len(properties),
            "properties": properties,
        })
    except Exception as e:
        logger.error("Error fetching properties: %s", e)
        return jsonify({"status": "error", "error": str(e)}), 500


@api.route("/properties/<property_id>", methods=["GET"])
def get_property(property_id: str):
    """Get single property detail."""
    try:
        with get_connection() as conn:
            property_data = fetch_one(conn, """
                SELECT
                    p.*,
                    h.price_display,
                    h.price_value,
                    h.beds,
                    h.baths,
                    h.cars,
                    h.land_size,
                    h.property_type,
                    h.agent,
                    h.status,
                    h.sold_date
                FROM properties p
                JOIN listing_history h ON p.property_id = h.property_id
                WHERE p.property_id = ?
                ORDER BY h.date DESC
                LIMIT 1
            """, (property_id,))

            if not property_data:
                return jsonify({
                    "status": "error",
                    "error": "Property not found",
                }), 404

            # Get price history
            history = fetch_all(conn, """
                SELECT date, price_display, price_value, status
                FROM listing_history
                WHERE property_id = ?
                ORDER BY date ASC
            """, (property_id,))

            # Get predictions if available
            prediction = fetch_one(conn, """
                SELECT * FROM xgboost_predictions WHERE property_id = ?
            """, (property_id,))

            # Get domain estimate if available
            estimate = fetch_one(conn, """
                SELECT * FROM domain_estimates WHERE property_id = ?
            """, (property_id,))

        return jsonify({
            "status": "success",
            "property": property_data,
            "history": history,
            "prediction": prediction,
            "estimate": estimate,
        })
    except Exception as e:
        logger.error("Error fetching property %s: %s", property_id, e)
        return jsonify({"status": "error", "error": str(e)}), 500


@api.route("/sold", methods=["GET"])
def get_sold_properties():
    """Get sold properties."""
    try:
        limit = request.args.get("limit", 100, type=int)
        offset = request.args.get("offset", 0, type=int)

        with get_connection() as conn:
            properties = fetch_all(conn, """
                SELECT DISTINCT
                    p.property_id,
                    p.address,
                    p.suburb,
                    p.url,
                    h.price_display,
                    h.price_value,
                    h.beds,
                    h.baths,
                    h.cars,
                    h.land_size,
                    h.property_type,
                    h.sold_date,
                    h.sold_date_iso,
                    h.price_per_m2
                FROM properties p
                JOIN listing_history h ON p.property_id = h.property_id
                WHERE h.status = 'sold'
                ORDER BY h.sold_date_iso DESC
                LIMIT ? OFFSET ?
            """, (limit, offset))

            total = fetch_one(conn, """
                SELECT COUNT(DISTINCT property_id) as count
                FROM listing_history
                WHERE status = 'sold'
            """)

        return jsonify({
            "status": "success",
            "count": len(properties),
            "total": total["count"] if total else 0,
            "properties": properties,
        })
    except Exception as e:
        logger.error("Error fetching sold properties: %s", e)
        return jsonify({"status": "error", "error": str(e)}), 500


@api.route("/stats", methods=["GET"])
def get_stats():
    """Get dashboard statistics."""
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

        with get_connection() as conn:
            # Total for sale
            for_sale = fetch_one(conn, """
                SELECT COUNT(DISTINCT property_id) as count
                FROM listing_history
                WHERE status = 'sale'
                AND date = (SELECT MAX(date) FROM listing_history WHERE status = 'sale')
            """)

            # Total sold (all time)
            total_sold = fetch_one(conn, """
                SELECT COUNT(DISTINCT property_id) as count
                FROM listing_history
                WHERE status = 'sold'
            """)

            # New this week
            new_this_week = fetch_one(conn, """
                SELECT COUNT(*) as count
                FROM properties
                WHERE first_seen >= ?
            """, (week_ago,))

            # Sold this week
            sold_this_week = fetch_one(conn, """
                SELECT COUNT(DISTINCT property_id) as count
                FROM listing_history
                WHERE status = 'sold'
                AND sold_date_iso >= ?
            """, (week_ago,))

            # Average prices
            avg_for_sale = fetch_one(conn, """
                SELECT AVG(price_value) as avg_price
                FROM listing_history
                WHERE status = 'sale'
                AND price_value > 0
                AND date = (SELECT MAX(date) FROM listing_history WHERE status = 'sale')
            """)

            avg_sold = fetch_one(conn, """
                SELECT AVG(price_value) as avg_price
                FROM listing_history
                WHERE status = 'sold'
                AND price_value > 0
                AND sold_date_iso >= ?
            """, ((datetime.now() - timedelta(days=180)).strftime("%Y-%m-%d"),))

            # By suburb
            by_suburb = fetch_all(conn, """
                SELECT
                    p.suburb,
                    COUNT(DISTINCT CASE WHEN h.status = 'sale' THEN p.property_id END) as for_sale,
                    COUNT(DISTINCT CASE WHEN h.status = 'sold' THEN p.property_id END) as sold
                FROM properties p
                JOIN listing_history h ON p.property_id = h.property_id
                GROUP BY p.suburb
            """)

            # By property type
            by_type = fetch_all(conn, """
                SELECT
                    h.property_type,
                    COUNT(DISTINCT h.property_id) as count
                FROM listing_history h
                WHERE h.status = 'sale'
                AND h.date = (SELECT MAX(date) FROM listing_history WHERE status = 'sale')
                GROUP BY h.property_type
            """)

        return jsonify({
            "status": "success",
            "stats": {
                "total_for_sale": for_sale["count"] if for_sale else 0,
                "total_sold": total_sold["count"] if total_sold else 0,
                "new_this_week": new_this_week["count"] if new_this_week else 0,
                "sold_this_week": sold_this_week["count"] if sold_this_week else 0,
                "avg_price_for_sale": avg_for_sale["avg_price"] if avg_for_sale else 0,
                "avg_price_sold": avg_sold["avg_price"] if avg_sold else 0,
                "by_suburb": {row["suburb"]: row for row in by_suburb},
                "by_property_type": {row["property_type"]: row["count"] for row in by_type if row["property_type"]},
            },
        })
    except Exception as e:
        logger.error("Error fetching stats: %s", e)
        return jsonify({"status": "error", "error": str(e)}), 500


@api.route("/stats/trends", methods=["GET"])
def get_trends():
    """Get price trend data for charts."""
    try:
        months = request.args.get("months", 12, type=int)
        cutoff = (datetime.now() - timedelta(days=months * 30)).strftime("%Y-%m-%d")

        with get_connection() as conn:
            trends = fetch_all(conn, """
                SELECT
                    strftime('%Y-%m', sold_date_iso) as month,
                    suburb,
                    property_type,
                    COUNT(*) as count,
                    AVG(price_value) as avg_price,
                    AVG(price_per_m2) as avg_price_per_m2
                FROM listing_history h
                JOIN properties p ON h.property_id = p.property_id
                WHERE h.status = 'sold'
                AND h.sold_date_iso >= ?
                AND h.price_value > 0
                GROUP BY month, suburb, property_type
                ORDER BY month ASC
            """, (cutoff,))

        return jsonify({
            "status": "success",
            "trends": trends,
        })
    except Exception as e:
        logger.error("Error fetching trends: %s", e)
        return jsonify({"status": "error", "error": str(e)}), 500


@api.route("/suburbs", methods=["GET"])
def get_suburbs():
    """Get list of suburbs."""
    try:
        with get_connection() as conn:
            suburbs = fetch_all(conn, """
                SELECT DISTINCT suburb
                FROM properties
                ORDER BY suburb
            """)

        return jsonify({
            "status": "success",
            "suburbs": [s["suburb"] for s in suburbs],
        })
    except Exception as e:
        logger.error("Error fetching suburbs: %s", e)
        return jsonify({"status": "error", "error": str(e)}), 500


# Tool Management Endpoints
@api.route("/tools", methods=["GET"])
def list_tools():
    """Get all available tools with their definitions and last run info."""
    try:
        tools = get_tool_definitions()
        return jsonify({
            "status": "success",
            "tools": tools,
        })
    except Exception as e:
        logger.error("Error fetching tools: %s", e)
        return jsonify({"status": "error", "error": str(e)}), 500


@api.route("/tools/<tool_id>/run", methods=["POST"])
def run_tool(tool_id: str):
    """Start a tool execution."""
    try:
        data = request.get_json() or {}
        flags = data.get("flags")

        execution_id = start_tool_execution(tool_id, flags)

        return jsonify({
            "status": "success",
            "execution_id": execution_id,
        })
    except ValueError as e:
        return jsonify({"status": "error", "error": str(e)}), 400
    except Exception as e:
        logger.error("Error starting tool %s: %s", tool_id, e)
        return jsonify({"status": "error", "error": str(e)}), 500


@api.route("/tools/executions", methods=["GET"])
def list_executions():
    """Get execution history."""
    try:
        limit = request.args.get("limit", 20, type=int)
        tool_id = request.args.get("tool_id")

        executions = get_execution_history(limit=limit, tool_id=tool_id)

        return jsonify({
            "status": "success",
            "executions": executions,
        })
    except Exception as e:
        logger.error("Error fetching executions: %s", e)
        return jsonify({"status": "error", "error": str(e)}), 500


@api.route("/tools/executions/<int:execution_id>", methods=["GET"])
def get_execution_detail(execution_id: int):
    """Get a specific execution by ID."""
    try:
        execution = get_execution(execution_id)

        if not execution:
            return jsonify({
                "status": "error",
                "error": "Execution not found",
            }), 404

        return jsonify({
            "status": "success",
            "execution": execution,
        })
    except Exception as e:
        logger.error("Error fetching execution %d: %s", execution_id, e)
        return jsonify({"status": "error", "error": str(e)}), 500


@api.route("/tools/executions/<int:execution_id>/cancel", methods=["POST"])
def cancel_execution_endpoint(execution_id: int):
    """Cancel a running execution."""
    try:
        cancelled = cancel_execution(execution_id)

        return jsonify({
            "status": "success",
            "cancelled": cancelled,
        })
    except Exception as e:
        logger.error("Error cancelling execution %d: %s", execution_id, e)
        return jsonify({"status": "error", "error": str(e)}), 500


@api.route("/data-freshness", methods=["GET"])
def get_data_freshness():
    """Get data freshness timestamps for all data sources."""
    try:
        with get_connection() as conn:
            # Get most recent listing scrape time
            listing_freshness = fetch_one(conn, """
                SELECT MAX(scraped_at) as last_scraped
                FROM listing_history
                WHERE scraped_at IS NOT NULL
            """)

            # Get most recent domain estimate scrape time
            domain_freshness = fetch_one(conn, """
                SELECT MAX(scraped_at) as last_scraped
                FROM domain_estimates
                WHERE scraped_at IS NOT NULL
            """)

            # Get most recent xgboost prediction time
            xgboost_freshness = fetch_one(conn, """
                SELECT MAX(predicted_at) as last_predicted
                FROM xgboost_predictions
                WHERE predicted_at IS NOT NULL
            """)

        return jsonify({
            "status": "success",
            "freshness": {
                "listing_last_scraped": listing_freshness["last_scraped"] if listing_freshness else None,
                "domain_last_scraped": domain_freshness["last_scraped"] if domain_freshness else None,
                "xgboost_last_predicted": xgboost_freshness["last_predicted"] if xgboost_freshness else None,
            },
        })
    except Exception as e:
        logger.error("Error fetching data freshness: %s", e)
        return jsonify({"status": "error", "error": str(e)}), 500


@api.route("/admin/summary", methods=["GET"])
def get_admin_summary():
    """Get admin dashboard summary with freshness, quality metrics, and latest scrape info."""
    try:
        with get_connection() as conn:
            # === DATA FRESHNESS ===
            listing_freshness = fetch_one(conn, """
                SELECT MAX(scraped_at) as last_scraped
                FROM listing_history
                WHERE scraped_at IS NOT NULL
            """)

            domain_freshness = fetch_one(conn, """
                SELECT MAX(scraped_at) as last_scraped
                FROM domain_estimates
                WHERE scraped_at IS NOT NULL
            """)

            xgboost_freshness = fetch_one(conn, """
                SELECT MAX(predicted_at) as last_predicted
                FROM xgboost_predictions
                WHERE predicted_at IS NOT NULL
            """)

            # === DATA QUALITY ===
            # Total for-sale properties
            total_for_sale = fetch_one(conn, """
                SELECT COUNT(DISTINCT property_id) as count
                FROM listing_history
                WHERE status = 'sale'
                AND date = (SELECT MAX(date) FROM listing_history WHERE status = 'sale')
            """)
            total_count = total_for_sale["count"] if total_for_sale else 0

            # Properties with domain estimates
            with_domain = fetch_one(conn, """
                SELECT COUNT(DISTINCT h.property_id) as count
                FROM listing_history h
                JOIN domain_estimates de ON h.property_id = de.property_id
                WHERE h.status = 'sale'
                AND h.date = (SELECT MAX(date) FROM listing_history WHERE status = 'sale')
            """)
            domain_count = with_domain["count"] if with_domain else 0

            # Properties with xgboost predictions
            with_xgboost = fetch_one(conn, """
                SELECT COUNT(DISTINCT h.property_id) as count
                FROM listing_history h
                JOIN xgboost_predictions xp ON h.property_id = xp.property_id
                WHERE h.status = 'sale'
                AND h.date = (SELECT MAX(date) FROM listing_history WHERE status = 'sale')
            """)
            xgboost_count = with_xgboost["count"] if with_xgboost else 0

            # Calculate coverage percentages
            domain_coverage = (domain_count / total_count * 100) if total_count > 0 else 0
            xgboost_coverage = (xgboost_count / total_count * 100) if total_count > 0 else 0

            # === LAST SCRAPE INFO ===
            last_scrape = fetch_one(conn, """
                SELECT id, completed_at, summary, summary_json, status
                FROM tool_executions
                WHERE tool_id = 'scraper' AND status = 'completed'
                ORDER BY completed_at DESC
                LIMIT 1
            """)

            # === DAILY CHANGES (from daily_summary table) ===
            daily_changes = {"new_count": 0, "sold_count": 0, "adjusted_count": 0}
            try:
                today = datetime.now().strftime("%Y-%m-%d")
                daily_summary = fetch_one(conn, """
                    SELECT new_count, sold_count, adj_count
                    FROM daily_summary
                    WHERE date = ?
                """, (today,))
                if daily_summary:
                    daily_changes = {
                        "new_count": daily_summary["new_count"] or 0,
                        "sold_count": daily_summary["sold_count"] or 0,
                        "adjusted_count": daily_summary["adj_count"] or 0,
                    }
            except Exception:
                pass  # Table might not exist yet

            # === AVERAGE PRICE ===
            avg_price = fetch_one(conn, """
                SELECT AVG(price_value) as avg_price
                FROM listing_history
                WHERE status = 'sale'
                AND price_value > 0
                AND date = (SELECT MAX(date) FROM listing_history WHERE status = 'sale')
            """)

        return jsonify({
            "status": "success",
            "freshness": {
                "listings": listing_freshness["last_scraped"] if listing_freshness else None,
                "domain_estimates": domain_freshness["last_scraped"] if domain_freshness else None,
                "xgboost_predictions": xgboost_freshness["last_predicted"] if xgboost_freshness else None,
            },
            "data_quality": {
                "total_for_sale": total_count,
                "with_domain_estimate": domain_count,
                "with_xgboost_prediction": xgboost_count,
                "domain_coverage_pct": round(domain_coverage, 1),
                "xgboost_coverage_pct": round(xgboost_coverage, 1),
                "avg_price": int(avg_price["avg_price"]) if avg_price and avg_price["avg_price"] else 0,
            },
            "last_scrape": {
                "completed_at": last_scrape["completed_at"] if last_scrape else None,
                "summary": last_scrape["summary"] if last_scrape else None,
                "status": last_scrape["status"] if last_scrape else None,
            } if last_scrape else None,
            "daily_changes": daily_changes,
        })
    except Exception as e:
        logger.error("Error fetching admin summary: %s", e)
        return jsonify({"status": "error", "error": str(e)}), 500


@api.route("/db-stats", methods=["GET"])
def get_db_stats():
    """Get comprehensive database statistics for validation and debugging."""
    try:
        with get_connection() as conn:
            # Get all tables and row counts
            tables_query = fetch_all(conn, """
                SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'
            """)

            tables = []
            for t in tables_query:
                table_name = t["name"]
                count = fetch_one(conn, f"SELECT COUNT(*) as count FROM {table_name}")
                tables.append({
                    "name": table_name,
                    "rows": count["count"] if count else 0
                })

            # Properties date range
            props_range = fetch_one(conn, """
                SELECT MIN(first_seen) as earliest, MAX(first_seen) as latest, COUNT(*) as total
                FROM properties
            """)

            # Listing history date range
            history_range = fetch_one(conn, """
                SELECT MIN(date) as earliest, MAX(date) as latest
                FROM listing_history
            """)

            # Status breakdown in listing_history
            status_breakdown = fetch_all(conn, """
                SELECT status, COUNT(*) as count FROM listing_history GROUP BY status
            """)

            # Sold date range (actual sale dates, not scrape dates)
            sold_range = fetch_one(conn, """
                SELECT MIN(sold_date_iso) as earliest, MAX(sold_date_iso) as latest
                FROM listing_history WHERE sold_date_iso IS NOT NULL
            """)

            # Monthly sold distribution
            monthly_sold = fetch_all(conn, """
                SELECT substr(sold_date_iso, 1, 7) as month, COUNT(*) as count
                FROM listing_history
                WHERE sold_date_iso IS NOT NULL
                GROUP BY month
                ORDER BY month
            """)

            # Latest inserts per table
            latest_inserts = {}

            # Latest properties
            latest_props = fetch_all(conn, """
                SELECT property_id, address, suburb, first_seen
                FROM properties
                ORDER BY first_seen DESC
                LIMIT 5
            """)
            latest_inserts["properties"] = [dict(p) for p in latest_props]

            # Latest listing history entries
            latest_history = fetch_all(conn, """
                SELECT property_id, date, status, price_display, scraped_at
                FROM listing_history
                ORDER BY scraped_at DESC
                LIMIT 5
            """)
            latest_inserts["listing_history"] = [dict(h) for h in latest_history]

            # Latest sold entries
            latest_sold = fetch_all(conn, """
                SELECT lh.property_id, p.address, lh.price_display, lh.sold_date_iso, lh.scraped_at
                FROM listing_history lh
                JOIN properties p ON lh.property_id = p.property_id
                WHERE lh.status = 'sold'
                ORDER BY lh.scraped_at DESC
                LIMIT 5
            """)
            latest_inserts["sold"] = [dict(s) for s in latest_sold]

            # Daily summary
            daily_summary = fetch_all(conn, """
                SELECT date, new_count, sold_count, adj_count
                FROM daily_summary
                ORDER BY date DESC
                LIMIT 10
            """)

            # Active for-sale count (latest scrape date)
            active_sale = fetch_one(conn, """
                SELECT COUNT(DISTINCT property_id) as count
                FROM listing_history
                WHERE status = 'sale'
                AND date = (SELECT MAX(date) FROM listing_history WHERE status = 'sale')
            """)

        return jsonify({
            "status": "success",
            "tables": tables,
            "properties": {
                "total": props_range["total"] if props_range else 0,
                "first_seen_range": {
                    "earliest": props_range["earliest"] if props_range else None,
                    "latest": props_range["latest"] if props_range else None,
                }
            },
            "listing_history": {
                "scrape_date_range": {
                    "earliest": history_range["earliest"] if history_range else None,
                    "latest": history_range["latest"] if history_range else None,
                },
                "status_breakdown": {s["status"]: s["count"] for s in status_breakdown},
            },
            "sold_data": {
                "sold_date_range": {
                    "earliest": sold_range["earliest"] if sold_range else None,
                    "latest": sold_range["latest"] if sold_range else None,
                },
                "monthly_distribution": [{"month": m["month"], "count": m["count"]} for m in monthly_sold],
            },
            "active_for_sale": active_sale["count"] if active_sale else 0,
            "latest_inserts": latest_inserts,
            "daily_summary": [dict(d) for d in daily_summary],
            "data_model_info": {
                "uniqueness": "property_id (extracted from Domain URL) is the unique identifier",
                "history_tracking": "listing_history stores daily snapshots with composite key (property_id, date, status)",
                "sold_handling": "Sold properties get one immutable record; sold_date_iso is when property actually sold",
                "scrape_tracking": "scraped_at = when we scraped it; date = scrape day; first_seen = first appearance",
            }
        })
    except Exception as e:
        logger.error("Error fetching DB stats: %s", e)
        return jsonify({"status": "error", "error": str(e)}), 500


def register_routes(app):
    """Register API routes with Flask app."""
    app.register_blueprint(api)

    # Initialize tools tables
    try:
        init_tools_tables()
    except Exception as e:
        logger.warning("Failed to initialize tools tables: %s", e)

    logger.info("API routes registered")
