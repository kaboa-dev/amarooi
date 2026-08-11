"""Domain exception hierarchy for the Amarooi framework.

This module defines all custom exceptions used across the Amarooi codebase,
ensuring consistent error handling and clear error semantics.
"""


class AmarooiException(Exception):
    """Base class for all domain errors within Amarooi.

    All custom exceptions in the framework inherit from this class,
    enabling callers to catch any Amarooi-specific error with a single
    ``except AmarooiException`` clause.
    """


class ConfigurationError(AmarooiException):
    """Raised when environment or configuration validation fails.

    Examples include missing required environment variables, invalid
    API keys, or unsupported configuration values.
    """


class LLMExecutionError(AmarooiException):
    """Raised when Groq API calls fail after all retry attempts are exhausted.

    Attributes:
        status_code: The HTTP status code returned by the API, if available.
        prompt_context: Metadata about the prompt that triggered the error,
            such as message count or model name.
    """

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        prompt_context: dict | None = None,
    ) -> None:
        """Initialise the exception.

        Args:
            message: Human-readable description of the failure.
            status_code: HTTP status code from the API response, if any.
            prompt_context: Arbitrary metadata about the prompt that failed.
        """
        super().__init__(message)
        self.status_code: int | None = status_code
        self.prompt_context: dict = prompt_context or {}


class ManifestValidationError(AmarooiException):
    """Raised when JSON logic manifest payloads fail validation.

    This exception is raised when a manifest cannot be parsed as valid JSON
    or when its structure does not conform to the expected Pydantic schema.
    """


class TranspilationError(AmarooiException):
    """Base error for transpilation syntax or AST generation failures.

    Subclass this exception to represent more specific transpilation errors
    such as unsupported operator types or malformed AST nodes.
    """
