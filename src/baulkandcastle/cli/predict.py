#!/usr/bin/env python
"""
CLI for property value predictions.

Usage:
    python -m baulkandcastle.cli.predict --beds 4 --property_type house --suburb "Castle Hill"
    python -m baulkandcastle.cli.predict --beds 3 --baths 2 --cars 2 --land_size 600
"""

import argparse
import json
import sys

from baulkandcastle.config import get_config
from baulkandcastle.logging_config import setup_logging, get_logger
from baulkandcastle.utils.price_parser import format_price


def main():
    """Main entry point for the prediction CLI."""
    parser = argparse.ArgumentParser(
        description="Predict property values using the trained ML model",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python -m baulkandcastle.cli.predict --beds 4 --property_type house
    python -m baulkandcastle.cli.predict --beds 3 --baths 2 --cars 2 --land_size 600 --suburb "CASTLE HILL"
    python -m baulkandcastle.cli.predict --beds 2 --property_type unit --json
        """,
    )
    parser.add_argument("--beds", type=int, required=True, help="Number of bedrooms")
    parser.add_argument("--baths", type=int, default=2, help="Number of bathrooms (default: 2)")
    parser.add_argument("--cars", type=int, default=2, help="Number of car spaces (default: 2)")
    parser.add_argument("--land_size", type=float, default=None, help="Land size in m² (optional)")
    parser.add_argument(
        "--property_type",
        type=str,
        default="house",
        choices=["house", "unit", "townhouse", "other"],
        help="Property type (default: house)",
    )
    parser.add_argument(
        "--suburb",
        type=str,
        default="CASTLE HILL",
        help="Suburb (default: CASTLE HILL)",
    )
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="WARNING",
        help="Set log level (default: WARNING)",
    )

    args = parser.parse_args()

    # Setup logging
    setup_logging(level=args.log_level)
    logger = get_logger(__name__)

    try:
        from baulkandcastle.ml.valuation_predictor import PropertyValuationModel

        model = PropertyValuationModel()
        if not model.load():
            logger.error("Model not found. Run 'python -m baulkandcastle.cli.train_model' first.")
            sys.exit(1)

        # Build prediction params
        params = {
            "beds": args.beds,
            "bathrooms": args.baths,
            "car_spaces": args.cars,
            "suburb": args.suburb.upper(),
            "property_type": args.property_type,
        }
        if args.land_size and args.land_size > 0:
            params["land_size"] = args.land_size

        # Make prediction
        result = model.predict(**params)

        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print("\n" + "=" * 50)
            print("Property Value Prediction")
            print("=" * 50)
            print(f"\nInput:")
            print(f"  Bedrooms: {args.beds}")
            print(f"  Bathrooms: {args.baths}")
            print(f"  Car Spaces: {args.cars}")
            if args.land_size:
                print(f"  Land Size: {args.land_size}m²")
            print(f"  Property Type: {args.property_type}")
            print(f"  Suburb: {args.suburb}")
            print(f"\nPrediction:")
            print(f"  Estimated Value: {format_price(result.get('predicted_price'))}")
            print(f"  Range: {format_price(result.get('price_range_low'))} - {format_price(result.get('price_range_high'))}")
            if result.get("confidence_note"):
                print(f"  Note: {result['confidence_note']}")
            print()

    except Exception as e:
        logger.error("Prediction failed: %s", e, exc_info=True)
        if args.json:
            print(json.dumps({"error": str(e)}))
        else:
            print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
