#!/usr/bin/env python
"""
Property Value Prediction CLI

Usage:
    # House with known land size
    python ml/predict_property_value.py 600 4 --bathrooms 2 --car_spaces 2 --suburb "CASTLE HILL" --property_type house

    # Unit (land size not needed)
    python ml/predict_property_value.py 2 --bathrooms 1 --suburb "BAULKHAM HILLS" --property_type unit

    # House without land size (will use default)
    python ml/predict_property_value.py 4 --bathrooms 2 --suburb "CASTLE HILL" --property_type house

    # JSON input
    python ml/predict_property_value.py --json '{"beds": 4, "bathrooms": 2, "property_type": "house"}'
"""

import argparse
import json
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from ml.valuation_predictor import PropertyValuationModel


def main():
    parser = argparse.ArgumentParser(
        description="Predict property value using the trained XGBoost model"
    )

    # Positional arguments - now more flexible
    parser.add_argument(
        "arg1",
        type=float,
        nargs='?',
        help="Land size (m²) if 2 args provided, OR beds if 1 arg provided"
    )
    parser.add_argument(
        "arg2",
        type=int,
        nargs='?',
        help="Number of bedrooms (when land_size is provided)"
    )

    # Optional arguments
    parser.add_argument(
        "--land_size",
        type=float,
        help="Land size in m² (optional for units, recommended for houses)"
    )
    parser.add_argument(
        "--beds",
        type=int,
        help="Number of bedrooms"
    )
    parser.add_argument(
        "--bathrooms",
        type=int,
        default=2,
        help="Number of bathrooms (default: 2)"
    )
    parser.add_argument(
        "--car_spaces",
        type=int,
        default=1,
        help="Number of car spaces (default: 1)"
    )
    parser.add_argument(
        "--suburb",
        type=str,
        default="CASTLE HILL",
        choices=["CASTLE HILL", "BAULKHAM HILLS"],
        help="Suburb (default: CASTLE HILL)"
    )
    parser.add_argument(
        "--property_type",
        type=str,
        default="house",
        choices=["house", "unit", "townhouse", "apartment", "villa", "duplex", "terrace"],
        help="Property type (default: house)"
    )
    parser.add_argument(
        "--json",
        type=str,
        help="JSON string with all parameters"
    )
    parser.add_argument(
        "--output",
        type=str,
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)"
    )

    args = parser.parse_args()

    # Parse input - multiple ways to specify
    if args.json:
        try:
            params = json.loads(args.json)
        except json.JSONDecodeError as e:
            print(f"Error parsing JSON: {e}")
            sys.exit(1)
    elif args.arg1 is not None and args.arg2 is not None:
        # Two positional args: land_size beds
        params = {
            'land_size': args.arg1,
            'beds': args.arg2,
            'bathrooms': args.bathrooms,
            'car_spaces': args.car_spaces,
            'suburb': args.suburb,
            'property_type': args.property_type,
        }
    elif args.arg1 is not None and args.arg2 is None:
        # One positional arg: beds only (land_size optional)
        params = {
            'beds': int(args.arg1),
            'bathrooms': args.bathrooms,
            'car_spaces': args.car_spaces,
            'suburb': args.suburb,
            'property_type': args.property_type,
        }
        if args.land_size:
            params['land_size'] = args.land_size
    elif args.beds is not None:
        # Named arguments only
        params = {
            'beds': args.beds,
            'bathrooms': args.bathrooms,
            'car_spaces': args.car_spaces,
            'suburb': args.suburb,
            'property_type': args.property_type,
        }
        if args.land_size:
            params['land_size'] = args.land_size
    else:
        parser.print_help()
        print("\n" + "=" * 50)
        print("USAGE EXAMPLES:")
        print("=" * 50)
        print("\n# House with known land size:")
        print("  python ml/predict_property_value.py 600 4 --property_type house")
        print("\n# Unit (no land size needed):")
        print("  python ml/predict_property_value.py 2 --property_type unit")
        print("\n# House without land size:")
        print("  python ml/predict_property_value.py 4 --property_type house")
        print("\n# Using named arguments:")
        print("  python ml/predict_property_value.py --beds 3 --bathrooms 2 --property_type townhouse")
        sys.exit(1)

    # Load model and predict
    model = PropertyValuationModel()
    if not model.load():
        print("Error: Model not found. Run 'python ml/train_model.py' first.")
        sys.exit(1)

    try:
        result = model.predict(**params)
    except Exception as e:
        print(f"Prediction error: {e}")
        sys.exit(1)

    # Output
    if args.output == "json":
        print(json.dumps(result, indent=2))
    else:
        inputs = result['input_features']
        print("\n" + "=" * 50)
        print("PROPERTY VALUATION PREDICTION")
        print("=" * 50)
        print(f"\nInput:")
        print(f"  Suburb:        {inputs['suburb']}")
        print(f"  Property Type: {inputs['property_type']} -> {inputs['property_type_consolidated']}")

        # Show land size info based on property type
        if inputs['property_type_consolidated'] == 'unit':
            print(f"  Land Size:     N/A (unit - strata title)")
        elif inputs['has_real_land_size']:
            print(f"  Land Size:     {inputs['land_size_used']}m² (provided)")
        else:
            print(f"  Land Size:     {inputs['land_size_used']}m² (estimated - no data provided)")

        print(f"  Bedrooms:      {inputs['beds']}")
        print(f"  Bathrooms:     {inputs['bathrooms']}")
        print(f"  Car Spaces:    {inputs['car_spaces']}")

        print(f"\nPredicted Value:")
        print(f"  Estimated Price: ${result['predicted_price']:,.0f}")
        print(f"  Price Range:     ${result['price_range_low']:,.0f} - ${result['price_range_high']:,.0f}")
        print(f"  {result['confidence_level']}")
        print("=" * 50)


if __name__ == "__main__":
    main()
