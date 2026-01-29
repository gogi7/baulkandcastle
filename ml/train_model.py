#!/usr/bin/env python
"""
Train the Property Valuation Model

Usage:
    python ml/train_model.py
    python ml/train_model.py --db path/to/database.db
"""

import argparse
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from ml.valuation_predictor import PropertyValuationModel


def main():
    parser = argparse.ArgumentParser(
        description="Train the XGBoost property valuation model"
    )
    parser.add_argument(
        "--db",
        type=str,
        default="baulkandcastle_properties.db",
        help="Path to SQLite database (default: baulkandcastle_properties.db)"
    )
    parser.add_argument(
        "--test-size",
        type=float,
        default=0.2,
        help="Fraction of data for testing (default: 0.2)"
    )

    args = parser.parse_args()

    # Resolve database path
    db_path = Path(args.db)
    if not db_path.is_absolute():
        # Look in project root
        project_root = Path(__file__).parent.parent
        db_path = project_root / args.db

    if not db_path.exists():
        print(f"Error: Database not found at {db_path}")
        sys.exit(1)

    print("=" * 60)
    print("PROPERTY VALUATION MODEL TRAINING")
    print("Baulkham Hills & Castle Hill")
    print("=" * 60)
    print(f"\nDatabase: {db_path}")

    # Train model
    model = PropertyValuationModel()
    metrics = model.train(str(db_path), test_size=args.test_size)

    # Summary
    print(f"\n{'=' * 60}")
    print("TRAINING COMPLETE")
    print(f"{'=' * 60}")

    # Quality check
    if metrics['r2'] >= 0.70:
        print("Model quality: GOOD (R² >= 0.70)")
    elif metrics['r2'] >= 0.50:
        print("Model quality: ACCEPTABLE (R² >= 0.50)")
    else:
        print("Model quality: NEEDS IMPROVEMENT (R² < 0.50)")

    if metrics['mape'] <= 15:
        print("Price accuracy: GOOD (MAPE <= 15%)")
    elif metrics['mape'] <= 20:
        print("Price accuracy: ACCEPTABLE (MAPE <= 20%)")
    else:
        print("Price accuracy: NEEDS IMPROVEMENT (MAPE > 20%)")

    print(f"\nModel ready for predictions!")


if __name__ == "__main__":
    main()
