"""Production-ready Groq SDK wrapper for Amarooi.

This module provides :class:`GroqClientWrapper`, a resilient client that adds
exponential-backoff retry logic, structured-JSON output parsing, and consistent
error translation on top of the raw ``groq`` SDK.

Example:
    >>> from amarooi.utils.llm import GroqClientWrapper
    >>> client = GroqClientWrapper()
    >>> text = client.generate_completion([{"role": "user", "content": "hi"}])
"""

from __future__ import annotations

import json
import logging
import time
from typing import TypeVar

import groq

from amarooi.core.config import get_settings
from amarooi.core.exceptions import (
    ConfigurationError,
    LLMExecutionError,
    ManifestValidationError,
)

try:
    from pydantic import BaseModel, ValidationError
except ImportError as _exc:  # pragma: no cover
    raise ImportError("pydantic is required for GroqClientWrapper") from _exc

T = TypeVar("T", bound=BaseModel)

logger = logging.getLogger(__name__)

# Groq error types that warrant a retry with back-off.
_RETRYABLE_ERRORS = (
    groq.RateLimitError,
    groq.APIConnectionError,
    groq.InternalServerError,
)


class GroqClientWrapper:
    """Resilient wrapper around the Groq SDK client.

    Instantiating this class reads application settings once via
    :func:`~amarooi.core.config.get_settings` and creates a single
    ``groq.Groq`` client that is reused for all requests.

    Attributes:
        _client: The underlying ``groq.Groq`` SDK client.
        _settings: Cached application settings.
    """

    def __init__(self) -> None:
        """Initialise the wrapper and the underlying Groq client.

        Raises:
            ConfigurationError: If settings are invalid (propagated from
                :func:`~amarooi.core.config.get_settings`).
        """
        self._settings = get_settings()
        self._client = groq.Groq(
            api_key=self._settings.GROQ_API_KEY.get_secret_value(),
            timeout=self._settings.REQUEST_TIMEOUT,
            max_retries=0,  # We handle retries ourselves.
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate_completion(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float = 0.2,
        max_tokens: int = 4096,
    ) -> str:
        """Execute a chat completion request with automatic retries.

        Retries are attempted for transient errors (:class:`groq.RateLimitError`,
        :class:`groq.APIConnectionError`, :class:`groq.InternalServerError`)
        using exponential back-off.  Authentication failures are re-raised
        immediately as :class:`~amarooi.core.exceptions.ConfigurationError`.

        Args:
            messages: A list of role/content dicts following the OpenAI chat
                format, e.g. ``[{"role": "user", "content": "hello"}]``.
            model: Optional model override.  Defaults to
                ``Settings.DEFAULT_MODEL``.
            temperature: Sampling temperature (0.0 – 2.0).  Lower values
                produce more deterministic output.
            max_tokens: Maximum number of tokens to generate.

        Returns:
            The text content of the first choice returned by the model.

        Raises:
            ConfigurationError: If the API key is rejected
                (:class:`groq.AuthenticationError`).
            LLMExecutionError: If all retry attempts are exhausted or an
                unhandled API error occurs.
        """
        resolved_model = model or self._settings.DEFAULT_MODEL
        prompt_context = {
            "model": resolved_model,
            "message_count": len(messages),
        }

        last_exc: Exception | None = None
        for attempt in range(self._settings.MAX_RETRIES):
            try:
                response = self._client.chat.completions.create(
                    model=resolved_model,
                    messages=messages,  # type: ignore[arg-type]
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                return response.choices[0].message.content or ""

            except groq.AuthenticationError as exc:
                raise ConfigurationError(
                    "Groq API authentication failed.  "
                    "Verify that GROQ_API_KEY is correct."
                ) from exc

            except _RETRYABLE_ERRORS as exc:
                last_exc = exc
                wait = 2**attempt  # 1 s, 2 s, 4 s …
                logger.warning(
                    "Transient Groq error on attempt %d/%d: %s.  "
                    "Retrying in %d s.",
                    attempt + 1,
                    self._settings.MAX_RETRIES,
                    exc,
                    wait,
                )
                time.sleep(wait)

            except groq.APIError as exc:
                status_code: int | None = getattr(exc, "status_code", None)
                raise LLMExecutionError(
                    f"Groq API error: {exc}",
                    status_code=status_code,
                    prompt_context=prompt_context,
                ) from exc

        raise LLMExecutionError(
            f"Groq request failed after {self._settings.MAX_RETRIES} attempts.",
            prompt_context=prompt_context,
        ) from last_exc

    def generate_structured_json(
        self,
        messages: list[dict[str, str]],
        response_schema: type[T],
        model: str | None = None,
    ) -> T:
        """Execute a completion and parse the response into a Pydantic model.

        Uses ``response_format={"type": "json_object"}`` to instruct the model
        to emit valid JSON, then validates the output against *response_schema*.

        Args:
            messages: A list of role/content dicts following the OpenAI chat
                format.
            response_schema: A :class:`pydantic.BaseModel` subclass that
                defines the expected JSON schema.
            model: Optional model override.  Defaults to
                ``Settings.DEFAULT_MODEL``.

        Returns:
            A validated instance of *response_schema*.

        Raises:
            ManifestValidationError: If the model output cannot be parsed as
                JSON or fails Pydantic schema validation.
            ConfigurationError: If the API key is rejected.
            LLMExecutionError: If all retry attempts are exhausted or an
                unhandled API error occurs.
        """
        resolved_model = model or self._settings.DEFAULT_MODEL
        prompt_context = {
            "model": resolved_model,
            "message_count": len(messages),
            "schema": response_schema.__name__,
        }

        last_exc: Exception | None = None
        for attempt in range(self._settings.MAX_RETRIES):
            try:
                response = self._client.chat.completions.create(
                    model=resolved_model,
                    messages=messages,  # type: ignore[arg-type]
                    response_format={"type": "json_object"},
                    max_tokens=4096,
                )
                raw_content = response.choices[0].message.content or ""
                break

            except groq.AuthenticationError as exc:
                raise ConfigurationError(
                    "Groq API authentication failed.  "
                    "Verify that GROQ_API_KEY is correct."
                ) from exc

            except _RETRYABLE_ERRORS as exc:
                last_exc = exc
                wait = 2**attempt
                logger.warning(
                    "Transient Groq error on attempt %d/%d: %s.  "
                    "Retrying in %d s.",
                    attempt + 1,
                    self._settings.MAX_RETRIES,
                    exc,
                    wait,
                )
                time.sleep(wait)

            except groq.APIError as exc:
                status_code = getattr(exc, "status_code", None)
                raise LLMExecutionError(
                    f"Groq API error: {exc}",
                    status_code=status_code,
                    prompt_context=prompt_context,
                ) from exc
        else:
            raise LLMExecutionError(
                f"Groq request failed after {self._settings.MAX_RETRIES} attempts.",
                prompt_context=prompt_context,
            ) from last_exc

        try:
            data = json.loads(raw_content)
            return response_schema.model_validate(data)
        except (json.JSONDecodeError, ValidationError) as exc:
            raise ManifestValidationError(
                f"Failed to parse model output into {response_schema.__name__}: {exc}"
            ) from exc
