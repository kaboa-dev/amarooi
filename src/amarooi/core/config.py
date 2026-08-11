"""Application configuration via environment variables.

This module exposes a ``Settings`` class (backed by *pydantic-settings*) and a
cached ``get_settings()`` factory.  All runtime configuration is loaded from
environment variables or an optional ``.env`` file in the working directory.

Example:
    >>> from amarooi.core.config import get_settings
    >>> settings = get_settings()
    >>> settings.DEFAULT_MODEL
    'llama-3.3-70b-versatile'
"""

from __future__ import annotations

import functools

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from amarooi.core.exceptions import ConfigurationError


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
        env_file=".env",
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
