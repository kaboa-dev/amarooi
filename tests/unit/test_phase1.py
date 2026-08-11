"""Unit tests for Phase 1: core utilities, exceptions, and Groq LLM client.

Covers:
- Configuration loading and missing/invalid API key handling.
- Domain exception hierarchy and metadata preservation.
- Mocked Groq client: successful completion, rate-limit retries, and
  structured-JSON validation failures.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from pydantic import BaseModel

from amarooi.core.exceptions import (
    AmarooiException,
    ConfigurationError,
    LLMExecutionError,
    ManifestValidationError,
    TranspilationError,
)


# ---------------------------------------------------------------------------
# Exception hierarchy tests
# ---------------------------------------------------------------------------


class TestExceptionHierarchy:
    """Verify that the custom exception classes form the correct hierarchy."""

    def test_configuration_error_is_amarooi_exception(self) -> None:
        assert issubclass(ConfigurationError, AmarooiException)

    def test_llm_execution_error_is_amarooi_exception(self) -> None:
        assert issubclass(LLMExecutionError, AmarooiException)

    def test_manifest_validation_error_is_amarooi_exception(self) -> None:
        assert issubclass(ManifestValidationError, AmarooiException)

    def test_transpilation_error_is_amarooi_exception(self) -> None:
        assert issubclass(TranspilationError, AmarooiException)

    def test_llm_execution_error_metadata(self) -> None:
        ctx = {"model": "llama-3.3-70b-versatile", "message_count": 2}
        exc = LLMExecutionError("boom", status_code=429, prompt_context=ctx)
        assert str(exc) == "boom"
        assert exc.status_code == 429
        assert exc.prompt_context == ctx

    def test_llm_execution_error_defaults(self) -> None:
        exc = LLMExecutionError("oops")
        assert exc.status_code is None
        assert exc.prompt_context == {}

    def test_cause_preserved(self) -> None:
        original = ValueError("root cause")
        try:
            raise LLMExecutionError("wrapper") from original
        except LLMExecutionError as exc:
            assert exc.__cause__ is original

    def test_all_exceptions_catchable_as_base(self) -> None:
        for cls in (
            ConfigurationError,
            LLMExecutionError,
            ManifestValidationError,
            TranspilationError,
        ):
            with pytest.raises(AmarooiException):
                raise cls("test")


# ---------------------------------------------------------------------------
# Configuration tests
# ---------------------------------------------------------------------------


class TestSettings:
    """Tests for Settings loading and get_settings()."""

    def setup_method(self) -> None:
        """Clear the lru_cache before every test."""
        from amarooi.core.config import get_settings

        get_settings.cache_clear()

    def test_valid_settings_loads(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GROQ_API_KEY", "gsk_test_key_123")
        from amarooi.core.config import get_settings

        settings = get_settings()
        assert settings.GROQ_API_KEY.get_secret_value() == "gsk_test_key_123"
        assert settings.DEFAULT_MODEL == "llama-3.3-70b-versatile"
        assert settings.REASONING_MODEL == "llama-3.3-70b-versatile"
        assert settings.MAX_RETRIES == 3
        assert settings.REQUEST_TIMEOUT == 30.0
        assert settings.LOG_LEVEL == "INFO"

    def test_missing_api_key_raises_configuration_error(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path
    ) -> None:
        from amarooi.core.config import get_settings

        get_settings.cache_clear()
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("GROQ_API_KEY", raising=False)

        with pytest.raises(ConfigurationError):
            get_settings()

    def test_empty_api_key_raises_configuration_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("GROQ_API_KEY", "   ")
        from amarooi.core.config import get_settings

        with pytest.raises(ConfigurationError):
            get_settings()

    def test_custom_values(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GROQ_API_KEY", "gsk_custom")
        monkeypatch.setenv("MAX_RETRIES", "5")
        monkeypatch.setenv("LOG_LEVEL", "DEBUG")
        from amarooi.core.config import get_settings

        settings = get_settings()
        assert settings.MAX_RETRIES == 5
        assert settings.LOG_LEVEL == "DEBUG"

    def test_get_settings_is_cached(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GROQ_API_KEY", "gsk_cached")
        from amarooi.core.config import get_settings

        s1 = get_settings()
        s2 = get_settings()
        assert s1 is s2


# ---------------------------------------------------------------------------
# GroqClientWrapper tests (all Groq SDK calls are mocked)
# ---------------------------------------------------------------------------


def _make_mock_response(content: str) -> MagicMock:
    """Build a minimal mock that mimics the Groq completion response shape."""
    msg = MagicMock()
    msg.content = content
    choice = MagicMock()
    choice.message = msg
    response = MagicMock()
    response.choices = [choice]
    return response


def _make_settings_mock(max_retries: int = 3) -> MagicMock:
    """Return a mock Settings object."""
    settings = MagicMock()
    settings.GROQ_API_KEY.get_secret_value.return_value = "gsk_test"
    settings.DEFAULT_MODEL = "llama-3.3-70b-versatile"
    settings.REQUEST_TIMEOUT = 30.0
    settings.MAX_RETRIES = max_retries
    return settings


class TestGroqClientWrapperCompletion:
    """Tests for generate_completion()."""

    def _make_client(self, max_retries: int = 3) -> tuple:
        """Return (wrapper, mock_groq_client) with patched settings."""
        settings = _make_settings_mock(max_retries)
        with (
            patch("amarooi.utils.llm.get_settings", return_value=settings),
            patch("amarooi.utils.llm.groq.Groq") as MockGroq,
        ):
            mock_groq_instance = MockGroq.return_value
            from amarooi.utils.llm import GroqClientWrapper

            wrapper = GroqClientWrapper()
            wrapper._client = mock_groq_instance
            wrapper._settings = settings
            return wrapper, mock_groq_instance

    def test_successful_completion(self) -> None:
        import groq as groq_lib

        settings = _make_settings_mock()
        with (
            patch("amarooi.utils.llm.get_settings", return_value=settings),
            patch("amarooi.utils.llm.groq.Groq") as MockGroq,
        ):
            mock_client = MockGroq.return_value
            mock_client.chat.completions.create.return_value = _make_mock_response(
                "Hello!"
            )
            from amarooi.utils.llm import GroqClientWrapper

            wrapper = GroqClientWrapper()
            result = wrapper.generate_completion(
                [{"role": "user", "content": "hi"}]
            )
        assert result == "Hello!"

    def test_authentication_error_raises_configuration_error(self) -> None:
        import groq as groq_lib

        settings = _make_settings_mock()
        with (
            patch("amarooi.utils.llm.get_settings", return_value=settings),
            patch("amarooi.utils.llm.groq.Groq") as MockGroq,
        ):
            mock_client = MockGroq.return_value
            mock_client.chat.completions.create.side_effect = (
                groq_lib.AuthenticationError(
                    message="invalid key",
                    response=MagicMock(status_code=401),
                    body={},
                )
            )
            from amarooi.utils.llm import GroqClientWrapper

            wrapper = GroqClientWrapper()
            with pytest.raises(ConfigurationError):
                wrapper.generate_completion([{"role": "user", "content": "hi"}])

    def test_rate_limit_retries_then_raises(self) -> None:
        import groq as groq_lib

        settings = _make_settings_mock(max_retries=2)
        with (
            patch("amarooi.utils.llm.get_settings", return_value=settings),
            patch("amarooi.utils.llm.groq.Groq") as MockGroq,
            patch("amarooi.utils.llm.time.sleep"),  # don't actually sleep
        ):
            mock_client = MockGroq.return_value
            mock_client.chat.completions.create.side_effect = (
                groq_lib.RateLimitError(
                    message="rate limit",
                    response=MagicMock(status_code=429),
                    body={},
                )
            )
            from amarooi.utils.llm import GroqClientWrapper

            wrapper = GroqClientWrapper()
            with pytest.raises(LLMExecutionError):
                wrapper.generate_completion([{"role": "user", "content": "hi"}])

        assert mock_client.chat.completions.create.call_count == 2

    def test_rate_limit_succeeds_on_retry(self) -> None:
        import groq as groq_lib

        settings = _make_settings_mock(max_retries=3)
        with (
            patch("amarooi.utils.llm.get_settings", return_value=settings),
            patch("amarooi.utils.llm.groq.Groq") as MockGroq,
            patch("amarooi.utils.llm.time.sleep"),
        ):
            mock_client = MockGroq.return_value
            rate_err = groq_lib.RateLimitError(
                message="rate limit",
                response=MagicMock(status_code=429),
                body={},
            )
            mock_client.chat.completions.create.side_effect = [
                rate_err,
                _make_mock_response("recovered"),
            ]
            from amarooi.utils.llm import GroqClientWrapper

            wrapper = GroqClientWrapper()
            result = wrapper.generate_completion([{"role": "user", "content": "hi"}])

        assert result == "recovered"

    def test_generic_api_error_raises_llm_execution_error(self) -> None:
        import groq as groq_lib

        settings = _make_settings_mock()
        with (
            patch("amarooi.utils.llm.get_settings", return_value=settings),
            patch("amarooi.utils.llm.groq.Groq") as MockGroq,
        ):
            mock_client = MockGroq.return_value
            mock_resp = MagicMock()
            mock_resp.status_code = 500
            mock_client.chat.completions.create.side_effect = groq_lib.APIStatusError(
                message="server error",
                response=mock_resp,
                body={},
            )
            from amarooi.utils.llm import GroqClientWrapper

            wrapper = GroqClientWrapper()
            with pytest.raises(LLMExecutionError):
                wrapper.generate_completion([{"role": "user", "content": "hi"}])


class TestGroqClientWrapperStructuredJSON:
    """Tests for generate_structured_json()."""

    class _Schema(BaseModel):
        name: str
        value: int

    def test_successful_structured_json(self) -> None:
        settings = _make_settings_mock()
        with (
            patch("amarooi.utils.llm.get_settings", return_value=settings),
            patch("amarooi.utils.llm.groq.Groq") as MockGroq,
        ):
            mock_client = MockGroq.return_value
            mock_client.chat.completions.create.return_value = _make_mock_response(
                json.dumps({"name": "test", "value": 42})
            )
            from amarooi.utils.llm import GroqClientWrapper

            wrapper = GroqClientWrapper()
            result = wrapper.generate_structured_json(
                [{"role": "user", "content": "give json"}],
                self._Schema,
            )
        assert result.name == "test"
        assert result.value == 42

    def test_invalid_json_raises_manifest_validation_error(self) -> None:
        settings = _make_settings_mock()
        with (
            patch("amarooi.utils.llm.get_settings", return_value=settings),
            patch("amarooi.utils.llm.groq.Groq") as MockGroq,
        ):
            mock_client = MockGroq.return_value
            mock_client.chat.completions.create.return_value = _make_mock_response(
                "not valid json {{{"
            )
            from amarooi.utils.llm import GroqClientWrapper

            wrapper = GroqClientWrapper()
            with pytest.raises(ManifestValidationError):
                wrapper.generate_structured_json(
                    [{"role": "user", "content": "give json"}],
                    self._Schema,
                )

    def test_schema_mismatch_raises_manifest_validation_error(self) -> None:
        settings = _make_settings_mock()
        with (
            patch("amarooi.utils.llm.get_settings", return_value=settings),
            patch("amarooi.utils.llm.groq.Groq") as MockGroq,
        ):
            mock_client = MockGroq.return_value
            # "value" should be an int but we return a string that can't coerce
            mock_client.chat.completions.create.return_value = _make_mock_response(
                json.dumps({"name": "ok", "value": "not-an-int"})
            )
            from amarooi.utils.llm import GroqClientWrapper

            wrapper = GroqClientWrapper()
            with pytest.raises(ManifestValidationError):
                wrapper.generate_structured_json(
                    [{"role": "user", "content": "give json"}],
                    self._Schema,
                )
