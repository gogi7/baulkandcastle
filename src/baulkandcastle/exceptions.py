"""
Custom Exceptions for Baulkham & Castle Property Tracker

Provides a hierarchy of exceptions for standardized error handling across all modules.

Exception Hierarchy:
    BaulkAndCastleError (base)
    ├── ConfigurationError
    ├── DatabaseError
    │   └── DatabaseConnectionError
    ├── ScraperError
    │   ├── NetworkError
    │   └── ParsingError
    ├── EstimatorError
    ├── ModelError
    │   ├── ModelNotFoundError
    │   └── PredictionError
    └── ValidationError
"""


class BaulkAndCastleError(Exception):
    """Base exception for all Baulkham & Castle errors."""

    def __init__(self, message: str, *args, **kwargs):
        self.message = message
        super().__init__(message, *args, **kwargs)


# Configuration Errors
class ConfigurationError(BaulkAndCastleError):
    """Raised when there's a configuration problem."""

    pass


# Database Errors
class DatabaseError(BaulkAndCastleError):
    """Base exception for database-related errors."""

    pass


class DatabaseConnectionError(DatabaseError):
    """Raised when unable to connect to the database."""

    pass


# Scraper Errors
class ScraperError(BaulkAndCastleError):
    """Base exception for scraper-related errors."""

    pass


class NetworkError(ScraperError):
    """Raised when a network request fails."""

    def __init__(self, message: str, url: str = None, status_code: int = None):
        self.url = url
        self.status_code = status_code
        super().__init__(message)


class ParsingError(ScraperError):
    """Raised when HTML or data parsing fails."""

    def __init__(self, message: str, source: str = None):
        self.source = source
        super().__init__(message)


# Estimator Errors
class EstimatorError(BaulkAndCastleError):
    """Raised when Domain estimate extraction fails."""

    def __init__(self, message: str, property_id: str = None):
        self.property_id = property_id
        super().__init__(message)


# ML Model Errors
class ModelError(BaulkAndCastleError):
    """Base exception for ML model-related errors."""

    pass


class ModelNotFoundError(ModelError):
    """Raised when the trained model file is not found."""

    def __init__(self, model_path: str = None):
        self.model_path = model_path
        message = f"Model not found at: {model_path}" if model_path else "Model not found"
        super().__init__(message)


class PredictionError(ModelError):
    """Raised when a prediction fails."""

    def __init__(self, message: str, input_data: dict = None):
        self.input_data = input_data
        super().__init__(message)


class TrainingError(ModelError):
    """Raised when model training fails."""

    pass


class InsufficientDataError(ModelError):
    """Raised when there's not enough data for training or prediction."""

    def __init__(self, message: str, required: int = None, available: int = None):
        self.required = required
        self.available = available
        super().__init__(message)


# Validation Errors
class ValidationError(BaulkAndCastleError):
    """Raised when input validation fails."""

    def __init__(self, message: str, field: str = None, value=None):
        self.field = field
        self.value = value
        super().__init__(message)
