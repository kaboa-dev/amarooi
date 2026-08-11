"""Manifest loading, validation, and serialization utilities."""

from __future__ import annotations

from pathlib import Path

from pydantic import ValidationError

from amarooi.core.exceptions import ManifestValidationError
from amarooi.planner.schemas import LogicManifest


class ManifestEngine:
    """Engine for reading and writing visual logic manifests."""

    @staticmethod
    def load_manifest(path: str | Path) -> LogicManifest:
        """Load and validate a logic manifest from disk.

        Args:
            path: Absolute or relative filesystem path to an ``.amarooi.json``
                manifest file.

        Returns:
            The parsed and validated manifest instance.

        Raises:
            ManifestValidationError: If the file cannot be read or the payload
                does not conform to :class:`LogicManifest`.
        """
        manifest_path = Path(path)
        try:
            raw_json = manifest_path.read_text(encoding="utf-8")
        except OSError as exc:
            raise ManifestValidationError(
                f"Failed to read manifest from '{manifest_path}': {exc}"
            ) from exc

        return ManifestEngine.validate_raw_json(raw_json)

    @staticmethod
    def save_manifest(manifest: LogicManifest, path: str | Path) -> None:
        """Serialize a manifest to disk using two-space indentation.

        Args:
            manifest: Validated manifest instance to serialize.
            path: Destination filesystem path.

        Raises:
            ManifestValidationError: If the manifest cannot be written to disk.
        """
        manifest_path = Path(path)
        try:
            manifest_path.write_text(
                f"{manifest.model_dump_json(indent=2)}\n",
                encoding="utf-8",
            )
        except OSError as exc:
            raise ManifestValidationError(
                f"Failed to write manifest to '{manifest_path}': {exc}"
            ) from exc

    @staticmethod
    def validate_raw_json(raw_json: str) -> LogicManifest:
        """Validate raw JSON text against the logic manifest schema.

        Args:
            raw_json: Raw JSON manifest text, typically produced by an LLM.

        Returns:
            A validated :class:`LogicManifest` instance.

        Raises:
            ManifestValidationError: If the text is not valid JSON or fails
                schema validation.
        """
        try:
            return LogicManifest.model_validate_json(raw_json)
        except ValidationError as exc:
            raise ManifestValidationError(
                f"Failed to validate logic manifest JSON: {exc}"
            ) from exc
