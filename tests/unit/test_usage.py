"""Unit tests for Phase 7: Local Usage Tracker.

Covers:
- Counter increment and persistence.
- Monthly rollover when the stored month differs.
- Limit enforcement and upgrade message.
- Spec-file-count limit.
- Reset functionality.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from amarooi.core.usage import (
    MONTHLY_LIMITS,
    SPEC_LIMIT,
    UsageTracker,
    _UPGRADE_MESSAGE,
    _current_month,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_tracker(tmp_path: Path) -> UsageTracker:
    return UsageTracker(usage_file=tmp_path / "usage.json")


# ---------------------------------------------------------------------------
# increment
# ---------------------------------------------------------------------------


class TestIncrement:
    def test_increment_creates_file(self, tmp_path: Path) -> None:
        tracker = _make_tracker(tmp_path)
        tracker.increment("transpile")
        assert (tmp_path / "usage.json").exists()

    def test_increment_increases_counter(self, tmp_path: Path) -> None:
        tracker = _make_tracker(tmp_path)
        tracker.increment("transpile")
        tracker.increment("transpile")
        counts = tracker.get_counts()
        assert counts["transpile"] == 2

    def test_increment_returns_none_within_limits(self, tmp_path: Path) -> None:
        tracker = _make_tracker(tmp_path)
        result = tracker.increment("transpile")
        assert result is None

    def test_increment_returns_upgrade_message_at_limit(self, tmp_path: Path) -> None:
        tracker = _make_tracker(tmp_path)
        limit = MONTHLY_LIMITS["transpile"]
        for _ in range(limit - 1):
            tracker.increment("transpile")
        result = tracker.increment("transpile")
        assert result == _UPGRADE_MESSAGE

    def test_increment_extraction_counter(self, tmp_path: Path) -> None:
        tracker = _make_tracker(tmp_path)
        tracker.increment("extraction")
        assert tracker.get_counts()["extraction"] == 1

    def test_increment_extraction_returns_upgrade_at_limit(self, tmp_path: Path) -> None:
        tracker = _make_tracker(tmp_path)
        limit = MONTHLY_LIMITS["extraction"]
        for _ in range(limit - 1):
            tracker.increment("extraction")
        result = tracker.increment("extraction")
        assert result == _UPGRADE_MESSAGE


# ---------------------------------------------------------------------------
# check_limit
# ---------------------------------------------------------------------------


class TestCheckLimit:
    def test_check_limit_within_allows(self, tmp_path: Path) -> None:
        tracker = _make_tracker(tmp_path)
        result = tracker.check_limit("transpile")
        assert result is None

    def test_check_limit_at_limit_returns_message(self, tmp_path: Path) -> None:
        tracker = _make_tracker(tmp_path)
        limit = MONTHLY_LIMITS["transpile"]
        for _ in range(limit):
            tracker.increment("transpile")
        result = tracker.check_limit("transpile")
        assert result == _UPGRADE_MESSAGE

    def test_check_limit_does_not_modify_counter(self, tmp_path: Path) -> None:
        tracker = _make_tracker(tmp_path)
        tracker.increment("transpile")
        tracker.check_limit("transpile")
        assert tracker.get_counts()["transpile"] == 1


# ---------------------------------------------------------------------------
# Monthly rollover
# ---------------------------------------------------------------------------


class TestMonthlyRollover:
    def test_rollover_resets_counters(self, tmp_path: Path) -> None:
        usage_file = tmp_path / "usage.json"
        # Write a file that claims it was last updated in a past month.
        usage_file.write_text(
            json.dumps({"month": "2000-01", "transpile": 25, "extraction": 9}),
            encoding="utf-8",
        )
        tracker = UsageTracker(usage_file=usage_file)
        counts = tracker.get_counts()
        assert counts["transpile"] == 0
        assert counts["extraction"] == 0

    def test_rollover_updates_stored_month(self, tmp_path: Path) -> None:
        usage_file = tmp_path / "usage.json"
        usage_file.write_text(
            json.dumps({"month": "2000-01", "transpile": 10}),
            encoding="utf-8",
        )
        tracker = UsageTracker(usage_file=usage_file)
        tracker.get_counts()
        tracker.increment("transpile")
        data = json.loads(usage_file.read_text(encoding="utf-8"))
        assert data["month"] == _current_month()

    def test_no_rollover_same_month(self, tmp_path: Path) -> None:
        usage_file = tmp_path / "usage.json"
        usage_file.write_text(
            json.dumps({"month": _current_month(), "transpile": 5, "extraction": 2}),
            encoding="utf-8",
        )
        tracker = UsageTracker(usage_file=usage_file)
        counts = tracker.get_counts()
        assert counts["transpile"] == 5
        assert counts["extraction"] == 2


# ---------------------------------------------------------------------------
# check_spec_limit
# ---------------------------------------------------------------------------


class TestCheckSpecLimit:
    def test_within_spec_limit(self, tmp_path: Path) -> None:
        spec_dir = tmp_path / "logic"
        spec_dir.mkdir()
        for i in range(SPEC_LIMIT - 1):
            (spec_dir / f"component_{i}.amarooi").write_text("", encoding="utf-8")

        tracker = _make_tracker(tmp_path)
        result = tracker.check_spec_limit(spec_dir)
        assert result is None

    def test_at_spec_limit_returns_upgrade_message(self, tmp_path: Path) -> None:
        spec_dir = tmp_path / "logic"
        spec_dir.mkdir()
        for i in range(SPEC_LIMIT):
            (spec_dir / f"component_{i}.amarooi").write_text("", encoding="utf-8")

        tracker = _make_tracker(tmp_path)
        result = tracker.check_spec_limit(spec_dir)
        assert result == _UPGRADE_MESSAGE

    def test_nonexistent_spec_dir_is_within_limit(self, tmp_path: Path) -> None:
        tracker = _make_tracker(tmp_path)
        result = tracker.check_spec_limit(tmp_path / "nonexistent")
        assert result is None


# ---------------------------------------------------------------------------
# reset
# ---------------------------------------------------------------------------


class TestReset:
    def test_reset_zeroes_counters(self, tmp_path: Path) -> None:
        tracker = _make_tracker(tmp_path)
        for _ in range(5):
            tracker.increment("transpile")
        tracker.reset()
        assert tracker.get_counts()["transpile"] == 0

    def test_reset_writes_current_month(self, tmp_path: Path) -> None:
        usage_file = tmp_path / "usage.json"
        tracker = UsageTracker(usage_file=usage_file)
        tracker.reset()
        data = json.loads(usage_file.read_text(encoding="utf-8"))
        assert data["month"] == _current_month()


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


class TestPersistence:
    def test_data_persists_across_tracker_instances(self, tmp_path: Path) -> None:
        usage_file = tmp_path / "usage.json"
        t1 = UsageTracker(usage_file=usage_file)
        t1.increment("transpile")
        t1.increment("transpile")

        t2 = UsageTracker(usage_file=usage_file)
        assert t2.get_counts()["transpile"] == 2

    def test_missing_file_returns_zero_counts(self, tmp_path: Path) -> None:
        tracker = _make_tracker(tmp_path)
        counts = tracker.get_counts()
        assert all(v == 0 for v in counts.values())
