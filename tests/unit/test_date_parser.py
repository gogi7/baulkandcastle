"""
Unit tests for date_parser module.
"""

from datetime import datetime

import pytest

from baulkandcastle.utils.date_parser import (
    parse_date,
    parse_to_iso,
    parse_snapshot_date,
    format_date,
    days_between,
    get_season,
    years_since,
)


class TestParseDate:
    """Tests for parse_date function."""

    def test_iso_format(self):
        result = parse_date("2024-01-15")
        assert result == datetime(2024, 1, 15)

    def test_iso_with_time(self):
        result = parse_date("2024-01-15T10:30:00")
        assert result == datetime(2024, 1, 15)

    def test_australian_format(self):
        result = parse_date("15/01/2024")
        assert result == datetime(2024, 1, 15)

    def test_domain_format(self):
        result = parse_date("15 Jan 2024")
        assert result == datetime(2024, 1, 15)

    def test_full_month(self):
        result = parse_date("15 January 2024")
        assert result == datetime(2024, 1, 15)

    def test_month_year(self):
        result = parse_date("Jan 2024")
        assert result.year == 2024
        assert result.month == 1

    def test_empty_string(self):
        assert parse_date("") is None

    def test_none(self):
        assert parse_date(None) is None

    def test_invalid_format(self):
        assert parse_date("not a date") is None


class TestParseToIso:
    """Tests for parse_to_iso function."""

    def test_domain_format_to_iso(self):
        assert parse_to_iso("15 Jan 2024") == "2024-01-15"

    def test_australian_format_to_iso(self):
        assert parse_to_iso("15/01/2024") == "2024-01-15"

    def test_already_iso(self):
        assert parse_to_iso("2024-01-15") == "2024-01-15"

    def test_none_returns_none(self):
        assert parse_to_iso(None) is None


class TestParseSnapshotDate:
    """Tests for parse_snapshot_date function."""

    def test_estimated_prefix(self):
        result = parse_snapshot_date("Estimated Jan 2024")
        assert result is not None
        assert "2024-01" in result

    def test_as_at_prefix(self):
        result = parse_snapshot_date("As at 15 Jan 2024")
        assert result == "2024-01-15"

    def test_empty_string(self):
        assert parse_snapshot_date("") is None

    def test_none(self):
        assert parse_snapshot_date(None) is None


class TestFormatDate:
    """Tests for format_date function."""

    def test_default_format(self):
        dt = datetime(2024, 1, 15)
        assert format_date(dt) == "15 Jan 2024"

    def test_custom_format(self):
        dt = datetime(2024, 1, 15)
        assert format_date(dt, "%Y-%m-%d") == "2024-01-15"

    def test_none_returns_empty(self):
        assert format_date(None) == ""


class TestDaysBetween:
    """Tests for days_between function."""

    def test_datetime_inputs(self):
        d1 = datetime(2024, 1, 1)
        d2 = datetime(2024, 1, 11)
        assert days_between(d1, d2) == 10

    def test_string_inputs(self):
        assert days_between("2024-01-01", "2024-01-11") == 10

    def test_order_independent(self):
        assert days_between("2024-01-11", "2024-01-01") == 10

    def test_invalid_date_returns_none(self):
        assert days_between("invalid", "2024-01-01") is None


class TestGetSeason:
    """Tests for get_season function."""

    def test_summer(self):
        assert get_season(datetime(2024, 12, 15)) == "summer"
        assert get_season(datetime(2024, 1, 15)) == "summer"
        assert get_season(datetime(2024, 2, 15)) == "summer"

    def test_autumn(self):
        assert get_season(datetime(2024, 3, 15)) == "autumn"
        assert get_season(datetime(2024, 4, 15)) == "autumn"
        assert get_season(datetime(2024, 5, 15)) == "autumn"

    def test_winter(self):
        assert get_season(datetime(2024, 6, 15)) == "winter"
        assert get_season(datetime(2024, 7, 15)) == "winter"
        assert get_season(datetime(2024, 8, 15)) == "winter"

    def test_spring(self):
        assert get_season(datetime(2024, 9, 15)) == "spring"
        assert get_season(datetime(2024, 10, 15)) == "spring"
        assert get_season(datetime(2024, 11, 15)) == "spring"


class TestYearsSince:
    """Tests for years_since function."""

    def test_one_year_ago(self):
        reference = datetime(2024, 1, 15)
        result = years_since("2023-01-15", reference)
        assert result is not None
        assert abs(result - 1.0) < 0.01

    def test_invalid_date(self):
        assert years_since("invalid") is None
