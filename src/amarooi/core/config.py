"""Application configuration via environment variables.

This module exposes a ``Settings`` class (backed by *pydantic-settings*) and a
cached ``get_settings()`` factory.  All runtime configuration is loaded from
environment variables or an optional ``.env`` file in the working directory.

First-Run Onboarding
--------------------
When ``GROQ_API_KEY`` is not present in the environment *or* in the project
``.env`` file, :func:`ensure_api_key` interactively prompts the user for a key
and persists it to ``~/.amarooi/.env`` so that subsequent invocations load it
automatically.

Example::

    >>> from amarooi.core.config import get_settings
    >>> settings = get_settings()
    >>> settings.DEFAULT_MODEL
    'llama-3.3-70b-versatile'
"""

from __future__ import annotations

import functools
import os
from pathlib import Path

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from amarooi.core.exceptions import ConfigurationError

#: Path to the user-global Amarooi configuration directory.
AMAROOI_HOME: Path = Path.home() / ".amarooi"

#: Path to the user-global ``.env`` file persisted during first-run onboarding.
AMAROOI_ENV_FILE: Path = AMAROOI_HOME / ".env"


def _env_files() -> list[str]:
    """Return the ordered list of ``.env`` files to load.

    The user-global ``~/.amarooi/.env`` is consulted first so that a
    project-level ``.env`` can override it when present.

    Returns:
        List of path strings that pydantic-settings will attempt to load.
    """
    files: list[str] = [str(AMAROOI_ENV_FILE), ".env"]
    return files


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables.

    Attributes:
        GROQ_API_KEY: Required Groq API key.  Must be non-empty.
        DEFAULT_MODEL: Default LLM model for standard logic and CLI operations.
        REASONING_MODEL: Model reserved for complex reasoning and state planning.
        MAX_RETRIES: Maximum retry attempts for transient API failures.
        REQUEST_TIMEOUT: HTTP request timeout in seconds.
        LOG_LEVEL: Python logging level string (e.g. ``"INFO"``, ``"DEBUG"``).
    """

    model_config = SettingsConfigDict(
        env_file=_env_files(),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    GROQ_API_KEY: SecretStr
    DEFAULT_MODEL: str = "llama-3.3-70b-versatile"
    REASONING_MODEL: str = "llama-3.3-70b-versatile"
    MAX_RETRIES: int = 3
    REQUEST_TIMEOUT: float = 30.0
    LOG_LEVEL: str = "INFO"

    @field_validator("GROQ_API_KEY")
    @classmethod
    def _validate_api_key(cls, value: SecretStr) -> SecretStr:
        """Ensure the API key is non-empty.

        Args:
            value: The raw ``SecretStr`` value read from the environment.

        Returns:
            The validated ``SecretStr`` if it is non-empty.

        Raises:
            ValueError: If the secret resolves to an empty string.
        """
        if not value.get_secret_value().strip():
            raise ValueError("GROQ_API_KEY must not be empty.")
        return value


@functools.lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the application settings, loading them on first call.

    The result is cached so that environment variables are read only once per
    process.  Call ``get_settings.cache_clear()`` in tests to reset the cache.

    Returns:
        A fully validated :class:`Settings` instance.

    Raises:
        ConfigurationError: If ``GROQ_API_KEY`` is absent or invalid, or if
            any other configuration field fails validation.
    """
    try:
        return Settings()  # type: ignore[call-arg]
    except Exception as exc:
        raise ConfigurationError(
            "Amarooi configuration is invalid.  "
            "Ensure that GROQ_API_KEY is set in your environment or in a "
            ".env file.  "
            f"Details: {exc}"
        ) from exc


# ---------------------------------------------------------------------------
# First-Run Onboarding
# ---------------------------------------------------------------------------


def save_api_key(api_key: str) -> None:
    """Persist *api_key* to ``~/.amarooi/.env``.

    Creates ``~/.amarooi/`` if it does not already exist.  The key is written
    in ``KEY=value`` format so that the file can be loaded by *python-dotenv*
    or any POSIX shell.

    Args:
        api_key: The raw Groq API key string to persist.

    Raises:
        ValueError: If *api_key* is empty or contains only whitespace.
    """
    if not api_key or not api_key.strip():
        raise ValueError("api_key must not be empty.")

    AMAROOI_HOME.mkdir(parents=True, exist_ok=True)

    # Read existing content so we can replace an existing key line.
    existing_lines: list[str] = []
    if AMAROOI_ENV_FILE.exists():
        existing_lines = AMAROOI_ENV_FILE.read_text(encoding="utf-8").splitlines()

    new_lines: list[str] = [
        line for line in existing_lines if not line.startswith("GROQ_API_KEY=")
    ]
    new_lines.append(f"GROQ_API_KEY={api_key.strip()}")
    AMAROOI_ENV_FILE.write_text("\n".join(new_lines) + "\n", encoding="utf-8")


def ensure_api_key(*, interactive: bool = True) -> str:
    """Return the Groq API key, running onboarding if it is absent.

    Checks ``GROQ_API_KEY`` in the environment first, then in
    ``~/.amarooi/.env``.  When the key is not found and *interactive* is
    ``True``, the user is prompted to enter one; the supplied value is
    persisted via :func:`save_api_key` and injected into the current process
    environment so that :func:`get_settings` can pick it up immediately.

    Args:
        interactive: When ``False`` the function raises
            :class:`~amarooi.core.exceptions.ConfigurationError` instead of
            prompting the user.

    Returns:
        The validated, non-empty API key string.

    Raises:
        ConfigurationError: If no key is found and *interactive* is ``False``,
            or if the user supplies an empty value interactively.
    """
    # 1. Already set in the environment?
    key = os.environ.get("GROQ_API_KEY", "").strip()
    if key:
        return key

    # 2. Present in ~/.amarooi/.env?
    if AMAROOI_ENV_FILE.exists():
        from dotenv import dotenv_values  # type: ignore[import-untyped]

        values = dotenv_values(str(AMAROOI_ENV_FILE))
        key = (values.get("GROQ_API_KEY") or "").strip()
        if key:
            os.environ["GROQ_API_KEY"] = key
            return key

    # 3. Interactive onboarding.
    if not interactive:
        raise ConfigurationError(
            "GROQ_API_KEY is not set.  "
            "Run `amarooi` interactively to complete first-run onboarding, "
            "or set the key in your environment."
        )

    print(
        "\n[Amarooi] First-run setup: a Groq API key is required.\n"
        "  Get a free key at https://console.groq.com/keys\n"
    )
    key = input("  Enter your GROQ_API_KEY: ").strip()
    if not key:
        raise ConfigurationError("No API key supplied.  Onboarding cancelled.")

    save_api_key(key)
    os.environ["GROQ_API_KEY"] = key
    print(f"  ✓ Key saved to {AMAROOI_ENV_FILE}\n")
    return key
