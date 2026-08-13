"""Extractor factory registry.

:class:`ExtractorFactory` maps file extensions and language names to
:class:`~amarooi.core.extractor.base.BaseExtractor` implementations, allowing
language-specific extractors to be registered and dispatched at runtime.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from amarooi.core.extractor.base import BaseExtractor
from amarooi.core.extractor.python_extractor import PythonExtractor

if TYPE_CHECKING:
    pass


class ExtractorFactory:
    """Registry and factory for language-specific extractors.

    Pre-registered extractors:

    * ``".py"`` / ``"python"`` → :class:`~amarooi.core.extractor.python_extractor.PythonExtractor`

    Additional extractors can be registered at runtime via
    :meth:`register`.

    Example::

        factory = ExtractorFactory()
        extractor = factory.get_extractor(".py")
        spec = extractor.extract(source_code)
    """

    #: Default registry populated at class creation.
    _DEFAULT_REGISTRY: dict[str, type[BaseExtractor]] = {
        ".py": PythonExtractor,
        "python": PythonExtractor,
    }

    def __init__(self) -> None:
        self._registry: dict[str, type[BaseExtractor]] = dict(self._DEFAULT_REGISTRY)

    def register(self, key: str, extractor_cls: type[BaseExtractor]) -> None:
        """Register an extractor class for a file extension or language name.

        Args:
            key: File extension (e.g. ``".cob"``) or language name (e.g.
                ``"cobol"``).  The key is normalised to lower-case.
            extractor_cls: Concrete :class:`BaseExtractor` subclass.
        """
        self._registry[key.lower()] = extractor_cls

    def get_extractor(self, key: str) -> BaseExtractor:
        """Return an instantiated extractor for *key*.

        Args:
            key: File extension (e.g. ``".py"``) or language name (e.g.
                ``"python"``).  The key is normalised to lower-case.

        Returns:
            An instantiated :class:`BaseExtractor` implementation.

        Raises:
            KeyError: If no extractor is registered for *key*.
        """
        normalised = key.lower()
        extractor_cls = self._registry.get(normalised)
        if extractor_cls is None:
            supported = sorted(self._registry.keys())
            raise KeyError(
                f"No extractor registered for {key!r}. "
                f"Supported keys: {supported}"
            )
        return extractor_cls()

    @property
    def supported_keys(self) -> list[str]:
        """Return a sorted list of all registered extractor keys."""
        return sorted(self._registry.keys())
