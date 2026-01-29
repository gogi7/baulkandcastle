"""
Unit tests for property_types module.
"""

import pytest

from baulkandcastle.utils.property_types import (
    consolidate_property_type,
    is_unit_type,
    is_house_type,
    is_townhouse_type,
    get_default_land_size,
    PROPERTY_TYPE_MAP,
)


class TestConsolidatePropertyType:
    """Tests for consolidate_property_type function."""

    def test_house_types(self):
        assert consolidate_property_type("house") == "house"
        assert consolidate_property_type("free-standing") == "house"
        assert consolidate_property_type("duplex") == "house"
        assert consolidate_property_type("semi-detached") == "house"
        assert consolidate_property_type("terrace") == "house"
        assert consolidate_property_type("villa") == "house"

    def test_unit_types(self):
        assert consolidate_property_type("unit") == "unit"
        assert consolidate_property_type("apartment") == "unit"
        assert consolidate_property_type("apartment-unit-flat") == "unit"
        assert consolidate_property_type("studio") == "unit"
        assert consolidate_property_type("pent-house") == "unit"
        assert consolidate_property_type("flat") == "unit"

    def test_townhouse_types(self):
        assert consolidate_property_type("townhouse") == "townhouse"
        assert consolidate_property_type("town-house") == "townhouse"

    def test_other_types(self):
        assert consolidate_property_type("vacant-land") == "other"
        assert consolidate_property_type("land") == "other"
        assert consolidate_property_type("development-site") == "other"

    def test_case_insensitive(self):
        assert consolidate_property_type("HOUSE") == "house"
        assert consolidate_property_type("House") == "house"
        assert consolidate_property_type("APARTMENT") == "unit"

    def test_none_returns_other(self):
        assert consolidate_property_type(None) == "other"

    def test_empty_returns_other(self):
        assert consolidate_property_type("") == "other"

    def test_unknown_returns_other(self):
        assert consolidate_property_type("unknown-type") == "other"


class TestIsUnitType:
    """Tests for is_unit_type function."""

    def test_unit_types_return_true(self):
        assert is_unit_type("unit") is True
        assert is_unit_type("apartment") is True
        assert is_unit_type("apartment-unit-flat") is True
        assert is_unit_type("studio") is True

    def test_house_returns_false(self):
        assert is_unit_type("house") is False

    def test_townhouse_returns_false(self):
        assert is_unit_type("townhouse") is False

    def test_none_returns_false(self):
        assert is_unit_type(None) is False


class TestIsHouseType:
    """Tests for is_house_type function."""

    def test_house_types_return_true(self):
        assert is_house_type("house") is True
        assert is_house_type("free-standing") is True
        assert is_house_type("duplex") is True

    def test_unit_returns_false(self):
        assert is_house_type("apartment") is False

    def test_townhouse_returns_false(self):
        assert is_house_type("townhouse") is False

    def test_none_returns_false(self):
        assert is_house_type(None) is False


class TestIsTownhouseType:
    """Tests for is_townhouse_type function."""

    def test_townhouse_returns_true(self):
        assert is_townhouse_type("townhouse") is True
        assert is_townhouse_type("town-house") is True

    def test_house_returns_false(self):
        assert is_townhouse_type("house") is False

    def test_unit_returns_false(self):
        assert is_townhouse_type("apartment") is False


class TestGetDefaultLandSize:
    """Tests for get_default_land_size function."""

    def test_house_default(self):
        assert get_default_land_size("house") == 550.0

    def test_townhouse_default(self):
        assert get_default_land_size("townhouse") == 250.0

    def test_unit_default(self):
        assert get_default_land_size("unit") == 0.0
        assert get_default_land_size("apartment") == 0.0

    def test_other_default(self):
        assert get_default_land_size("other") == 400.0
        assert get_default_land_size(None) == 400.0
