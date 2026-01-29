#!/usr/bin/env python
"""
CLI for Domain estimate extraction.

This is a wrapper that calls the original domain_estimator_helper script.
Eventually the estimator logic should be moved into the package.

Usage:
    python -m baulkandcastle.cli.estimate_for_sale --batch
    python -m baulkandcastle.cli.estimate_for_sale --stats
"""

import argparse
import sys
from pathlib import Path


def main():
    """Main entry point for the Domain estimator CLI."""
    parser = argparse.ArgumentParser(
        description="Domain Property Estimate Extractor",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python -m baulkandcastle.cli.estimate_for_sale --batch
    python -m baulkandcastle.cli.estimate_for_sale --batch --mode today-new
    python -m baulkandcastle.cli.estimate_for_sale --stats
    python -m baulkandcastle.cli.estimate_for_sale --list-urls
        """,
    )
    parser.add_argument(
        "--batch",
        action="store_true",
        help="Run batch estimation",
    )
    parser.add_argument(
        "--mode",
        choices=["new-only", "today-new", "all"],
        default="new-only",
        help="Estimation mode (default: new-only)",
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Show estimation coverage stats",
    )
    parser.add_argument(
        "--list-urls",
        action="store_true",
        help="List URLs to scrape",
    )

    args = parser.parse_args()

    # Find the original script
    project_root = Path(__file__).parent.parent.parent.parent
    estimator_path = project_root / "domain_estimator_helper.py"

    if not estimator_path.exists():
        print(f"Error: Original estimator not found at {estimator_path}")
        print("The estimator hasn't been migrated yet.")
        sys.exit(1)

    # Build command
    cmd_args = [sys.executable, str(estimator_path)]
    if args.batch:
        cmd_args.append("--batch")
        cmd_args.extend(["--mode", args.mode])
    if args.stats:
        cmd_args.append("--stats")
    if args.list_urls:
        cmd_args.append("--list-urls")

    # Execute
    import subprocess
    result = subprocess.run(cmd_args)
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
