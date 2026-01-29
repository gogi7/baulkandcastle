"""
Centralized Configuration Module

Provides configuration classes and environment variable loading for all components.

Usage:
    from baulkandcastle.config import get_config

    config = get_config()
    db_path = config.database.path
    api_port = config.api.port
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv

# Load .env file if present
load_dotenv()


def _get_project_root() -> Path:
    """Get the project root directory."""
    # Navigate up from src/baulkandcastle/config.py to project root
    current = Path(__file__).resolve()
    # Go up: config.py -> baulkandcastle -> src -> project_root
    return current.parent.parent.parent


@dataclass
class DatabaseConfig:
    """Database configuration."""

    path: str = field(default_factory=lambda: os.getenv(
        "BAULKANDCASTLE_DB_PATH",
        str(_get_project_root() / "baulkandcastle_properties.db")
    ))

    def __post_init__(self):
        # Resolve relative paths
        if not os.path.isabs(self.path):
            self.path = str(_get_project_root() / self.path)


@dataclass
class APIConfig:
    """API server configuration."""

    host: str = field(default_factory=lambda: os.getenv(
        "BAULKANDCASTLE_API_HOST", "127.0.0.1"
    ))
    port: int = field(default_factory=lambda: int(os.getenv(
        "BAULKANDCASTLE_API_PORT", "5000"
    )))
    debug: bool = field(default_factory=lambda: os.getenv(
        "BAULKANDCASTLE_DEBUG", "false"
    ).lower() in ("true", "1", "yes"))
    frontend_dir: str = field(default_factory=lambda: os.getenv(
        "BAULKANDCASTLE_FRONTEND_DIR",
        str(_get_project_root() / "frontend" / "dist")
    ))


@dataclass
class ScraperConfig:
    """Scraper configuration."""

    target_suburbs: List[str] = field(default_factory=lambda: os.getenv(
        "BAULKANDCASTLE_TARGET_SUBURBS", "BAULKHAM HILLS,CASTLE HILL"
    ).split(","))
    scrape_delay: float = field(default_factory=lambda: float(os.getenv(
        "BAULKANDCASTLE_SCRAPE_DELAY", "2"
    )))
    excelsior_catchment_url: str = (
        "https://www.domain.com.au/school-catchment/excelsior-public-school-nsw-2154-637"
        "?ptype=apartment-unit-flat,block-of-units,duplex,free-standing,new-apartments,"
        "new-home-designs,new-house-land,pent-house,semi-detached,studio,terrace,"
        "town-house,villa&ssubs=0"
    )

    def __post_init__(self):
        # Normalize suburb names
        self.target_suburbs = [s.strip().upper() for s in self.target_suburbs]


@dataclass
class MLConfig:
    """Machine learning model configuration."""

    model_dir: str = field(default_factory=lambda: os.getenv(
        "BAULKANDCASTLE_MODEL_DIR",
        str(_get_project_root() / "ml" / "models")
    ))
    model_version: str = field(default_factory=lambda: os.getenv(
        "BAULKANDCASTLE_MODEL_VERSION", "1.0.0"
    ))

    def __post_init__(self):
        # Resolve relative paths
        if not os.path.isabs(self.model_dir):
            self.model_dir = str(_get_project_root() / self.model_dir)
        # Ensure directory exists
        Path(self.model_dir).mkdir(parents=True, exist_ok=True)

    @property
    def model_path(self) -> Path:
        """Path to the trained model file."""
        return Path(self.model_dir) / "property_valuation_model.pkl"

    @property
    def metadata_path(self) -> Path:
        """Path to the training metadata file."""
        return Path(self.model_dir) / "training_metadata.json"


@dataclass
class LoggingConfig:
    """Logging configuration."""

    level: str = field(default_factory=lambda: os.getenv(
        "BAULKANDCASTLE_LOG_LEVEL", "INFO"
    ).upper())
    log_file: Optional[str] = field(default_factory=lambda: os.getenv(
        "BAULKANDCASTLE_LOG_FILE"
    ))

    def __post_init__(self):
        # Validate log level
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if self.level not in valid_levels:
            self.level = "INFO"


@dataclass
class Config:
    """Main configuration container."""

    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    api: APIConfig = field(default_factory=APIConfig)
    scraper: ScraperConfig = field(default_factory=ScraperConfig)
    ml: MLConfig = field(default_factory=MLConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)


# Singleton instance
_config: Optional[Config] = None


def get_config() -> Config:
    """Get the global configuration instance.

    Returns:
        Config: The application configuration.
    """
    global _config
    if _config is None:
        _config = Config()
    return _config


def reset_config() -> None:
    """Reset the configuration (useful for testing)."""
    global _config
    _config = None
