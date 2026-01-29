"""
Database Helper Functions

Provides context managers and helper functions for SQLite database operations.

Usage:
    from baulkandcastle.core.database import get_connection, fetch_all

    with get_connection() as conn:
        results = fetch_all(conn, "SELECT * FROM properties")
"""

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional, Tuple, Union

from baulkandcastle.config import get_config
from baulkandcastle.exceptions import DatabaseConnectionError, DatabaseError
from baulkandcastle.logging_config import get_logger

logger = get_logger(__name__)

# Type aliases
Row = Dict[str, Any]
Params = Union[Tuple, Dict[str, Any], None]


def dict_factory(cursor: sqlite3.Cursor, row: tuple) -> Dict[str, Any]:
    """Convert SQLite row to dictionary."""
    return {col[0]: row[idx] for idx, col in enumerate(cursor.description)}


@contextmanager
def get_connection(
    db_path: Optional[str] = None,
    as_dict: bool = True,
) -> Generator[sqlite3.Connection, None, None]:
    """Context manager for database connections.

    Args:
        db_path: Path to database file. Uses config default if not specified.
        as_dict: If True, rows are returned as dictionaries.

    Yields:
        SQLite connection object.

    Raises:
        DatabaseConnectionError: If unable to connect to the database.

    Usage:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM properties")
    """
    if db_path is None:
        db_path = get_config().database.path

    # Ensure parent directory exists
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    conn = None
    try:
        conn = sqlite3.connect(db_path)
        if as_dict:
            conn.row_factory = dict_factory
        else:
            conn.row_factory = sqlite3.Row
        logger.debug("Connected to database: %s", db_path)
        yield conn
    except sqlite3.Error as e:
        logger.error("Database connection error: %s", e)
        raise DatabaseConnectionError(f"Failed to connect to database: {e}") from e
    finally:
        if conn:
            conn.close()
            logger.debug("Closed database connection")


def fetch_all(
    conn: sqlite3.Connection,
    query: str,
    params: Params = None,
) -> List[Row]:
    """Execute a query and fetch all results.

    Args:
        conn: Database connection.
        query: SQL query string.
        params: Query parameters (tuple or dict).

    Returns:
        List of result rows as dictionaries.

    Raises:
        DatabaseError: If query execution fails.
    """
    try:
        cursor = conn.cursor()
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)
        return cursor.fetchall()
    except sqlite3.Error as e:
        logger.error("Query failed: %s - Error: %s", query[:100], e)
        raise DatabaseError(f"Query failed: {e}") from e


def fetch_one(
    conn: sqlite3.Connection,
    query: str,
    params: Params = None,
) -> Optional[Row]:
    """Execute a query and fetch one result.

    Args:
        conn: Database connection.
        query: SQL query string.
        params: Query parameters (tuple or dict).

    Returns:
        Single result row as dictionary, or None if no results.

    Raises:
        DatabaseError: If query execution fails.
    """
    try:
        cursor = conn.cursor()
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)
        return cursor.fetchone()
    except sqlite3.Error as e:
        logger.error("Query failed: %s - Error: %s", query[:100], e)
        raise DatabaseError(f"Query failed: {e}") from e


def execute(
    conn: sqlite3.Connection,
    query: str,
    params: Params = None,
    commit: bool = True,
) -> int:
    """Execute a query (INSERT, UPDATE, DELETE).

    Args:
        conn: Database connection.
        query: SQL query string.
        params: Query parameters (tuple or dict).
        commit: If True, commit the transaction.

    Returns:
        Number of rows affected.

    Raises:
        DatabaseError: If query execution fails.
    """
    try:
        cursor = conn.cursor()
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)
        if commit:
            conn.commit()
        return cursor.rowcount
    except sqlite3.Error as e:
        logger.error("Execute failed: %s - Error: %s", query[:100], e)
        raise DatabaseError(f"Execute failed: {e}") from e


def execute_many(
    conn: sqlite3.Connection,
    query: str,
    params_list: List[Params],
    commit: bool = True,
) -> int:
    """Execute a query multiple times with different parameters.

    Args:
        conn: Database connection.
        query: SQL query string.
        params_list: List of parameter tuples/dicts.
        commit: If True, commit the transaction.

    Returns:
        Total number of rows affected.

    Raises:
        DatabaseError: If query execution fails.
    """
    try:
        cursor = conn.cursor()
        cursor.executemany(query, params_list)
        if commit:
            conn.commit()
        return cursor.rowcount
    except sqlite3.Error as e:
        logger.error("Execute many failed: %s - Error: %s", query[:100], e)
        raise DatabaseError(f"Execute many failed: {e}") from e


def table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    """Check if a table exists in the database.

    Args:
        conn: Database connection.
        table_name: Name of the table to check.

    Returns:
        True if table exists, False otherwise.
    """
    result = fetch_one(
        conn,
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    )
    return result is not None


def get_table_info(conn: sqlite3.Connection, table_name: str) -> List[Row]:
    """Get column information for a table.

    Args:
        conn: Database connection.
        table_name: Name of the table.

    Returns:
        List of column info dictionaries.
    """
    return fetch_all(conn, f"PRAGMA table_info({table_name})")


def add_column_if_not_exists(
    conn: sqlite3.Connection,
    table_name: str,
    column_name: str,
    column_type: str,
    default: Optional[str] = None,
) -> bool:
    """Add a column to a table if it doesn't exist.

    Args:
        conn: Database connection.
        table_name: Name of the table.
        column_name: Name of the column to add.
        column_type: SQLite column type (TEXT, INTEGER, REAL, etc.).
        default: Default value for the column.

    Returns:
        True if column was added, False if it already existed.
    """
    columns = get_table_info(conn, table_name)
    column_names = [col["name"] for col in columns]

    if column_name in column_names:
        return False

    default_clause = f" DEFAULT {default}" if default is not None else ""
    query = f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}{default_clause}"

    try:
        execute(conn, query)
        logger.info("Added column %s to table %s", column_name, table_name)
        return True
    except DatabaseError:
        return False
