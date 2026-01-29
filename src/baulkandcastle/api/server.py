"""
Flask Application Factory

Creates and configures the Flask application.
"""

import os
from pathlib import Path

from flask import Flask, send_from_directory, send_file

from baulkandcastle.config import get_config
from baulkandcastle.api.routes import register_routes
from baulkandcastle.logging_config import setup_logging, get_logger

logger = get_logger(__name__)


def create_app(test_config=None) -> Flask:
    """Create and configure the Flask application.

    Args:
        test_config: Optional test configuration dict.

    Returns:
        Configured Flask application.
    """
    config = get_config()

    # Setup logging
    setup_logging()

    # Determine static folder for frontend
    frontend_dir = Path(config.api.frontend_dir)
    if frontend_dir.exists():
        app = Flask(
            __name__,
            static_folder=str(frontend_dir),
            static_url_path="",
        )
    else:
        app = Flask(__name__)

    # Apply configuration
    app.config["DEBUG"] = config.api.debug

    if test_config:
        app.config.update(test_config)

    # Enable CORS
    try:
        from flask_cors import CORS
        CORS(app)
    except ImportError:
        logger.warning("flask-cors not installed, CORS not enabled")

    # Register API routes
    register_routes(app)

    # Serve frontend in production
    if frontend_dir.exists():
        @app.route("/")
        def serve_frontend():
            """Serve the React frontend."""
            return send_from_directory(app.static_folder, "index.html")

        @app.route("/<path:path>")
        def serve_static(path):
            """Serve static files or fallback to index.html for SPA routing."""
            # Check if it's an API route
            if path.startswith("api/"):
                # Let Flask handle API routes
                return app.send_static_file(path)

            # Try to serve the static file
            static_file = Path(app.static_folder) / path
            if static_file.exists():
                return send_from_directory(app.static_folder, path)

            # Fallback to index.html for SPA routing
            return send_from_directory(app.static_folder, "index.html")

    logger.info("Flask app created")
    return app


def run_server(host: str = None, port: int = None, debug: bool = None):
    """Run the Flask development server.

    Args:
        host: Host to bind to.
        port: Port to bind to.
        debug: Enable debug mode.
    """
    config = get_config()

    host = host or config.api.host
    port = port or config.api.port
    debug = debug if debug is not None else config.api.debug

    app = create_app()

    logger.info("Starting server on %s:%d", host, port)
    app.run(host=host, port=port, debug=debug)
