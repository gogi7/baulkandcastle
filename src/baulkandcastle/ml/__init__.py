"""
Machine Learning modules for property valuation.

Provides XGBoost-based property valuation with multi-suburb,
multi-property-type support and 17 engineered features.
"""

from baulkandcastle.ml.valuation_predictor import PropertyValuationModel
from baulkandcastle.ml.feature_engineering import (
    engineer_features,
    compute_rolling_avg_price_per_m2,
)

__all__ = [
    "PropertyValuationModel",
    "engineer_features",
    "compute_rolling_avg_price_per_m2",
]
