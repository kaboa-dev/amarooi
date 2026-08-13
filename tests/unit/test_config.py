"""Unit tests for Phase 7: First-Run Onboarding & persistent config.

Covers:
- ``save_api_key()`` creates ``~/.amarooi/.env`` and persists the key.
- ``save_api_key()`` updates an existing key without duplicating it.
- ``ensure_api_key()`` reads from the home env file and injects the key.
- ``ensure_api_key()`` raises ``ConfigurationError`` in non-interactive mode
  when no key is present.
- The ``Settings`` class can load from the home env file.
"""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from amarooi.core.exceptions import ConfigurationError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _clear_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GROQ_API_KEY", raising=False)


# ---------------------------------------------------------------------------
# save_api_key
# ---------------------------------------------------------------------------


class TestSaveApiKey:
    def test_creates_amarooi_home_directory(self, tmp_path: Path) -> None:
        amarooi_home = tmp_path / ".amarooi"
        env_file = amarooi_home / ".env"

        with (
            patch("amarooi.core.config.AMAROOI_HOME", amarooi_home),
            patch("amarooi.core.config.AMAROOI_ENV_FILE", env_file),
        ):
            from amarooi.core.config import save_api_key
            save_api_key("gsk_test_key")

        assert amarooi_home.exists()

    def test_writes_key_to_env_file(self, tmp_path: Path) -> None:
        amarooi_home = tmp_path / ".amarooi"
        env_file = amarooi_home / ".env"

        with (
            patch("amarooi.core.config.AMAROOI_HOME", amarooi_home),
            patch("amarooi.core.config.AMAROOI_ENV_FILE", env_file),
        ):
            from amarooi.core.config import save_api_key
            save_api_key("gsk_test_key_123")

        content = env_file.read_text(encoding="utf-8")
        assert "GROQ_API_KEY=gsk_test_key_123" in content

    def test_updates_existing_key(self, tmp_path: Path) -> None:
        amarooi_home = tmp_path / ".amarooi"
        env_file = amarooi_home / ".env"
        amarooi_home.mkdir()
        env_file.write_text("GROQ_API_KEY=old_key\n", encoding="utf-8")

        with (
            patch("amarooi.core.config.AMAROOI_HOME", amarooi_home),
            patch("amarooi.core.config.AMAROOI_ENV_FILE", env_file),
        ):
            from amarooi.core.config import save_api_key
            save_api_key("gsk_new_key")

        content = env_file.read_text(encoding="utf-8")
        assert "GROQ_API_KEY=gsk_new_key" in content
        assert "old_key" not in content

    def test_no_duplicate_key_lines(self, tmp_path: Path) -> None:
        amarooi_home = tmp_path / ".amarooi"
        env_file = amarooi_home / ".env"
        amarooi_home.mkdir()
        env_file.write_text("GROQ_API_KEY=old\n", encoding="utf-8")

        with (
            patch("amarooi.core.config.AMAROOI_HOME", amarooi_home),
            patch("amarooi.core.config.AMAROOI_ENV_FILE", env_file),
        ):
            from amarooi.core.config import save_api_key
            save_api_key("gsk_new")

        lines = [
            ln for ln in env_file.read_text(encoding="utf-8").splitlines()
            if ln.startswith("GROQ_API_KEY=")
        ]
        assert len(lines) == 1

    def test_empty_key_raises_value_error(self, tmp_path: Path) -> None:
        amarooi_home = tmp_path / ".amarooi"
        env_file = amarooi_home / ".env"

        with (
            patch("amarooi.core.config.AMAROOI_HOME", amarooi_home),
            patch("amarooi.core.config.AMAROOI_ENV_FILE", env_file),
        ):
            from amarooi.core.config import save_api_key
            with pytest.raises(ValueError):
                save_api_key("")

    def test_whitespace_key_raises_value_error(self, tmp_path: Path) -> None:
        amarooi_home = tmp_path / ".amarooi"
        env_file = amarooi_home / ".env"

        with (
            patch("amarooi.core.config.AMAROOI_HOME", amarooi_home),
            patch("amarooi.core.config.AMAROOI_ENV_FILE", env_file),
        ):
            from amarooi.core.config import save_api_key
            with pytest.raises(ValueError):
                save_api_key("   ")

    def test_preserves_other_env_vars(self, tmp_path: Path) -> None:
        amarooi_home = tmp_path / ".amarooi"
        env_file = amarooi_home / ".env"
        amarooi_home.mkdir()
        env_file.write_text("OTHER_VAR=hello\nGROQ_API_KEY=old\n", encoding="utf-8")

        with (
            patch("amarooi.core.config.AMAROOI_HOME", amarooi_home),
            patch("amarooi.core.config.AMAROOI_ENV_FILE", env_file),
        ):
            from amarooi.core.config import save_api_key
            save_api_key("gsk_new")

        content = env_file.read_text(encoding="utf-8")
        assert "OTHER_VAR=hello" in content


# ---------------------------------------------------------------------------
# ensure_api_key
# ---------------------------------------------------------------------------


class TestEnsureApiKey:
    def test_returns_key_from_environment(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setenv("GROQ_API_KEY", "gsk_from_env")
        env_file = tmp_path / ".amarooi" / ".env"

        with patch("amarooi.core.config.AMAROOI_ENV_FILE", env_file):
            from amarooi.core.config import ensure_api_key
            key = ensure_api_key(interactive=False)

        assert key == "gsk_from_env"

    def test_returns_key_from_home_env_file(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.delenv("GROQ_API_KEY", raising=False)
        amarooi_home = tmp_path / ".amarooi"
        env_file = amarooi_home / ".env"
        amarooi_home.mkdir()
        env_file.write_text("GROQ_API_KEY=gsk_from_file\n", encoding="utf-8")

        with (
            patch("amarooi.core.config.AMAROOI_HOME", amarooi_home),
            patch("amarooi.core.config.AMAROOI_ENV_FILE", env_file),
        ):
            from amarooi.core.config import ensure_api_key
            key = ensure_api_key(interactive=False)

        assert key == "gsk_from_file"

    def test_injects_key_into_environment(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.delenv("GROQ_API_KEY", raising=False)
        amarooi_home = tmp_path / ".amarooi"
        env_file = amarooi_home / ".env"
        amarooi_home.mkdir()
        env_file.write_text("GROQ_API_KEY=gsk_injected\n", encoding="utf-8")

        with (
            patch("amarooi.core.config.AMAROOI_HOME", amarooi_home),
            patch("amarooi.core.config.AMAROOI_ENV_FILE", env_file),
        ):
            from amarooi.core.config import ensure_api_key
            ensure_api_key(interactive=False)

        assert os.environ.get("GROQ_API_KEY") == "gsk_injected"

    def test_raises_configuration_error_non_interactive(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.delenv("GROQ_API_KEY", raising=False)
        env_file = tmp_path / "missing.env"

        with patch("amarooi.core.config.AMAROOI_ENV_FILE", env_file):
            from amarooi.core.config import ensure_api_key
            with pytest.raises(ConfigurationError):
                ensure_api_key(interactive=False)

    def test_interactive_saves_and_returns_key(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.delenv("GROQ_API_KEY", raising=False)
        amarooi_home = tmp_path / ".amarooi"
        env_file = amarooi_home / ".env"

        with (
            patch("amarooi.core.config.AMAROOI_HOME", amarooi_home),
            patch("amarooi.core.config.AMAROOI_ENV_FILE", env_file),
            patch("builtins.input", return_value="gsk_interactive"),
            patch("builtins.print"),
        ):
            from amarooi.core.config import ensure_api_key
            key = ensure_api_key(interactive=True)

        assert key == "gsk_interactive"
        assert env_file.exists()
        assert "GROQ_API_KEY=gsk_interactive" in env_file.read_text(encoding="utf-8")

    def test_interactive_empty_input_raises_configuration_error(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.delenv("GROQ_API_KEY", raising=False)
        env_file = tmp_path / "missing.env"

        with (
            patch("amarooi.core.config.AMAROOI_ENV_FILE", env_file),
            patch("builtins.input", return_value=""),
            patch("builtins.print"),
        ):
            from amarooi.core.config import ensure_api_key
            with pytest.raises(ConfigurationError):
                ensure_api_key(interactive=True)


# ---------------------------------------------------------------------------
# Settings – loading from home env file
# ---------------------------------------------------------------------------


class TestSettingsHomeEnvFile:
    def setup_method(self) -> None:
        from amarooi.core.config import get_settings
        get_settings.cache_clear()

    def teardown_method(self) -> None:
        from amarooi.core.config import get_settings
        get_settings.cache_clear()

    def test_settings_loads_from_home_env_file(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.delenv("GROQ_API_KEY", raising=False)
        amarooi_home = tmp_path / ".amarooi"
        env_file = amarooi_home / ".env"
        amarooi_home.mkdir()
        env_file.write_text("GROQ_API_KEY=gsk_home_file\n", encoding="utf-8")

        from amarooi.core.config import Settings
        import pydantic_settings

        # Create Settings with env_file pointing at our tmp file.
        settings = Settings(_env_file=str(env_file))  # type: ignore[call-arg]
        assert settings.GROQ_API_KEY.get_secret_value() == "gsk_home_file"
