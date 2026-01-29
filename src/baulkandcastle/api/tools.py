"""
Tool Management Module

Provides functionality for managing and executing Python tools (scrapers, ML scripts, etc.)
with execution history tracking and status monitoring.
"""

import json
import os
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from baulkandcastle.core.database import (
    execute,
    fetch_all,
    fetch_one,
    get_connection,
    table_exists,
)
from baulkandcastle.logging_config import get_logger

logger = get_logger(__name__)

# Thread pool for running tools (max 2 concurrent)
_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="tool_worker")

# Track running processes by execution_id
_running_processes: Dict[int, subprocess.Popen] = {}
_process_lock = threading.Lock()

# Get project root directory (baulkandcastle folder)
# __file__ = src/baulkandcastle/api/tools.py
# .parent = src/baulkandcastle/api
# .parent.parent = src/baulkandcastle
# .parent.parent.parent = src
# .parent.parent.parent.parent = baulkandcastle (project root)
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent

# Virtual environment Python path (use this if it exists, otherwise fall back to system python)
VENV_PYTHON = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"
PYTHON_CMD = str(VENV_PYTHON) if VENV_PYTHON.exists() else "python"


# Tool definitions with metadata and flag schemas
TOOL_DEFINITIONS = {
    "scraper": {
        "id": "scraper",
        "name": "Domain Scraper",
        "description": "Scrape property listings from Domain.com.au for Baulkham Hills and Castle Hill",
        "category": "Data Collection",
        "script": "baulkandcastle_scraper.py",
        "flags": [
            {
                "name": "--mode",
                "type": "select",
                "options": ["full", "daily", "reports-only"],
                "description": "full = all pages, daily = configurable quick scan, reports-only = no scraping",
                "default": "full",
            },
            {
                "name": "--sale-pages",
                "type": "number",
                "description": "Number of for-sale pages to scrape (0=all, daily mode default: 1)",
                "default": 0,
            },
            {
                "name": "--sold-pages",
                "type": "number",
                "description": "Number of sold pages to scrape (full default: 30, daily default: 1)",
                "default": 30,
            },
            {
                "name": "--accuracy-report",
                "type": "boolean",
                "description": "Show prediction accuracy comparison report",
                "default": False,
            },
            {
                "name": "--update-catchment",
                "type": "boolean",
                "description": "Scrape Excelsior catchment and update property flags only",
                "default": False,
            },
            {
                "name": "--show-console",
                "type": "boolean",
                "description": "Open a visible command window (Windows only)",
                "default": False,
            },
        ],
    },
    "domain-estimator": {
        "id": "domain-estimator",
        "name": "Domain Estimator",
        "description": "Extract Domain.com.au property value estimates using browser automation (for-sale properties only)",
        "category": "Data Collection",
        "script": "domain_estimator_helper.py",
        "flags": [
            {
                "name": "--batch",
                "type": "boolean",
                "description": "Batch scrape for-sale properties (required to run)",
                "default": True,
            },
            {
                "name": "--mode",
                "type": "select",
                "options": ["new-only", "today-new", "all"],
                "description": "new-only = unestimated properties (default), today-new = today's new listings, all = re-estimate all",
                "default": "new-only",
            },
            {
                "name": "--limit",
                "type": "number",
                "description": "Limit number of properties to process",
                "default": None,
            },
            {
                "name": "--suburb",
                "type": "select",
                "options": ["", "CASTLE HILL", "BAULKHAM HILLS"],
                "description": "Filter by suburb (empty = all suburbs)",
                "default": "",
            },
            {
                "name": "--delay",
                "type": "number",
                "description": "Delay between requests in seconds (default: 3)",
                "default": 3.0,
            },
            {
                "name": "--stats",
                "type": "boolean",
                "description": "Show estimate coverage statistics only (no scraping)",
                "default": False,
            },
            {
                "name": "--show-console",
                "type": "boolean",
                "description": "Open a visible command window (Windows only)",
                "default": False,
            },
        ],
    },
    "train-model": {
        "id": "train-model",
        "name": "Train ML Model",
        "description": "Train the XGBoost property valuation model using sold property data",
        "category": "Machine Learning",
        "script": "ml/train_model.py",
        "flags": [
            {
                "name": "--db",
                "type": "string",
                "description": "Path to SQLite database file",
                "default": None,
            },
            {
                "name": "--test-size",
                "type": "number",
                "description": "Test set size ratio (0.0-1.0)",
                "default": 0.2,
            },
            {
                "name": "--show-console",
                "type": "boolean",
                "description": "Open a visible command window (Windows only)",
                "default": False,
            },
        ],
    },
    "ml-batch-estimates": {
        "id": "ml-batch-estimates",
        "name": "ML Batch Estimates",
        "description": "Generate XGBoost predictions for all current for-sale properties",
        "category": "Machine Learning",
        "script": "ml/estimate_for_sale.py",
        "flags": [
            {
                "name": "--db",
                "type": "string",
                "description": "Path to SQLite database file",
                "default": None,
            },
            {
                "name": "--show-console",
                "type": "boolean",
                "description": "Open a visible command window (Windows only)",
                "default": False,
            },
        ],
    },
}


def init_tools_tables() -> None:
    """Initialize the tool_executions table in the database."""
    with get_connection() as conn:
        if not table_exists(conn, "tool_executions"):
            execute(
                conn,
                """
                CREATE TABLE tool_executions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tool_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    flags TEXT,
                    started_at TEXT,
                    completed_at TEXT,
                    exit_code INTEGER,
                    stdout TEXT,
                    stderr TEXT,
                    summary TEXT,
                    summary_json TEXT,
                    created_at TEXT NOT NULL
                )
                """,
            )
            logger.info("Created tool_executions table")
        else:
            # Add summary_json column if it doesn't exist (for existing databases)
            try:
                execute(conn, "ALTER TABLE tool_executions ADD COLUMN summary_json TEXT")
                logger.info("Added summary_json column to tool_executions")
            except Exception:
                pass  # Column already exists

    # Clean up any stale executions from previous server runs
    cleanup_stale_executions()


def cleanup_stale_executions() -> int:
    """Mark any 'running' or 'pending' executions as 'failed'.

    Called on server startup to clean up executions that were interrupted
    by a server restart or crash.

    Returns:
        Number of executions cleaned up
    """
    with get_connection() as conn:
        # Find stale executions
        stale = fetch_all(
            conn,
            """
            SELECT id, tool_id FROM tool_executions
            WHERE status IN ('running', 'pending')
            """,
        )

        if not stale:
            return 0

        # Mark them as failed
        now = datetime.now().isoformat()
        execute(
            conn,
            """
            UPDATE tool_executions
            SET status = 'failed',
                completed_at = ?,
                summary = 'Interrupted by server restart'
            WHERE status IN ('running', 'pending')
            """,
            (now,),
        )

        for exec in stale:
            logger.warning(
                "Cleaned up stale execution #%d for %s",
                exec["id"],
                exec["tool_id"],
            )

        logger.info("Cleaned up %d stale executions", len(stale))
        return len(stale)


def get_tool_definitions() -> List[Dict[str, Any]]:
    """Get all tool definitions with last run information."""
    tools = []

    with get_connection() as conn:
        for tool_id, tool in TOOL_DEFINITIONS.items():
            # Get last execution for this tool
            last_run = fetch_one(
                conn,
                """
                SELECT id, status, started_at, completed_at, summary
                FROM tool_executions
                WHERE tool_id = ?
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (tool_id,),
            )

            tool_data = {**tool}
            if last_run:
                tool_data["last_run"] = {
                    "execution_id": last_run["id"],
                    "status": last_run["status"],
                    "started_at": last_run["started_at"],
                    "completed_at": last_run["completed_at"],
                    "summary": last_run["summary"],
                }
            else:
                tool_data["last_run"] = None

            tools.append(tool_data)

    return tools


def get_execution_history(limit: int = 20, tool_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Get execution history, optionally filtered by tool_id."""
    with get_connection() as conn:
        if tool_id:
            executions = fetch_all(
                conn,
                """
                SELECT id, tool_id, status, flags, started_at, completed_at,
                       exit_code, summary, created_at
                FROM tool_executions
                WHERE tool_id = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (tool_id, limit),
            )
        else:
            executions = fetch_all(
                conn,
                """
                SELECT id, tool_id, status, flags, started_at, completed_at,
                       exit_code, summary, created_at
                FROM tool_executions
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            )

    # Add tool name to each execution
    for execution in executions:
        tool_def = TOOL_DEFINITIONS.get(execution["tool_id"], {})
        execution["tool_name"] = tool_def.get("name", execution["tool_id"])
        if execution["flags"]:
            execution["flags"] = json.loads(execution["flags"])

    return executions


def get_execution(execution_id: int) -> Optional[Dict[str, Any]]:
    """Get a specific execution by ID."""
    with get_connection() as conn:
        execution = fetch_one(
            conn,
            """
            SELECT id, tool_id, status, flags, started_at, completed_at,
                   exit_code, stdout, stderr, summary, summary_json, created_at
            FROM tool_executions
            WHERE id = ?
            """,
            (execution_id,),
        )

    if execution:
        tool_def = TOOL_DEFINITIONS.get(execution["tool_id"], {})
        execution["tool_name"] = tool_def.get("name", execution["tool_id"])
        if execution["flags"]:
            execution["flags"] = json.loads(execution["flags"])
        # Parse summary_json if present
        if execution.get("summary_json"):
            try:
                execution["summary_json"] = json.loads(execution["summary_json"])
            except json.JSONDecodeError:
                execution["summary_json"] = None

    return execution


def start_tool_execution(tool_id: str, flags: Optional[Dict[str, Any]] = None) -> int:
    """Start a tool execution in the background.

    Args:
        tool_id: The tool identifier
        flags: Dictionary of flag names to values

    Returns:
        The execution ID

    Raises:
        ValueError: If tool_id is invalid
    """
    if tool_id not in TOOL_DEFINITIONS:
        raise ValueError(f"Unknown tool: {tool_id}")

    # Check if tool is already running
    with get_connection() as conn:
        running = fetch_one(
            conn,
            """
            SELECT id FROM tool_executions
            WHERE tool_id = ? AND status = 'running'
            """,
            (tool_id,),
        )
        if running:
            raise ValueError(f"Tool {tool_id} is already running (execution #{running['id']})")

    # Create execution record
    now = datetime.now().isoformat()
    flags_json = json.dumps(flags) if flags else None

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO tool_executions (tool_id, status, flags, created_at)
            VALUES (?, 'pending', ?, ?)
            """,
            (tool_id, flags_json, now),
        )
        conn.commit()
        execution_id = cursor.lastrowid

    # Submit to thread pool
    _executor.submit(_run_tool, execution_id, tool_id, flags)

    logger.info("Started tool execution #%d for %s", execution_id, tool_id)
    return execution_id


def cancel_execution(execution_id: int) -> bool:
    """Cancel a running execution.

    Args:
        execution_id: The execution ID to cancel

    Returns:
        True if cancelled, False if not running
    """
    with _process_lock:
        process = _running_processes.get(execution_id)
        if process and process.poll() is None:
            process.terminate()
            logger.info("Terminated execution #%d", execution_id)

            # Update status
            with get_connection() as conn:
                execute(
                    conn,
                    """
                    UPDATE tool_executions
                    SET status = 'cancelled', completed_at = ?
                    WHERE id = ?
                    """,
                    (datetime.now().isoformat(), execution_id),
                )
            return True

    return False


def _run_tool(execution_id: int, tool_id: str, flags: Optional[Dict[str, Any]]) -> None:
    """Execute a tool in a subprocess (runs in thread pool).

    Uses a finally block to guarantee status is always updated, preventing
    infinite spinner bugs in the frontend.
    """
    tool = TOOL_DEFINITIONS[tool_id]
    script_path = PROJECT_ROOT / tool["script"]

    # Initialize final state variables - guaranteed to be set before finally
    final_status = "failed"
    final_exit_code: Optional[int] = None
    final_stdout = ""
    final_stderr = ""
    final_summary = "Execution failed unexpectedly"
    final_summary_json: Optional[str] = None

    # Extract show-console flag (not passed to script)
    show_console = flags.get("--show-console", False) if flags else False

    # Build command
    cmd = [PYTHON_CMD, str(script_path)]

    # Special handling for scraper mode flag
    if tool_id == "scraper" and flags:
        mode = flags.get("--mode", "full")
        if mode == "daily":
            cmd.append("--daily")
        elif mode == "reports-only":
            cmd.append("--reports-only")
        # For "full" mode, no flag needed (default behavior)

        # Add other flags (excluding --mode and --show-console)
        for flag_def in tool.get("flags", []):
            flag_name = flag_def["name"]
            if flag_name in ("--mode", "--show-console"):
                continue  # Already handled or not a script flag

            flag_type = flag_def["type"]
            value = flags.get(flag_name)

            if value is None:
                continue

            if flag_type == "boolean":
                if value:
                    cmd.append(flag_name)
            elif flag_type in ("string", "number", "select"):
                if value == "":
                    continue
                cmd.extend([flag_name, str(value)])
    elif flags:
        for flag_def in tool.get("flags", []):
            flag_name = flag_def["name"]
            if flag_name == "--show-console":
                continue  # Not a script flag

            flag_type = flag_def["type"]
            value = flags.get(flag_name)

            if value is None:
                continue

            if flag_type == "boolean":
                if value:
                    cmd.append(flag_name)
            elif flag_type in ("string", "number", "select"):
                # Skip empty strings for select/string types
                if value == "":
                    continue
                cmd.extend([flag_name, str(value)])

    # Update status to running
    started_at = datetime.now().isoformat()
    with get_connection() as conn:
        execute(
            conn,
            """
            UPDATE tool_executions
            SET status = 'running', started_at = ?
            WHERE id = ?
            """,
            (started_at, execution_id),
        )

    logger.info("Executing: %s", " ".join(cmd))

    # Validate script exists before running
    if not script_path.exists():
        final_stderr = f"Script not found: {script_path}"
        final_summary = "Script file missing"
        logger.error(final_stderr)
        # Fall through to finally block

    # Quick validation: check Python is accessible
    elif not _validate_python():
        final_stderr = "Python validation failed"
        final_summary = "Python not accessible"
        logger.error(final_stderr)
        # Fall through to finally block

    else:
        # Main execution block
        try:
            # Determine subprocess options based on show_console flag
            if show_console and sys.platform == "win32":
                # Windows: create a temporary batch file that keeps the window open
                import tempfile

                # Build the command string for the batch file
                cmd_str = " ".join(f'"{c}"' if " " in c else c for c in cmd)

                batch_content = f'''@echo off
title {tool["name"]} - Running...
cd /d "{PROJECT_ROOT}"
echo ======================================
echo Running: {tool["name"]}
echo Command: {cmd_str}
echo ======================================
echo.

{cmd_str}

echo.
echo ======================================
if errorlevel 1 (
    echo FAILED with exit code %errorlevel%
    echo.
    echo Press any key to close this window...
    pause > nul
) else (
    echo COMPLETED successfully
    echo.
    echo Window will close in 10 seconds...
    timeout /t 10
)
'''
                # Write batch file
                batch_file = Path(tempfile.gettempdir()) / f"tool_run_{execution_id}.bat"
                batch_file.write_text(batch_content)

                logger.info("Created batch file: %s", batch_file)

                process = subprocess.Popen(
                    ["cmd", "/c", str(batch_file)],
                    cwd=str(PROJECT_ROOT),
                    env={**os.environ, "PYTHONUNBUFFERED": "1"},
                    creationflags=subprocess.CREATE_NEW_CONSOLE,
                )
            else:
                # Normal background execution with output capture
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    bufsize=1,  # Line buffered for better output capture
                    encoding="utf-8",  # Explicit UTF-8 encoding for non-ASCII characters
                    errors="replace",  # Replace undecodable bytes instead of failing
                    cwd=str(PROJECT_ROOT),
                    env={**os.environ, "PYTHONUNBUFFERED": "1", "PYTHONIOENCODING": "utf-8"},
                )

            # Track the process
            with _process_lock:
                _running_processes[execution_id] = process

            # Wait for completion with timeout (1 hour max)
            EXECUTION_TIMEOUT = 3600  # 1 hour in seconds

            if show_console and sys.platform == "win32":
                # Console mode: no output capture, just wait for completion
                try:
                    process.wait(timeout=EXECUTION_TIMEOUT)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
                    final_stderr = f"Execution timed out after {EXECUTION_TIMEOUT} seconds"
                    final_summary = "Timed out"
                    raise

                final_exit_code = process.returncode
                final_stdout = "(Output displayed in console window)"
                final_stderr = ""
                final_summary = "Executed in visible console window"
            else:
                # Normal mode: capture output with timeout
                try:
                    final_stdout, final_stderr = process.communicate(timeout=EXECUTION_TIMEOUT)
                except subprocess.TimeoutExpired:
                    process.kill()
                    final_stdout, final_stderr = process.communicate()
                    final_stderr += f"\n\nExecution timed out after {EXECUTION_TIMEOUT} seconds"
                    final_summary = "Timed out"
                    raise

                final_exit_code = process.returncode
                final_summary, final_summary_json = _extract_summary(final_stdout, final_stderr, tool_id)

            # Determine final status
            final_status = "completed" if final_exit_code == 0 else "failed"
            logger.info("Execution #%d completed with status %s", execution_id, final_status)

        except subprocess.TimeoutExpired:
            final_status = "failed"
            logger.error("Execution #%d timed out", execution_id)

        except Exception as e:
            final_status = "failed"
            final_stderr = str(e)
            final_summary = f"Error: {str(e)[:100]}"
            logger.error("Execution #%d failed with error: %s", execution_id, e)

        finally:
            with _process_lock:
                _running_processes.pop(execution_id, None)

    # GUARANTEED: Update final status in database
    # This runs even if exceptions occurred above
    try:
        completed_at = datetime.now().isoformat()
        with get_connection() as conn:
            execute(
                conn,
                """
                UPDATE tool_executions
                SET status = ?, completed_at = ?, exit_code = ?,
                    stdout = ?, stderr = ?, summary = ?, summary_json = ?
                WHERE id = ?
                """,
                (
                    final_status,
                    completed_at,
                    final_exit_code,
                    final_stdout,
                    final_stderr,
                    final_summary,
                    final_summary_json,
                    execution_id,
                ),
            )
        logger.info("Execution #%d final status: %s", execution_id, final_status)
    except Exception as db_error:
        # CRITICAL: If we can't update the database, log it prominently
        logger.critical(
            "CRITICAL: Failed to update execution #%d status to '%s': %s. "
            "This will cause frontend spinner to hang!",
            execution_id,
            final_status,
            db_error,
        )


def _validate_python() -> bool:
    """Check that Python is accessible."""
    try:
        result = subprocess.run(
            [PYTHON_CMD, "--version"],
            capture_output=True,
            text=True,
            timeout=10,
            cwd=str(PROJECT_ROOT),
        )
        if result.returncode != 0:
            return False
        logger.info("Python validated: %s", result.stdout.strip())
        return True
    except Exception as e:
        logger.error("Python validation failed: %s", e)
        return False


def _extract_summary(stdout: str, stderr: str, tool_id: str) -> tuple[str, Optional[str]]:
    """Extract a human-readable summary and JSON data from tool output.

    Returns:
        Tuple of (human_readable_summary, json_string_or_none)
    """
    lines = stdout.strip().split("\n") if stdout else []
    summary_json: Optional[str] = None

    # Try to extract structured JSON summary first
    json_summary = _extract_json_summary(stdout)
    if json_summary:
        summary_json = json.dumps(json_summary)
        # Format human-readable summary from JSON
        human_summary = _format_json_summary(json_summary, tool_id)
        if human_summary:
            return human_summary, summary_json

    # Tool-specific summary extraction (fallback)
    if tool_id == "scraper":
        # Look for summary lines in scraper output
        for line in reversed(lines):
            if "properties" in line.lower() or "scraped" in line.lower():
                return line.strip(), summary_json
        if lines:
            return lines[-1][:200], summary_json

    elif tool_id == "domain-estimator":
        # Look for estimate count or stats
        for line in reversed(lines):
            if "estimate" in line.lower() or "processed" in line.lower():
                return line.strip(), summary_json
        if lines:
            return lines[-1][:200], summary_json

    elif tool_id == "train-model":
        # Look for model metrics
        for line in reversed(lines):
            if "r2" in line.lower() or "mae" in line.lower() or "trained" in line.lower():
                return line.strip(), summary_json
        if lines:
            return lines[-1][:200], summary_json

    elif tool_id == "ml-batch-estimates":
        # Look for prediction count
        for line in reversed(lines):
            if "predict" in line.lower() or "properties" in line.lower():
                return line.strip(), summary_json
        if lines:
            return lines[-1][:200], summary_json

    # Default: last non-empty line
    if lines:
        return lines[-1][:200], summary_json

    # Final fallback - distinguish errors from warnings
    if stderr:
        stderr_lower = stderr.lower()
        # Only treat as error if it contains actual error indicators
        is_actual_error = any(
            x in stderr_lower
            for x in ["traceback", "error:", "exception", "failed", "importerror", "syntaxerror"]
        )
        if is_actual_error:
            return f"Error: {stderr.strip()[:100]}", summary_json
        else:
            # Just warnings (e.g., XGBoost UserWarning), not an error
            return "Completed (see output for details)", summary_json

    return "No output", summary_json


def _extract_json_summary(stdout: str) -> Optional[Dict[str, Any]]:
    """Extract JSON summary from stdout if present.

    Looks for content between ---JSON_SUMMARY_START--- and ---JSON_SUMMARY_END--- markers.
    """
    if not stdout:
        return None

    start_marker = "---JSON_SUMMARY_START---"
    end_marker = "---JSON_SUMMARY_END---"

    start_idx = stdout.find(start_marker)
    if start_idx == -1:
        return None

    end_idx = stdout.find(end_marker, start_idx)
    if end_idx == -1:
        return None

    json_str = stdout[start_idx + len(start_marker) : end_idx].strip()

    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        logger.warning("Failed to parse JSON summary: %s", e)
        return None


def _format_json_summary(data: Dict[str, Any], tool_id: str) -> Optional[str]:
    """Format JSON summary as human-readable string."""
    if tool_id == "scraper" and "scraper_summary" in data:
        summary = data["scraper_summary"]
        changes = summary.get("daily_changes", {})
        stats = summary.get("current_stats", {})

        parts = []
        new_count = changes.get("new_count", 0)
        sold_count = changes.get("sold_count", 0)
        adj_count = changes.get("adjusted_count", 0)

        if new_count or sold_count or adj_count:
            parts.append(f"{new_count} new, {sold_count} sold, {adj_count} adjusted")

        total = stats.get("total_for_sale", 0)
        if total:
            parts.append(f"{total} active")

        return " | ".join(parts) if parts else None

    # Handle catchment update summary
    if tool_id == "scraper" and "catchment_summary" in data:
        summary = data["catchment_summary"]
        marked = summary.get("properties_marked", 0)
        for_sale = summary.get("for_sale_count", 0)
        sold = summary.get("sold_count", 0)
        found = summary.get("catchment_ids_found", 0)

        parts = [f"Catchment: {marked} properties marked"]
        if for_sale or sold:
            parts.append(f"({for_sale} for sale, {sold} sold)")

        # Add property addresses if available
        for_sale_list = summary.get("for_sale", [])
        if for_sale_list:
            addresses = [p.get("address", "Unknown") for p in for_sale_list[:5]]
            if len(for_sale_list) > 5:
                addresses.append(f"+{len(for_sale_list) - 5} more")
            parts.append(f"For sale: {', '.join(addresses)}")

        return " | ".join(parts) if parts else None

    return None
