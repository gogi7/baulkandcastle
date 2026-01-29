#!/usr/bin/env python
"""
CLI for running the Property Valuation API Server.

Usage:
    python -m baulkandcastle.cli.api_server
    python -m baulkandcastle.cli.api_server --port 8080
    python -m baulkandcastle.cli.api_server --host 0.0.0.0 --port 5000 --debug
"""

import argparse
import sys

from baulkandcastle.config import get_config
from baulkandcastle.logging_config import setup_logging, get_logger


def main():
    """Main entry point for the API server CLI."""
    parser = argparse.ArgumentParser(
        description="Property Valuation API Server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python -m baulkandcastle.cli.api_server
    python -m baulkandcastle.cli.api_server --port 8080
    python -m baulkandcastle.cli.api_server --host 0.0.0.0 --debug
        """,
    )
    parser.add_argument(
        "--host",
        type=str,
        default=None,
        help="Host to bind to (default: from config or 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Port to bind to (default: from config or 5000)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug mode",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default=None,
        help="Set log level",
    )

    args = parser.parse_args()

    # Setup logging
    setup_logging(level=args.log_level)
    logger = get_logger(__name__)

    config = get_config()
    host = args.host or config.api.host
    port = args.port or config.api.port
    debug = args.debug or config.api.debug

    logger.info("Starting Property Valuation API Server")
    logger.info("Host: %s, Port: %d, Debug: %s", host, port, debug)

    try:
        from baulkandcastle.api.server import run_server
        run_server(host=host, port=port, debug=debug)
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
        sys.exit(0)
    except Exception as e:
        logger.error("Server error: %s", e, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
