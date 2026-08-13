"""Local Freemium Usage Tracker.

Tracks monthly usage of Amarooi features against healthy free-tier limits and
stores the counter in ``~/.amarooi/usage.json``.

Limits
------
- **96 transpile runs / month**
- **10 code extractions / month**
- **5 active ``.amarooi`` specs per project**

When a limit is reached a non-blocking notification string is returned instead
of raising an exception, so the caller can display it to the user without
interrupting the current session.

Example::

    from amarooi.core.usage import UsageTracker
    tracker = UsageTracker()
    tracker.increment("transpile")        # returns None (within limits)
    tracker.check_limit("transpile")      # returns None (within limits)
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Literal

from amarooi.core.config import AMAROOI_HOME

#: Path to the local usage counter file.
USAGE_FILE: Path = AMAROOI_HOME / "usage.json"

#: Upgrade message shown when a monthly limit is reached.
_UPGRADE_MESSAGE = (
    "Monthly free allowance reached. "
    "Unlock unlimited local runs forever with an Amarooi Pro Lifetime Key "
    "($29 Dev / $149 Team)."
)

#: Monthly limits keyed by feature name.
MONTHLY_LIMITS: dict[str, int] = {
    "transpile": 96,
    "extraction": 10,
}

#: Absolute (project-level) limit for active `.amarooi` specs.
SPEC_LIMIT: int = 5

FeatureName = Literal["transpile", "extraction"]


class UsageTracker:
    """Lightweight local counter stored at ``~/.amarooi/usage.json``.

    The JSON file has the structure::

        {
          "month": "2026-08",
          "transpile": 12,
          "extraction": 3
        }

    Counters are automatically reset when the stored month differs from the
    current calendar month.

    Args:
        usage_file: Path to the JSON counter file.  Defaults to
            ``~/.amarooi/usage.json``.  Override in tests via a ``tmp_path``.
    """

    def __init__(self, usage_file: Path | None = None) -> None:
        self._path = usage_file or USAGE_FILE

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def increment(self, feature: FeatureName) -> str | None:
        """Increment the monthly counter for *feature*.

        Args:
            feature: One of ``"transpile"`` or ``"extraction"``.

        Returns:
            ``None`` when the new count is within limits, or the
            :data:`_UPGRADE_MESSAGE` string when the limit has been reached
            **after** this increment.
        """
        data = self._load()
        self._maybe_rollover(data)
        data[feature] = data.get(feature, 0) + 1
        self._save(data)

        limit = MONTHLY_LIMITS.get(feature, 0)
        if limit and data[feature] >= limit:
            return _UPGRADE_MESSAGE
        return None

    def check_limit(self, feature: FeatureName) -> str | None:
        """Check whether the monthly limit for *feature* has been reached.

        Does **not** modify the counter.

        Args:
            feature: One of ``"transpile"`` or ``"extraction"``.

        Returns:
            ``None`` when still within limits, or the :data:`_UPGRADE_MESSAGE`
            string when the limit has been reached.
        """
        data = self._load()
        self._maybe_rollover(data)
        limit = MONTHLY_LIMITS.get(feature, 0)
        if limit and data.get(feature, 0) >= limit:
            return _UPGRADE_MESSAGE
        return None

    def check_spec_limit(self, spec_dir: Path) -> str | None:
        """Check whether the project-level active-spec limit has been reached.

        Counts ``.amarooi`` files directly inside *spec_dir*.

        Args:
            spec_dir: Directory in which ``.amarooi`` files live (e.g.
                ``Path("logic")``).

        Returns:
            ``None`` when within the limit, or the :data:`_UPGRADE_MESSAGE`
            string when the limit has been reached.
        """
        count = len(list(spec_dir.glob("*.amarooi"))) if spec_dir.exists() else 0
        if count >= SPEC_LIMIT:
            return _UPGRADE_MESSAGE
        return None

    def get_counts(self) -> dict[str, int]:
        """Return current month's counters as a plain ``dict``.

        Returns:
            Dictionary mapping feature names to their current counts.
        """
        data = self._load()
        self._maybe_rollover(data)
        return {f: data.get(f, 0) for f in MONTHLY_LIMITS}

    def reset(self) -> None:
        """Reset all counters to zero for the current month.

        Useful in tests and for manual resets.
        """
        month = _current_month()
        self._save({f: 0 for f in MONTHLY_LIMITS} | {"month": month})

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _load(self) -> dict:
        """Load the usage JSON, returning an empty dict if not found."""
        if self._path.exists():
            try:
                return json.loads(self._path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass
        return {}

    def _save(self, data: dict) -> None:
        """Persist *data* to :attr:`_path`, creating parent dirs as needed."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    @staticmethod
    def _maybe_rollover(data: dict) -> None:
        """Reset counters in-place if the stored month is stale.

        Args:
            data: Mutable usage dict loaded from disk.
        """
        month = _current_month()
        if data.get("month") != month:
            for feature in MONTHLY_LIMITS:
                data[feature] = 0
            data["month"] = month


def _current_month() -> str:
    """Return the current month as ``"YYYY-MM"``."""
    return datetime.now().strftime("%Y-%m")
