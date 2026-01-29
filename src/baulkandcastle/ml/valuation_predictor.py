"""
Property Valuation Predictor for Baulkham Hills & Castle Hill

XGBoost-based ML model for predicting property values with support for:
- Multiple suburbs (Castle Hill, Baulkham Hills)
- Multiple property types (house, unit, townhouse, other)
- 17 engineered features including seasonal and market trend indicators

Author: Antigravity (for Goran)
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_absolute_percentage_error, r2_score
from sklearn.model_selection import train_test_split
from xgboost import XGBRegressor

from baulkandcastle.config import get_config
from baulkandcastle.exceptions import (
    InsufficientDataError,
    ModelNotFoundError,
    PredictionError,
    TrainingError,
)
from baulkandcastle.logging_config import get_logger
from baulkandcastle.ml.feature_engineering import (
    FEATURE_COLUMNS,
    engineer_features,
    parse_land_size,
    compute_rolling_avg_price_per_m2,
)
from baulkandcastle.utils.date_parser import parse_date
from baulkandcastle.utils.property_types import (
    consolidate_property_type,
    get_default_land_size,
    is_unit_type,
)

logger = get_logger(__name__)


class PropertyValuationModel:
    """XGBoost model for multi-suburb, multi-property-type valuation."""

    def __init__(self, model_dir: Optional[Path] = None):
        """Initialize the model.

        Args:
            model_dir: Directory for storing model files.
        """
        config = get_config()

        if model_dir is None:
            model_dir = Path(config.ml.model_dir)

        self.model_dir = Path(model_dir)
        self.model_dir.mkdir(parents=True, exist_ok=True)

        self.model_path = self.model_dir / "property_valuation_model.pkl"
        self.metadata_path = self.model_dir / "training_metadata.json"

        self.model: Optional[XGBRegressor] = None
        self.metadata: Dict = {}
        self.rolling_avg_cache: Dict[str, float] = {}

    def load_training_data(self, db_path: str) -> pd.DataFrame:
        """Load sold properties from database for training.

        Args:
            db_path: Path to SQLite database.

        Returns:
            DataFrame with sold property data.
        """
        logger.info("Loading training data from %s", db_path)

        conn = sqlite3.connect(db_path)

        query = """
            SELECT
                h.property_id,
                p.suburb,
                h.price_value,
                h.beds,
                h.baths,
                h.cars,
                h.land_size,
                h.property_type,
                h.price_per_m2,
                h.sold_date,
                h.sold_date_iso
            FROM listing_history h
            JOIN properties p ON h.property_id = p.property_id
            WHERE h.status = 'sold'
              AND h.price_value > 100000
              AND h.price_value < 10000000
        """

        df = pd.read_sql_query(query, conn)
        conn.close()

        logger.info("Loaded %d raw records", len(df))

        # Consolidate property types
        df["property_type_consolidated"] = df["property_type"].apply(consolidate_property_type)

        # Parse sold dates
        def parse_sold_date(row):
            # Prefer ISO format
            if pd.notna(row.get("sold_date_iso")):
                dt = parse_date(str(row["sold_date_iso"]))
                if dt:
                    return dt
            return parse_date(row.get("sold_date"))

        df["sold_date_parsed"] = df.apply(parse_sold_date, axis=1)

        # Remove rows without valid sold date
        initial_count = len(df)
        df = df[df["sold_date_parsed"].notna()].copy()
        logger.info("Removed %d rows with invalid dates", initial_count - len(df))

        return df

    def prepare_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Transform raw data into model features.

        Args:
            df: DataFrame with property data.

        Returns:
            DataFrame with engineered features.
        """
        df = df.copy()

        # Parse land size
        df["land_size_numeric"] = df["land_size"].apply(parse_land_size)

        # Track real land size data
        df["has_real_land_size"] = df["land_size_numeric"].notna().astype(int)

        # Handle land size by property type
        is_unit = df["property_type_consolidated"] == "unit"

        # Units: land size is not applicable
        df.loc[is_unit, "land_size_numeric"] = 0
        df.loc[is_unit, "has_real_land_size"] = 0

        # Houses/townhouses: impute missing with median
        for prop_type in ["house", "townhouse", "other"]:
            mask = (df["property_type_consolidated"] == prop_type) & df["land_size_numeric"].isna()
            type_median = df.loc[
                (df["property_type_consolidated"] == prop_type) & df["land_size_numeric"].notna(),
                "land_size_numeric",
            ].median()
            if pd.notna(type_median):
                df.loc[mask, "land_size_numeric"] = type_median
            else:
                df.loc[mask, "land_size_numeric"] = get_default_land_size(prop_type)
            df.loc[mask, "has_real_land_size"] = 0

        # Ensure numeric columns
        df["beds"] = pd.to_numeric(df["beds"], errors="coerce").fillna(3)
        df["baths"] = pd.to_numeric(df["baths"], errors="coerce").fillna(2)
        df["cars"] = pd.to_numeric(df["cars"], errors="coerce").fillna(1)

        # Derived ratios
        df["bedroom_to_land_ratio"] = df["beds"] / df["land_size_numeric"].clip(lower=1)
        df.loc[is_unit, "bedroom_to_land_ratio"] = 0
        df["bathroom_to_bedroom_ratio"] = df["baths"] / df["beds"].clip(lower=1)

        # Suburb encoding
        df["suburb_castle_hill"] = df["suburb"].str.upper().str.contains("CASTLE").astype(int)

        # Property type one-hot encoding
        df["property_type_house"] = (df["property_type_consolidated"] == "house").astype(int)
        df["property_type_unit"] = (df["property_type_consolidated"] == "unit").astype(int)
        df["property_type_townhouse"] = (df["property_type_consolidated"] == "townhouse").astype(int)

        # House with large land indicator
        df["is_house_large_land"] = (
            (df["property_type_consolidated"] == "house")
            & (df["land_size_numeric"] > 500)
            & (df["has_real_land_size"] == 1)
        ).astype(int)

        # Seasonal features
        if "sold_date_parsed" in df.columns:
            df["sale_month"] = df["sold_date_parsed"].dt.month
        else:
            df["sale_month"] = 6

        df["is_spring"] = df["sale_month"].isin([9, 10, 11]).astype(int)
        df["is_summer"] = df["sale_month"].isin([12, 1, 2]).astype(int)
        df["is_autumn"] = df["sale_month"].isin([3, 4, 5]).astype(int)
        df["is_winter"] = df["sale_month"].isin([6, 7, 8]).astype(int)

        # Years since sale
        now = datetime.now()
        if "sold_date_parsed" in df.columns:
            df["years_since_sale"] = (now - df["sold_date_parsed"]).dt.days / 365.25
        else:
            df["years_since_sale"] = 0

        # Rolling average price per m2
        if "sold_date_parsed" in df.columns and "price_per_m2" in df.columns:
            df["rolling_avg_price_per_m2"] = df.apply(
                lambda row: compute_rolling_avg_price_per_m2(
                    df, row["sold_date_parsed"], row["suburb"]
                )
                if pd.notna(row["sold_date_parsed"])
                else 10000.0,
                axis=1,
            )
        else:
            df["rolling_avg_price_per_m2"] = 10000.0

        return df

    def train(
        self,
        db_path: str = None,
        test_size: float = 0.2,
        random_state: int = 42,
        min_samples: int = 20,
    ) -> bool:
        """Train the XGBoost model on sold property data.

        Args:
            db_path: Path to database. Uses config default if not provided.
            test_size: Fraction of data for testing.
            random_state: Random seed for reproducibility.
            min_samples: Minimum samples required for training.

        Returns:
            True if training succeeded.

        Raises:
            InsufficientDataError: If not enough training data.
            TrainingError: If training fails.
        """
        config = get_config()
        if db_path is None:
            db_path = config.database.path

        logger.info("Starting model training")

        # Load data
        df = self.load_training_data(db_path)

        if len(df) < min_samples:
            raise InsufficientDataError(
                f"Insufficient training data: {len(df)} samples (minimum: {min_samples})",
                required=min_samples,
                available=len(df),
            )

        # Log distributions
        type_dist = df["property_type_consolidated"].value_counts()
        suburb_dist = df["suburb"].str.upper().value_counts()

        logger.info("Property type distribution: %s", type_dist.to_dict())
        logger.info("Suburb distribution: %s", suburb_dist.to_dict())

        # Prepare features
        logger.info("Preparing features")
        df = self.prepare_features(df)

        # Select features and target
        X = df[FEATURE_COLUMNS].copy()
        y = df["price_value"].copy()

        # Handle NaN
        X = X.fillna(X.median())

        # Train/test split
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=test_size, random_state=random_state
        )

        logger.info("Training set: %d samples", len(X_train))
        logger.info("Test set: %d samples", len(X_test))

        try:
            # Train model
            logger.info("Training XGBoost model")
            self.model = XGBRegressor(
                n_estimators=200,
                max_depth=6,
                learning_rate=0.1,
                subsample=0.8,
                colsample_bytree=0.8,
                min_child_weight=3,
                reg_alpha=0.1,
                reg_lambda=1.0,
                random_state=random_state,
                n_jobs=-1,
            )

            self.model.fit(X_train, y_train, eval_set=[(X_test, y_test)], verbose=False)

            # Evaluate
            y_pred = self.model.predict(X_test)

            metrics = {
                "r2": float(r2_score(y_test, y_pred)),
                "mae": float(mean_absolute_error(y_test, y_pred)),
                "mape": float(mean_absolute_percentage_error(y_test, y_pred) * 100),
                "train_size": len(X_train),
                "test_size": len(X_test),
                "total_samples": len(df),
            }

            logger.info("R² Score: %.4f", metrics["r2"])
            logger.info("MAE: $%,.0f", metrics["mae"])
            logger.info("MAPE: %.2f%%", metrics["mape"])

            # Feature importance
            feature_importance = dict(zip(FEATURE_COLUMNS, self.model.feature_importances_.tolist()))

            # Save metadata
            self.metadata = {
                "trained_at": datetime.now().isoformat(),
                "metrics": metrics,
                "feature_importance": feature_importance,
                "type_distribution": type_dist.to_dict(),
                "suburb_distribution": suburb_dist.to_dict(),
                "feature_columns": FEATURE_COLUMNS,
                "median_values": X.median().to_dict(),
            }

            # Save model
            self.save()

            return True

        except Exception as e:
            logger.error("Training failed: %s", e, exc_info=True)
            raise TrainingError(f"Model training failed: {e}") from e

    def save(self) -> None:
        """Save model and metadata to disk."""
        if self.model is None:
            raise ModelNotFoundError("No model to save. Train the model first.")

        joblib.dump(self.model, self.model_path)
        with open(self.metadata_path, "w") as f:
            json.dump(self.metadata, f, indent=2, default=str)

        logger.info("Model saved to: %s", self.model_path)
        logger.info("Metadata saved to: %s", self.metadata_path)

    def load(self) -> bool:
        """Load model and metadata from disk.

        Returns:
            True if model loaded successfully.
        """
        if not self.model_path.exists():
            logger.warning("Model not found at %s", self.model_path)
            return False

        try:
            self.model = joblib.load(self.model_path)
            if self.metadata_path.exists():
                with open(self.metadata_path, "r") as f:
                    self.metadata = json.load(f)
            logger.info("Model loaded from %s", self.model_path)
            return True
        except Exception as e:
            logger.error("Error loading model: %s", e)
            return False

    def predict(
        self,
        land_size: float = None,
        beds: int = 3,
        bathrooms: int = 2,
        car_spaces: int = 1,
        suburb: str = "CASTLE HILL",
        property_type: str = "house",
        sale_month: int = None,
        rolling_avg_price_per_m2: float = None,
    ) -> Dict:
        """Predict property value given features.

        Args:
            land_size: Land size in square meters (optional for units).
            beds: Number of bedrooms.
            bathrooms: Number of bathrooms.
            car_spaces: Number of car spaces.
            suburb: Suburb name.
            property_type: Property type.
            sale_month: Month of sale (1-12).
            rolling_avg_price_per_m2: Market trend indicator.

        Returns:
            Dictionary with prediction results.

        Raises:
            PredictionError: If prediction fails.
        """
        if self.model is None:
            if not self.load():
                raise ModelNotFoundError(str(self.model_path))

        try:
            # Consolidate property type
            prop_type = consolidate_property_type(property_type)
            is_unit = prop_type == "unit"

            # Handle land size
            if is_unit:
                effective_land_size = 0
                has_real_land_size = 0
            else:
                if land_size and land_size > 0:
                    effective_land_size = land_size
                    has_real_land_size = 1
                else:
                    effective_land_size = get_default_land_size(prop_type)
                    has_real_land_size = 0

            # Default sale month
            if sale_month is None:
                sale_month = datetime.now().month

            # Default rolling average
            if rolling_avg_price_per_m2 is None:
                if self.metadata and "median_values" in self.metadata:
                    rolling_avg_price_per_m2 = self.metadata["median_values"].get(
                        "rolling_avg_price_per_m2", 10000
                    )
                else:
                    rolling_avg_price_per_m2 = 10000

            # Build feature vector
            features = {
                "land_size_numeric": effective_land_size,
                "beds": beds,
                "baths": bathrooms,
                "cars": car_spaces,
                "bedroom_to_land_ratio": 0 if is_unit else beds / max(effective_land_size, 1),
                "bathroom_to_bedroom_ratio": bathrooms / max(beds, 1),
                "suburb_castle_hill": 1 if "CASTLE" in suburb.upper() else 0,
                "property_type_house": 1 if prop_type == "house" else 0,
                "property_type_unit": 1 if prop_type == "unit" else 0,
                "property_type_townhouse": 1 if prop_type == "townhouse" else 0,
                "is_house_large_land": (
                    1 if prop_type == "house" and effective_land_size > 500 and has_real_land_size else 0
                ),
                "has_real_land_size": has_real_land_size,
                "is_spring": 1 if sale_month in [9, 10, 11] else 0,
                "is_summer": 1 if sale_month in [12, 1, 2] else 0,
                "is_autumn": 1 if sale_month in [3, 4, 5] else 0,
                "is_winter": 1 if sale_month in [6, 7, 8] else 0,
                "years_since_sale": 0,
                "rolling_avg_price_per_m2": rolling_avg_price_per_m2,
            }

            # Create DataFrame
            X = pd.DataFrame([features])[FEATURE_COLUMNS]

            # Predict
            predicted_price = float(self.model.predict(X)[0])

            # Confidence range
            mape = self.metadata.get("metrics", {}).get("mape", 15)
            margin = predicted_price * (mape / 100)

            # Add confidence note for units without land size
            confidence_note = None
            if is_unit:
                confidence_note = "Land size not applicable for units"
            elif not has_real_land_size:
                confidence_note = f"Using imputed land size ({effective_land_size}m²)"

            return {
                "predicted_price": round(predicted_price, -3),
                "price_range_low": round(predicted_price - margin, -3),
                "price_range_high": round(predicted_price + margin, -3),
                "confidence_level": f"Based on MAPE: {mape:.1f}%",
                "confidence_note": confidence_note,
                "input_features": {
                    "land_size": land_size,
                    "land_size_used": effective_land_size,
                    "has_real_land_size": bool(has_real_land_size),
                    "beds": beds,
                    "bathrooms": bathrooms,
                    "car_spaces": car_spaces,
                    "suburb": suburb,
                    "property_type": property_type,
                    "property_type_consolidated": prop_type,
                },
            }

        except Exception as e:
            logger.error("Prediction failed: %s", e, exc_info=True)
            raise PredictionError(f"Prediction failed: {e}") from e

    def predict_batch(self, properties: List[Dict]) -> List[Dict]:
        """Predict values for multiple properties.

        Args:
            properties: List of property dictionaries.

        Returns:
            List of prediction results.
        """
        results = []
        for prop in properties:
            try:
                result = self.predict(**prop)
                results.append(result)
            except Exception as e:
                results.append({"error": str(e), "input": prop})
        return results

    def predict_all_listings(self, db_path: str = None, status: str = "sale") -> Tuple[List[Dict], Dict]:
        """Predict values for all current listings in the database.

        Args:
            db_path: Path to database.
            status: 'sale' or 'sold'.

        Returns:
            Tuple of (predictions list, summary stats).
        """
        config = get_config()
        if db_path is None:
            db_path = config.database.path

        if self.model is None:
            if not self.load():
                raise ModelNotFoundError(str(self.model_path))

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row

        query = """
            SELECT h.property_id, p.suburb, h.beds, h.baths, h.cars, h.land_size, h.property_type
            FROM listing_history h
            JOIN properties p ON h.property_id = p.property_id
            WHERE h.status = ?
            AND h.date = (SELECT MAX(date) FROM listing_history WHERE property_id = h.property_id AND status = ?)
        """
        listings = [dict(row) for row in conn.execute(query, (status, status)).fetchall()]

        predictions = []
        success_count = 0
        error_count = 0

        for listing in listings:
            try:
                land_size_val = parse_land_size(listing.get("land_size"))

                params = {
                    "land_size": land_size_val,
                    "beds": int(listing.get("beds") or 3),
                    "bathrooms": int(listing.get("baths") or 2),
                    "car_spaces": int(listing.get("cars") or 1),
                    "suburb": listing.get("suburb", "CASTLE HILL"),
                    "property_type": listing.get("property_type", "house"),
                }

                result = self.predict(**params)

                predictions.append({
                    "property_id": listing["property_id"],
                    "predicted_price": int(result["predicted_price"]),
                    "price_range_low": int(result["price_range_low"]),
                    "price_range_high": int(result["price_range_high"]),
                })
                success_count += 1

            except Exception as e:
                error_count += 1
                logger.warning("Error predicting %s: %s", listing.get("property_id"), e)

        # Save predictions
        model_version = self.metadata.get("trained_at", "unknown")
        now = datetime.now().isoformat()

        cursor = conn.cursor()
        for pred in predictions:
            cursor.execute(
                """
                INSERT OR REPLACE INTO xgboost_predictions
                (property_id, predicted_price, price_range_low, price_range_high, predicted_at, model_version)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    pred["property_id"],
                    pred["predicted_price"],
                    pred.get("price_range_low"),
                    pred.get("price_range_high"),
                    now,
                    model_version,
                ),
            )
        conn.commit()
        conn.close()

        summary = {
            "total_listings": len(listings),
            "success_count": success_count,
            "error_count": error_count,
            "saved_count": len(predictions),
            "model_version": model_version,
            "predicted_at": now,
        }

        logger.info(
            "Predicted %d/%d listings (%d errors)",
            success_count,
            len(listings),
            error_count,
        )

        return predictions, summary
