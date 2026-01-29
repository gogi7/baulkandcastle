#!/usr/bin/env python
"""
CLI for training the property valuation model.

Usage:
    python -m baulkandcastle.cli.train_model
    python -m baulkandcastle.cli.train_model --min-samples 50
"""

import argparse
import sys

from baulkandcastle.config import get_config
from baulkandcastle.logging_config import setup_logging, get_logger


def main():
    """Main entry point for model training CLI."""
    parser = argparse.ArgumentParser(
        description="Train the property valuation ML model",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python -m baulkandcastle.cli.train_model
    python -m baulkandcastle.cli.train_model --min-samples 100
    python -m baulkandcastle.cli.train_model --db-path custom.db
        """,
    )
    parser.add_argument(
        "--db-path",
        type=str,
        default=None,
        help="Path to database (default: from config)",
    )
    parser.add_argument(
        "--min-samples",
        type=int,
        default=20,
        help="Minimum samples required for training (default: 20)",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Set log level (default: INFO)",
    )

    args = parser.parse_args()

    # Setup logging
    setup_logging(level=args.log_level)
    logger = get_logger(__name__)

    config = get_config()
    db_path = args.db_path or config.database.path

    logger.info("Starting model training")
    logger.info("Database: %s", db_path)
    logger.info("Model directory: %s", config.ml.model_dir)

    try:
        from baulkandcastle.ml.valuation_predictor import PropertyValuationModel

        model = PropertyValuationModel()
        success = model.train(db_path=db_path, min_samples=args.min_samples)

        if success:
            logger.info("Model training completed successfully")
            logger.info("Model saved to: %s", config.ml.model_path)

            # Print metrics
            metrics = model.metadata.get("metrics", {})
            if metrics:
                print("\nModel Performance:")
                print(f"  R² Score: {metrics.get('r2', 0):.4f}")
                print(f"  MAE: ${metrics.get('mae', 0):,.0f}")
                print(f"  MAPE: {metrics.get('mape', 0):.2%}")
                print(f"  Training samples: {metrics.get('train_size', 0)}")
                print(f"  Test samples: {metrics.get('test_size', 0)}")
        else:
            logger.error("Model training failed")
            sys.exit(1)

    except Exception as e:
        logger.error("Training error: %s", e, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
