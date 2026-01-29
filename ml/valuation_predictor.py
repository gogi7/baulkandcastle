"""
Property Valuation Predictor for Baulkham Hills & Castle Hill

XGBoost-based ML model for predicting property values with support for:
- Multiple suburbs (Castle Hill, Baulkham Hills)
- Multiple property types (house, unit, townhouse, other)
- 17 engineered features including seasonal and market trend indicators

Author: Antigravity (for Goran)
"""

import re
import sqlite3
import json
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Tuple, List

import numpy as np
import pandas as pd
import joblib
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, mean_absolute_percentage_error, r2_score
from xgboost import XGBRegressor


class PropertyValuationModel:
    """XGBoost model for multi-suburb, multi-property-type valuation."""

    # Property type consolidation mapping
    PROPERTY_TYPE_MAP = {
        'house': 'house',
        'free-standing': 'house',
        'duplex': 'house',
        'semi-detached': 'house',
        'terrace': 'house',
        'villa': 'house',
        'unit': 'unit',
        'apartment': 'unit',
        'apartment-unit-flat': 'unit',
        'studio': 'unit',
        'pent-house': 'unit',
        'flat': 'unit',
        'townhouse': 'townhouse',
        'town-house': 'townhouse',
        'other': 'other',
        'vacant-land': 'other',
        'land': 'other',
        'block-of-units': 'other',
        'development-site': 'other',
    }

    FEATURE_COLUMNS = [
        'land_size_numeric',
        'beds',
        'baths',
        'cars',
        'bedroom_to_land_ratio',
        'bathroom_to_bedroom_ratio',
        'suburb_castle_hill',
        'property_type_house',
        'property_type_unit',
        'property_type_townhouse',
        'is_house_large_land',
        'has_real_land_size',  # 1 if land size from scraped data, 0 if imputed/not applicable
        'is_spring',
        'is_summer',
        'is_autumn',
        'is_winter',
        'years_since_sale',
        'rolling_avg_price_per_m2',
    ]

    def __init__(self, model_dir: Optional[Path] = None):
        """Initialize the model."""
        if model_dir is None:
            model_dir = Path(__file__).parent / 'models'
        self.model_dir = Path(model_dir)
        self.model_dir.mkdir(parents=True, exist_ok=True)

        self.model_path = self.model_dir / 'property_valuation_model.pkl'
        self.metadata_path = self.model_dir / 'training_metadata.json'

        self.model: Optional[XGBRegressor] = None
        self.metadata: Dict = {}
        self.rolling_avg_cache: Dict[str, float] = {}

    def _parse_land_size(self, land_size_str: str) -> Optional[float]:
        """Extract numeric land size from string like '450m²' or '450'."""
        if not land_size_str or land_size_str in ('na', 'NA', '-', ''):
            return None
        match = re.search(r'(\d+(?:\.\d+)?)', str(land_size_str))
        if match:
            value = float(match.group(1))
            return value if value > 0 else None
        return None

    def _consolidate_property_type(self, prop_type: str) -> str:
        """Map various property types to consolidated categories."""
        if not prop_type:
            return 'other'
        prop_type_lower = str(prop_type).lower().strip()
        return self.PROPERTY_TYPE_MAP.get(prop_type_lower, 'other')

    def _parse_sold_date(self, sold_date_str: str) -> Optional[datetime]:
        """Parse sold date from various formats."""
        if not sold_date_str:
            return None
        try:
            # Try ISO format first
            if 'T' in sold_date_str:
                return datetime.fromisoformat(sold_date_str.split('T')[0])
            # Try "DD MMM YYYY" format
            try:
                return datetime.strptime(sold_date_str, "%d %b %Y")
            except ValueError:
                pass
            # Try ISO date only
            try:
                return datetime.fromisoformat(sold_date_str)
            except ValueError:
                pass
        except Exception:
            pass
        return None

    def _compute_rolling_avg_price_per_m2(
        self, df: pd.DataFrame, current_date: datetime, suburb: str, lookback_days: int = 180
    ) -> float:
        """Compute rolling average price per m2 for a suburb."""
        cache_key = f"{suburb}_{current_date.strftime('%Y-%m')}"
        if cache_key in self.rolling_avg_cache:
            return self.rolling_avg_cache[cache_key]

        # Filter to same suburb, valid price_per_m2, and within lookback period
        cutoff = current_date - pd.Timedelta(days=lookback_days)
        mask = (
            (df['suburb'].str.upper() == suburb.upper()) &
            (df['price_per_m2'].notna()) &
            (df['price_per_m2'] > 0) &
            (df['sold_date_parsed'] < current_date) &
            (df['sold_date_parsed'] >= cutoff)
        )
        subset = df.loc[mask, 'price_per_m2']

        if len(subset) >= 5:
            avg = subset.mean()
        else:
            # Fall back to overall average if not enough suburb data
            overall_mask = (
                (df['price_per_m2'].notna()) &
                (df['price_per_m2'] > 0) &
                (df['sold_date_parsed'] < current_date)
            )
            avg = df.loc[overall_mask, 'price_per_m2'].mean()

        self.rolling_avg_cache[cache_key] = avg if pd.notna(avg) else 10000.0
        return self.rolling_avg_cache[cache_key]

    def prepare_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Transform raw data into model features."""
        df = df.copy()

        # Parse land size
        df['land_size_numeric'] = df['land_size'].apply(self._parse_land_size)

        # Track which properties have real (scraped) land size data
        df['has_real_land_size'] = df['land_size_numeric'].notna().astype(int)

        # Handle land size based on property type:
        # - Units: land size is not applicable, set to 0 (strata title)
        # - Houses/Townhouses: use real data if available, else impute median
        is_unit = df['property_type_consolidated'] == 'unit'

        # For units: set land size to 0 and mark as no real land size
        df.loc[is_unit, 'land_size_numeric'] = 0
        df.loc[is_unit, 'has_real_land_size'] = 0

        # For houses and townhouses: fill missing with median (only for those types)
        for prop_type in ['house', 'townhouse', 'other']:
            mask = (df['property_type_consolidated'] == prop_type) & df['land_size_numeric'].isna()
            type_median = df.loc[
                (df['property_type_consolidated'] == prop_type) & df['land_size_numeric'].notna(),
                'land_size_numeric'
            ].median()
            if pd.notna(type_median):
                df.loc[mask, 'land_size_numeric'] = type_median
                df.loc[mask, 'has_real_land_size'] = 0  # Mark as imputed
            else:
                df.loc[mask, 'land_size_numeric'] = 450  # Default fallback for houses
                df.loc[mask, 'has_real_land_size'] = 0

        # Ensure numeric columns
        df['beds'] = pd.to_numeric(df['beds'], errors='coerce').fillna(3)
        df['baths'] = pd.to_numeric(df['baths'], errors='coerce').fillna(2)
        df['cars'] = pd.to_numeric(df['cars'], errors='coerce').fillna(1)

        # Derived ratios (for units, bedroom_to_land_ratio will be 0)
        df['bedroom_to_land_ratio'] = df['beds'] / df['land_size_numeric'].clip(lower=1)
        # For units, set this ratio to 0 since land size is not meaningful
        df.loc[is_unit, 'bedroom_to_land_ratio'] = 0

        df['bathroom_to_bedroom_ratio'] = df['baths'] / df['beds'].clip(lower=1)

        # Suburb encoding (Castle Hill = 1, Baulkham Hills = 0)
        df['suburb_castle_hill'] = df['suburb'].str.upper().str.contains('CASTLE').astype(int)

        # Property type one-hot encoding
        df['property_type_house'] = (df['property_type_consolidated'] == 'house').astype(int)
        df['property_type_unit'] = (df['property_type_consolidated'] == 'unit').astype(int)
        df['property_type_townhouse'] = (df['property_type_consolidated'] == 'townhouse').astype(int)

        # Interaction feature: house with large land (>500m²) - only if real land size
        df['is_house_large_land'] = (
            (df['property_type_consolidated'] == 'house') &
            (df['land_size_numeric'] > 500) &
            (df['has_real_land_size'] == 1)
        ).astype(int)

        # Seasonal features (from sold date)
        if 'sold_date_parsed' in df.columns:
            df['sale_month'] = df['sold_date_parsed'].dt.month
        else:
            df['sale_month'] = 6  # Default to June

        df['is_spring'] = df['sale_month'].isin([9, 10, 11]).astype(int)
        df['is_summer'] = df['sale_month'].isin([12, 1, 2]).astype(int)
        df['is_autumn'] = df['sale_month'].isin([3, 4, 5]).astype(int)
        df['is_winter'] = df['sale_month'].isin([6, 7, 8]).astype(int)

        # Years since sale (for time-based market adjustment)
        now = datetime.now()
        if 'sold_date_parsed' in df.columns:
            df['years_since_sale'] = (now - df['sold_date_parsed']).dt.days / 365.25
        else:
            df['years_since_sale'] = 0

        # Rolling average price per m2 (market trend indicator)
        if 'sold_date_parsed' in df.columns and 'price_per_m2' in df.columns:
            df['rolling_avg_price_per_m2'] = df.apply(
                lambda row: self._compute_rolling_avg_price_per_m2(
                    df, row['sold_date_parsed'], row['suburb']
                ) if pd.notna(row['sold_date_parsed']) else 10000.0,
                axis=1
            )
        else:
            df['rolling_avg_price_per_m2'] = 10000.0

        return df

    def load_training_data(self, db_path: str) -> pd.DataFrame:
        """Load sold properties from database for training."""
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

        # Consolidate property types
        df['property_type_consolidated'] = df['property_type'].apply(self._consolidate_property_type)

        # Parse sold dates (prefer sold_date_iso, fall back to sold_date)
        def parse_date(row):
            if pd.notna(row.get('sold_date_iso')):
                try:
                    return datetime.fromisoformat(str(row['sold_date_iso']))
                except Exception:
                    pass
            return self._parse_sold_date(row.get('sold_date'))

        df['sold_date_parsed'] = df.apply(parse_date, axis=1)

        # Remove rows without valid sold date
        df = df[df['sold_date_parsed'].notna()].copy()

        return df

    def train(
        self,
        db_path: str,
        test_size: float = 0.2,
        random_state: int = 42
    ) -> Dict:
        """Train the XGBoost model on sold property data."""
        print("Loading training data...")
        df = self.load_training_data(db_path)
        print(f"Loaded {len(df)} sold properties")

        # Property type distribution
        type_dist = df['property_type_consolidated'].value_counts()
        print(f"\nProperty type distribution:")
        for ptype, count in type_dist.items():
            print(f"  {ptype}: {count}")

        # Suburb distribution
        suburb_dist = df['suburb'].str.upper().value_counts()
        print(f"\nSuburb distribution:")
        for suburb, count in suburb_dist.items():
            print(f"  {suburb}: {count}")

        # Prepare features
        print("\nPreparing features...")
        df = self.prepare_features(df)

        # Select features and target
        X = df[self.FEATURE_COLUMNS].copy()
        y = df['price_value'].copy()

        # Handle any remaining NaN values
        X = X.fillna(X.median())

        # Train/test split
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=test_size, random_state=random_state
        )

        print(f"\nTraining set: {len(X_train)} samples")
        print(f"Test set: {len(X_test)} samples")

        # Train XGBoost model
        print("\nTraining XGBoost model...")
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

        self.model.fit(
            X_train, y_train,
            eval_set=[(X_test, y_test)],
            verbose=False
        )

        # Evaluate
        y_pred = self.model.predict(X_test)

        metrics = {
            'r2': r2_score(y_test, y_pred),
            'mae': mean_absolute_error(y_test, y_pred),
            'mape': mean_absolute_percentage_error(y_test, y_pred) * 100,
            'train_samples': len(X_train),
            'test_samples': len(X_test),
            'total_samples': len(df),
        }

        print(f"\n{'='*50}")
        print("MODEL PERFORMANCE")
        print(f"{'='*50}")
        print(f"R² Score:  {metrics['r2']:.4f}")
        print(f"MAE:       ${metrics['mae']:,.0f}")
        print(f"MAPE:      {metrics['mape']:.2f}%")

        # Feature importance
        feature_importance = dict(zip(self.FEATURE_COLUMNS, self.model.feature_importances_))
        sorted_importance = sorted(feature_importance.items(), key=lambda x: x[1], reverse=True)

        print(f"\n{'='*50}")
        print("FEATURE IMPORTANCE (Top 10)")
        print(f"{'='*50}")
        for feat, imp in sorted_importance[:10]:
            print(f"  {feat}: {imp:.4f}")

        # Save metadata
        self.metadata = {
            'trained_at': datetime.now().isoformat(),
            'metrics': metrics,
            'feature_importance': feature_importance,
            'type_distribution': type_dist.to_dict(),
            'suburb_distribution': suburb_dist.to_dict(),
            'feature_columns': self.FEATURE_COLUMNS,
            'median_values': X.median().to_dict(),
        }

        # Save model and metadata
        self.save()

        return metrics

    def save(self):
        """Save model and metadata to disk."""
        if self.model is None:
            raise ValueError("No model to save. Train the model first.")

        joblib.dump(self.model, self.model_path)
        with open(self.metadata_path, 'w') as f:
            json.dump(self.metadata, f, indent=2, default=str)

        print(f"\nModel saved to: {self.model_path}")
        print(f"Metadata saved to: {self.metadata_path}")

    def load(self) -> bool:
        """Load model and metadata from disk."""
        if not self.model_path.exists():
            print(f"Model not found at {self.model_path}")
            return False

        try:
            self.model = joblib.load(self.model_path)
            if self.metadata_path.exists():
                with open(self.metadata_path, 'r') as f:
                    self.metadata = json.load(f)
            return True
        except Exception as e:
            print(f"Error loading model: {e}")
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
        """Predict property value given features."""
        if self.model is None:
            if not self.load():
                raise ValueError("Model not trained or loaded. Run train_model.py first.")

        # Consolidate property type
        prop_type_consolidated = self._consolidate_property_type(property_type)

        # Handle land size based on property type
        is_unit = prop_type_consolidated == 'unit'

        if is_unit:
            # For units: land size is not applicable
            effective_land_size = 0
            has_real_land_size = 0
        else:
            # For houses/townhouses: use provided land size or default
            if land_size is not None and land_size > 0:
                effective_land_size = land_size
                has_real_land_size = 1
            else:
                # No land size provided - use defaults
                effective_land_size = 450 if prop_type_consolidated == 'house' else 200
                has_real_land_size = 0

        # Default sale month to current
        if sale_month is None:
            sale_month = datetime.now().month

        # Default rolling average from metadata or fallback
        if rolling_avg_price_per_m2 is None:
            if self.metadata and 'median_values' in self.metadata:
                rolling_avg_price_per_m2 = self.metadata['median_values'].get('rolling_avg_price_per_m2', 10000)
            else:
                rolling_avg_price_per_m2 = 10000

        # Build feature vector
        features = {
            'land_size_numeric': effective_land_size,
            'beds': beds,
            'baths': bathrooms,
            'cars': car_spaces,
            'bedroom_to_land_ratio': 0 if is_unit else beds / max(effective_land_size, 1),
            'bathroom_to_bedroom_ratio': bathrooms / max(beds, 1),
            'suburb_castle_hill': 1 if 'CASTLE' in suburb.upper() else 0,
            'property_type_house': 1 if prop_type_consolidated == 'house' else 0,
            'property_type_unit': 1 if prop_type_consolidated == 'unit' else 0,
            'property_type_townhouse': 1 if prop_type_consolidated == 'townhouse' else 0,
            'is_house_large_land': 1 if prop_type_consolidated == 'house' and effective_land_size > 500 and has_real_land_size else 0,
            'has_real_land_size': has_real_land_size,
            'is_spring': 1 if sale_month in [9, 10, 11] else 0,
            'is_summer': 1 if sale_month in [12, 1, 2] else 0,
            'is_autumn': 1 if sale_month in [3, 4, 5] else 0,
            'is_winter': 1 if sale_month in [6, 7, 8] else 0,
            'years_since_sale': 0,  # Current prediction
            'rolling_avg_price_per_m2': rolling_avg_price_per_m2,
        }

        # Create DataFrame with correct column order
        X = pd.DataFrame([features])[self.FEATURE_COLUMNS]

        # Predict
        predicted_price = float(self.model.predict(X)[0])

        # Calculate confidence range (approximate based on MAPE)
        mape = self.metadata.get('metrics', {}).get('mape', 15)
        margin = predicted_price * (mape / 100)

        return {
            'predicted_price': round(predicted_price, -3),  # Round to nearest thousand
            'price_range_low': round(predicted_price - margin, -3),
            'price_range_high': round(predicted_price + margin, -3),
            'confidence_level': f"Based on MAPE: {mape:.1f}%",
            'input_features': {
                'land_size': land_size,
                'land_size_used': effective_land_size,
                'has_real_land_size': bool(has_real_land_size),
                'beds': beds,
                'bathrooms': bathrooms,
                'car_spaces': car_spaces,
                'suburb': suburb,
                'property_type': property_type,
                'property_type_consolidated': prop_type_consolidated,
            }
        }

    def predict_batch(self, properties: List[Dict]) -> List[Dict]:
        """Predict values for multiple properties."""
        results = []
        for prop in properties:
            try:
                result = self.predict(**prop)
                results.append(result)
            except Exception as e:
                results.append({'error': str(e), 'input': prop})
        return results

    def predict_all_listings(self, db_path: str, status: str = 'sale') -> Tuple[List[Dict], Dict]:
        """
        Predict values for all current listings in the database.

        Args:
            db_path: Path to the SQLite database
            status: 'sale' or 'sold' - which listings to predict

        Returns:
            Tuple of (predictions list, summary stats)
        """
        if self.model is None:
            if not self.load():
                raise ValueError("Model not trained or loaded. Run train_model.py first.")

        # Direct database access to avoid crawl4ai import issues
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row

        # Get listings for prediction
        query = '''
            SELECT h.property_id, p.suburb, h.beds, h.baths, h.cars, h.land_size, h.property_type
            FROM listing_history h
            JOIN properties p ON h.property_id = p.property_id
            WHERE h.status = ?
            AND h.date = (SELECT MAX(date) FROM listing_history WHERE property_id = h.property_id AND status = ?)
        '''
        listings = [dict(row) for row in conn.execute(query, (status, status)).fetchall()]

        predictions = []
        success_count = 0
        error_count = 0

        for listing in listings:
            try:
                # Parse land size
                land_size = self._parse_land_size(listing.get('land_size'))

                # Build prediction parameters
                params = {
                    'land_size': land_size,
                    'beds': int(listing.get('beds') or 3),
                    'bathrooms': int(listing.get('baths') or 2),
                    'car_spaces': int(listing.get('cars') or 1),
                    'suburb': listing.get('suburb', 'CASTLE HILL'),
                    'property_type': listing.get('property_type', 'house'),
                }

                result = self.predict(**params)

                predictions.append({
                    'property_id': listing['property_id'],
                    'predicted_price': int(result['predicted_price']),
                    'price_range_low': int(result['price_range_low']),
                    'price_range_high': int(result['price_range_high']),
                })
                success_count += 1

            except Exception as e:
                error_count += 1
                print(f"Error predicting {listing.get('property_id')}: {e}")

        # Save predictions to database
        model_version = self.metadata.get('trained_at', 'unknown')
        now = datetime.now().isoformat()

        cursor = conn.cursor()
        for pred in predictions:
            cursor.execute('''
                INSERT OR REPLACE INTO xgboost_predictions
                (property_id, predicted_price, price_range_low, price_range_high, predicted_at, model_version)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                pred['property_id'],
                pred['predicted_price'],
                pred.get('price_range_low'),
                pred.get('price_range_high'),
                now,
                model_version
            ))
        conn.commit()
        saved_count = len(predictions)
        conn.close()

        summary = {
            'total_listings': len(listings),
            'success_count': success_count,
            'error_count': error_count,
            'saved_count': saved_count,
            'model_version': model_version,
            'predicted_at': now,
        }

        return predictions, summary
