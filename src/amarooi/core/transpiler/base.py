"""Base class for Amarooi target transpiler generators."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import ClassVar

from amarooi.planner.schemas import LogicManifest

_REGISTRY: dict[str, type["BaseTargetTranspiler"]] = {}


class BaseTargetTranspiler(ABC):
    """Abstract base for all target language generators.

    Subclasses must declare :attr:`target_name` and implement
    :meth:`generate`.  Registration happens automatically on class
    definition via :meth:`__init_subclass__`.

    Example:
        >>> transpiler = BaseTargetTranspiler.for_target("cobol")
        >>> code = transpiler.generate(manifest)
    """

    target_name: ClassVar[str]

    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)
        if hasattr(cls, "target_name"):
            _REGISTRY[cls.target_name] = cls

    @classmethod
    def for_target(cls, target: str) -> "BaseTargetTranspiler":
        """Return an instance of the registered transpiler for *target*.

        Args:
            target: The canonical target language name (e.g. ``"cobol"``).

        Returns:
            An instance of the matching :class:`BaseTargetTranspiler` subclass.

        Raises:
            KeyError: If no transpiler is registered for *target*.
        """
        transpiler_cls = _REGISTRY[target]
        return transpiler_cls()

    @classmethod
    def registered_targets(cls) -> list[str]:
        """Return a sorted list of all registered target names."""
        return sorted(_REGISTRY)

    @abstractmethod
    def generate(self, manifest: LogicManifest) -> str:
        """Generate target language source code from *manifest*.

        Args:
            manifest: A validated :class:`~amarooi.planner.schemas.LogicManifest`.

        Returns:
            A string containing the generated source code.
        """
