"""
Logging Configuration Module

Provides consistent logging setup across all modules.

Usage:
    from baulkandcastle.logging_config import setup_logging, get_logger

    setup_logging()  # Call once at application startup
    logger = get_logger(__name__)
    logger.info("Application started")
"""

import logging
import sys
from pathlib import Path
from typing import Optional

from baulkandcastle.config import get_config

# Track if logging has been set up
_logging_configured = False


def setup_logging(
    level: Optional[str] = None,
    log_file: Optional[str] = None,
    force: bool = False,
) -> None:
    """Configure logging for the application.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
               Defaults to config value or INFO.
        log_file: Path to log file. If None, logs to console only.
        force: Force reconfiguration even if already configured.
    """
    global _logging_configured

    if _logging_configured and not force:
        return

    config = get_config()

    # Determine log level
    if level is None:
        level = config.logging.level
    level = level.upper()

    # Get numeric level
    numeric_level = getattr(logging, level, logging.INFO)

    # Determine log file
    if log_file is None:
        log_file = config.logging.log_file

    # Create formatter
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Get root logger for our package
    root_logger = logging.getLogger("baulkandcastle")
    root_logger.setLevel(numeric_level)

    # Remove existing handlers
    root_logger.handlers.clear()

    # Console handler (always)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # File handler (optional)
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        file_handler.setLevel(numeric_level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

    # Prevent propagation to root logger
    root_logger.propagate = False

    # Reduce noise from external libraries
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    logging.getLogger("playwright").setLevel(logging.WARNING)

    _logging_configured = True


def get_logger(name: str) -> logging.Logger:
    """Get a logger for the given module name.

    Args:
        name: Module name (typically __name__)

    Returns:
        Configured logger instance.

    Usage:
        logger = get_logger(__name__)
        logger.info("Processing started")
    """
    # Ensure logging is configured
    if not _logging_configured:
        setup_logging()

    # Prefix with package name if not already
    if not name.startswith("baulkandcastle"):
        name = f"baulkandcastle.{name}"

    return logging.getLogger(name)


def reset_logging() -> None:
    """Reset logging configuration (useful for testing)."""
    global _logging_configured
    _logging_configured = False

    # Clear handlers from our logger
    root_logger = logging.getLogger("baulkandcastle")
    root_logger.handlers.clear()
