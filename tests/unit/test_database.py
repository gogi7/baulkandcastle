"""
Unit tests for database module.
"""

import pytest

from baulkandcastle.core.database import (
    get_connection,
    fetch_all,
    fetch_one,
    execute,
    table_exists,
    add_column_if_not_exists,
)
from baulkandcastle.exceptions import DatabaseError


class TestGetConnection:
    """Tests for get_connection context manager."""

    def test_connection_opens_and_closes(self, temp_db):
        with get_connection(temp_db) as conn:
            assert conn is not None
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            assert result is not None

    def test_dict_factory_enabled_by_default(self, temp_db):
        with get_connection(temp_db) as conn:
            conn.execute("CREATE TABLE test (id INTEGER, name TEXT)")
            conn.execute("INSERT INTO test VALUES (1, 'test')")
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM test")
            row = cursor.fetchone()
            assert isinstance(row, dict)
            assert row["id"] == 1
            assert row["name"] == "test"


class TestFetchAll:
    """Tests for fetch_all function."""

    def test_fetch_all_returns_list(self, temp_db):
        with get_connection(temp_db) as conn:
            results = fetch_all(conn, "SELECT * FROM properties")
            assert isinstance(results, list)

    def test_fetch_all_with_params(self, populated_db):
        with get_connection(populated_db) as conn:
            results = fetch_all(
                conn,
                "SELECT * FROM properties WHERE suburb = ?",
                ("CASTLE HILL",)
            )
            assert len(results) == 1
            assert results[0]["suburb"] == "CASTLE HILL"


class TestFetchOne:
    """Tests for fetch_one function."""

    def test_fetch_one_returns_dict(self, populated_db):
        with get_connection(populated_db) as conn:
            result = fetch_one(
                conn,
                "SELECT * FROM properties WHERE suburb = ?",
                ("CASTLE HILL",)
            )
            assert isinstance(result, dict)
            assert result["suburb"] == "CASTLE HILL"

    def test_fetch_one_returns_none_when_empty(self, temp_db):
        with get_connection(temp_db) as conn:
            result = fetch_one(
                conn,
                "SELECT * FROM properties WHERE property_id = ?",
                ("nonexistent",)
            )
            assert result is None


class TestExecute:
    """Tests for execute function."""

    def test_execute_insert(self, temp_db):
        with get_connection(temp_db) as conn:
            rowcount = execute(
                conn,
                "INSERT INTO properties (property_id, address, suburb) VALUES (?, ?, ?)",
                ("test-1", "123 Test St", "CASTLE HILL")
            )
            assert rowcount == 1

    def test_execute_update(self, populated_db):
        with get_connection(populated_db) as conn:
            rowcount = execute(
                conn,
                "UPDATE properties SET address = ? WHERE suburb = ?",
                ("Updated Address", "CASTLE HILL")
            )
            assert rowcount >= 1


class TestTableExists:
    """Tests for table_exists function."""

    def test_existing_table(self, temp_db):
        with get_connection(temp_db) as conn:
            assert table_exists(conn, "properties") is True
            assert table_exists(conn, "listing_history") is True

    def test_nonexistent_table(self, temp_db):
        with get_connection(temp_db) as conn:
            assert table_exists(conn, "nonexistent_table") is False


class TestAddColumnIfNotExists:
    """Tests for add_column_if_not_exists function."""

    def test_add_new_column(self, temp_db):
        with get_connection(temp_db) as conn:
            result = add_column_if_not_exists(
                conn, "properties", "new_column", "TEXT"
            )
            assert result is True

            # Verify column exists
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(properties)")
            columns = [row["name"] for row in cursor.fetchall()]
            assert "new_column" in columns

    def test_existing_column_returns_false(self, temp_db):
        with get_connection(temp_db) as conn:
            result = add_column_if_not_exists(
                conn, "properties", "address", "TEXT"
            )
            assert result is False
