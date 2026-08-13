"""Abstract base extractor for the reverse logic extraction framework."""

from __future__ import annotations

from abc import ABC, abstractmethod

from amarooi.core.spec import SpecContract


class BaseExtractor(ABC):
    """Abstract base class for all language-specific logic extractors.

    Subclasses parse raw source code strings and return a structured
    :class:`~amarooi.core.spec.SpecContract` object.

    Each extractor must extract:

    * Component metadata & descriptions
    * Input/Output parameters with type signatures
    * Mutable state variables (state registers)
    * Execution flow steps
    * Pre/post-conditions and invariant boundaries
    """

    @abstractmethod
    def extract(self, source_code: str) -> SpecContract:
        """Parse *source_code* and return a validated :class:`SpecContract`.

        Args:
            source_code: Raw source code string to analyse.

        Returns:
            A fully-populated :class:`SpecContract` instance.
        """
