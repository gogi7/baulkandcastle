"""
Unit tests for price_parser module.
"""

import pytest

from baulkandcastle.utils.price_parser import (
    extract_price_value,
    parse_price,
    format_price,
    format_price_range,
    calculate_price_per_sqm,
)


class TestExtractPriceValue:
    """Tests for extract_price_value function."""

    def test_standard_format(self):
        assert extract_price_value("$1,500,000") == 1500000

    def test_millions_shorthand(self):
        assert extract_price_value("$1.5M") == 1500000
        assert extract_price_value("$1.5m") == 1500000
        assert extract_price_value("$2M") == 2000000

    def test_thousands_shorthand(self):
        assert extract_price_value("$500K") == 500000
        assert extract_price_value("$500k") == 500000

    def test_no_dollar_sign(self):
        assert extract_price_value("1500000") == 1500000

    def test_price_range_returns_lower(self):
        assert extract_price_value("$1,500,000 - $1,700,000") == 1500000

    def test_auction_returns_none(self):
        assert extract_price_value("Auction") is None

    def test_contact_agent_returns_none(self):
        assert extract_price_value("Contact Agent") is None

    def test_empty_string(self):
        assert extract_price_value("") is None

    def test_none(self):
        assert extract_price_value(None) is None

    def test_small_number_ignored(self):
        # Numbers under 10000 should be ignored as they're not prices
        assert extract_price_value("$100") is None


class TestParsePrice:
    """Tests for parse_price function."""

    def test_single_price(self):
        low, high = parse_price("$1,500,000")
        assert low == 1500000
        assert high == 1500000

    def test_price_range_hyphen(self):
        low, high = parse_price("$1,500,000 - $1,700,000")
        assert low == 1500000
        assert high == 1700000

    def test_price_range_to(self):
        low, high = parse_price("$1.5M to $1.7M")
        assert low == 1500000
        assert high == 1700000

    def test_empty_returns_none(self):
        low, high = parse_price("")
        assert low is None
        assert high is None


class TestFormatPrice:
    """Tests for format_price function."""

    def test_standard_format(self):
        assert format_price(1500000) == "$1,500,000"

    def test_compact_millions(self):
        assert format_price(1500000, compact=True) == "$1.5M"
        assert format_price(2000000, compact=True) == "$2M"

    def test_compact_thousands(self):
        assert format_price(500000, compact=True) == "$500K"
        assert format_price(750000, compact=True) == "$750K"

    def test_none_returns_dash(self):
        assert format_price(None) == "-"


class TestFormatPriceRange:
    """Tests for format_price_range function."""

    def test_same_low_high(self):
        assert format_price_range(1500000, 1500000) == "$1,500,000"

    def test_different_low_high(self):
        result = format_price_range(1500000, 1700000)
        assert "$1,500,000" in result
        assert "$1,700,000" in result

    def test_compact_range(self):
        result = format_price_range(1500000, 1700000, compact=True)
        assert "$1.5M" in result
        assert "$1.7M" in result

    def test_none_values(self):
        assert format_price_range(None, None) == "-"


class TestCalculatePricePerSqm:
    """Tests for calculate_price_per_sqm function."""

    def test_numeric_land_size(self):
        result = calculate_price_per_sqm(1000000, 500.0)
        assert result == 2000.0

    def test_string_land_size(self):
        result = calculate_price_per_sqm(1000000, "500m²")
        assert result == 2000.0

    def test_zero_land_size(self):
        assert calculate_price_per_sqm(1000000, 0) is None

    def test_none_price(self):
        assert calculate_price_per_sqm(None, 500) is None

    def test_none_land_size(self):
        assert calculate_price_per_sqm(1000000, None) is None
