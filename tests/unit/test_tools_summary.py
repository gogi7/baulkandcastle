"""Unit tests for tool summary extraction functions."""

import json
import pytest

# Import the functions we're testing
import sys
from pathlib import Path

# Add the src directory to path so we can import baulkandcastle
src_path = Path(__file__).parent.parent.parent / "src"
sys.path.insert(0, str(src_path))

from baulkandcastle.api.tools import _extract_summary, _extract_json_summary


class TestExtractJsonSummary:
    """Tests for _extract_json_summary function."""

    def test_extracts_json_with_markers(self):
        """Should extract JSON between markers."""
        stdout = '''Some output before
---JSON_SUMMARY_START---
{"test": 123}
---JSON_SUMMARY_END---
Some output after'''
        result = _extract_json_summary(stdout)
        assert result == {"test": 123}

    def test_extracts_nested_json(self):
        """Should extract complex nested JSON."""
        stdout = '''---JSON_SUMMARY_START---
{"scraper_summary": {"daily_changes": {"new_count": 5, "sold_count": 2}}}
---JSON_SUMMARY_END---'''
        result = _extract_json_summary(stdout)
        assert result["scraper_summary"]["daily_changes"]["new_count"] == 5

    def test_returns_none_for_empty_stdout(self):
        """Should return None for empty stdout."""
        assert _extract_json_summary("") is None
        assert _extract_json_summary(None) is None

    def test_returns_none_for_missing_start_marker(self):
        """Should return None if start marker is missing."""
        stdout = '''{"test": 123}
---JSON_SUMMARY_END---'''
        assert _extract_json_summary(stdout) is None

    def test_returns_none_for_missing_end_marker(self):
        """Should return None if end marker is missing."""
        stdout = '''---JSON_SUMMARY_START---
{"test": 123}'''
        assert _extract_json_summary(stdout) is None

    def test_returns_none_for_invalid_json(self):
        """Should return None for invalid JSON."""
        stdout = '''---JSON_SUMMARY_START---
{invalid json here}
---JSON_SUMMARY_END---'''
        assert _extract_json_summary(stdout) is None

    def test_handles_whitespace_around_json(self):
        """Should handle whitespace around JSON content."""
        stdout = '''---JSON_SUMMARY_START---

{"test": 1}

---JSON_SUMMARY_END---'''
        result = _extract_json_summary(stdout)
        assert result == {"test": 1}


class TestExtractSummary:
    """Tests for _extract_summary function."""

    def test_extracts_scraper_json_summary(self):
        """Should format scraper summary from JSON."""
        stdout = '''Some output
---JSON_SUMMARY_START---
{"scraper_summary": {"daily_changes": {"new_count": 5, "sold_count": 2, "adjusted_count": 3}, "current_stats": {"total_for_sale": 100}}}
---JSON_SUMMARY_END---'''
        summary, json_str = _extract_summary(stdout, "", "scraper")
        assert "5 new" in summary
        assert "2 sold" in summary
        assert "3 adjusted" in summary
        assert "100 active" in summary
        assert json_str is not None

    def test_handles_empty_stdout_with_warning_stderr(self):
        """Should not treat warnings as errors."""
        stderr = "C:\\path\\xgboost\\core.py:160: UserWarning: some xgboost warning"
        summary, json_str = _extract_summary("", stderr, "scraper")
        assert not summary.startswith("Error:")
        assert "Completed" in summary or "No output" in summary

    def test_handles_actual_error_in_stderr(self):
        """Should recognize actual errors in stderr."""
        stderr = "Traceback (most recent call last):\n  File \"test.py\", line 1"
        summary, json_str = _extract_summary("", stderr, "scraper")
        assert summary.startswith("Error:")

    def test_handles_importerror_in_stderr(self):
        """Should recognize ImportError as actual error."""
        stderr = "ImportError: No module named 'foo'"
        summary, json_str = _extract_summary("", stderr, "scraper")
        assert summary.startswith("Error:")

    def test_handles_exception_in_stderr(self):
        """Should recognize Exception in stderr."""
        stderr = "Exception: something went wrong"
        summary, json_str = _extract_summary("", stderr, "scraper")
        assert summary.startswith("Error:")

    def test_falls_back_to_last_line(self):
        """Should fall back to last stdout line if no JSON."""
        stdout = "Line 1\nLine 2\nFinal output line"
        summary, json_str = _extract_summary(stdout, "", "scraper")
        assert summary == "Final output line"
        assert json_str is None

    def test_returns_no_output_for_empty_both(self):
        """Should return 'No output' when both stdout and stderr are empty."""
        summary, json_str = _extract_summary("", "", "scraper")
        assert summary == "No output"
        assert json_str is None

    def test_scraper_specific_fallback(self):
        """Should look for scraper-specific keywords."""
        stdout = "Starting...\nProcessing...\nScraped 50 properties from domain.com.au"
        summary, json_str = _extract_summary(stdout, "", "scraper")
        assert "properties" in summary.lower() or "scraped" in summary.lower()

    def test_domain_estimator_fallback(self):
        """Should look for estimator-specific keywords."""
        stdout = "Starting...\nProcessed 25 estimates successfully"
        summary, json_str = _extract_summary(stdout, "", "domain-estimator")
        assert "estimate" in summary.lower() or "processed" in summary.lower()

    def test_train_model_fallback(self):
        """Should look for model training keywords."""
        stdout = "Training...\nModel trained with R2=0.95, MAE=50000"
        summary, json_str = _extract_summary(stdout, "", "train-model")
        assert "r2" in summary.lower() or "mae" in summary.lower() or "trained" in summary.lower()

    def test_truncates_long_summaries(self):
        """Should truncate summaries longer than 200 chars."""
        long_line = "x" * 300
        stdout = f"Line 1\n{long_line}"
        summary, json_str = _extract_summary(stdout, "", "unknown-tool")
        assert len(summary) <= 200


class TestSubprocessEncoding:
    """Tests for subprocess output capture with encoding handling."""

    def test_utf8_encoding_captures_unicode(self):
        """Should capture output with Unicode characters using UTF-8 encoding."""
        import subprocess
        import os

        # Create a subprocess that outputs Unicode characters
        process = subprocess.Popen(
            ["python", "-c", "print('Hello 世界 🌍 émojis')"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            env={**os.environ, "PYTHONUNBUFFERED": "1", "PYTHONIOENCODING": "utf-8"},
        )
        stdout, stderr = process.communicate(timeout=10)

        assert stdout is not None
        assert "Hello" in stdout
        # Unicode chars may be replaced but shouldn't cause None stdout

    def test_replace_errors_prevents_unicode_decode_failure(self):
        """Should use replacement character instead of failing on bad bytes."""
        import subprocess
        import os

        # This test simulates what happens with invalid UTF-8 bytes
        # The 'errors=replace' should prevent UnicodeDecodeError
        process = subprocess.Popen(
            ["python", "-c", r"import sys; sys.stdout.buffer.write(b'test\x8fdata\n')"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            env={**os.environ, "PYTHONUNBUFFERED": "1"},
        )
        stdout, stderr = process.communicate(timeout=10)

        # Should not be None - the invalid byte should be replaced
        assert stdout is not None
        assert "test" in stdout
        assert "data" in stdout


class TestScraperIntegration:
    """Integration tests for scraper JSON output."""

    def test_reports_only_produces_json_summary(self):
        """Running --reports-only should produce JSON summary markers."""
        import subprocess
        import os
        from pathlib import Path

        project_root = Path(__file__).parent.parent.parent
        venv_python = project_root / ".venv" / "Scripts" / "python.exe"

        if not venv_python.exists():
            pytest.skip("Virtual environment not found")

        process = subprocess.Popen(
            [str(venv_python), "baulkandcastle_scraper.py", "--reports-only"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=str(project_root),
            env={**os.environ, "PYTHONUNBUFFERED": "1", "PYTHONIOENCODING": "utf-8"},
        )
        stdout, stderr = process.communicate(timeout=120)

        assert stdout is not None, "stdout should not be None"
        assert "---JSON_SUMMARY_START---" in stdout, "Should contain JSON start marker"
        assert "---JSON_SUMMARY_END---" in stdout, "Should contain JSON end marker"

        # Extract and validate JSON
        json_summary = _extract_json_summary(stdout)
        assert json_summary is not None, "Should extract valid JSON"
        assert "scraper_summary" in json_summary, "Should have scraper_summary key"

    def test_summary_extraction_produces_human_readable(self):
        """Summary extraction should produce human-readable output for display."""
        # Simulate realistic scraper output
        stdout = '''
============================================================
                    DAILY SUMMARY
============================================================
[NEW] 123 Test Street (CASTLE HILL)
      Price: $1,500,000
------------------------------
============================================================

---JSON_SUMMARY_START---
{"scraper_summary": {"date": "2026-01-25", "daily_changes": {"new_count": 3, "sold_count": 1, "adjusted_count": 2}, "current_stats": {"total_for_sale": 275, "avg_price": 1500000}}}
---JSON_SUMMARY_END---
'''
        summary, json_str = _extract_summary(stdout, "", "scraper")

        # Verify human-readable summary
        assert "3 new" in summary, "Should show new count"
        assert "1 sold" in summary, "Should show sold count"
        assert "2 adjusted" in summary, "Should show adjusted count"
        assert "275 active" in summary, "Should show active listings"

        # Verify JSON is preserved
        assert json_str is not None
        data = json.loads(json_str)
        assert data["scraper_summary"]["daily_changes"]["new_count"] == 3

    def test_catchment_summary_extraction(self):
        """Should format catchment update summary correctly."""
        stdout = '''
============================================================
EXCELSIOR CATCHMENT UPDATE
============================================================
Properties found on Domain catchment page: 45
Properties matched in database: 11
---JSON_SUMMARY_START---
{"catchment_summary": {"date": "2026-01-25", "catchment_ids_found": 45, "properties_marked": 11, "for_sale_count": 8, "sold_count": 3, "for_sale": [{"address": "123 Test St", "suburb": "CASTLE HILL", "price": "$1,500,000"}, {"address": "456 Other Rd", "suburb": "CASTLE HILL", "price": "$2,000,000"}], "sold": [{"address": "789 Sold Ave", "suburb": "BAULKHAM HILLS", "price": "$1,800,000"}]}, "status": "success"}
---JSON_SUMMARY_END---
'''
        summary, json_str = _extract_summary(stdout, "", "scraper")

        # Should mention catchment and property counts
        assert "Catchment" in summary
        assert "11" in summary  # properties marked
        assert json_str is not None

        # Verify JSON contains property details
        data = json.loads(json_str)
        assert data["catchment_summary"]["for_sale_count"] == 8
        assert data["catchment_summary"]["sold_count"] == 3
        assert len(data["catchment_summary"]["for_sale"]) == 2
