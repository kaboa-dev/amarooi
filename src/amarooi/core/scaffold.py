"""Multi-File Component Scaffolding Engine.

Manages complex, multi-component software systems by:

1. Generating a root ``amarooi.json`` system manifest that links individual
   component ``.amarooi`` specification files.
2. Enforcing cross-file interface contracts: if component A declares an output
   that component B consumes, both specs must agree on the type and name.
3. Detecting and reporting cascading contract mismatches before transpilation.
4. Auto-generating a system architecture document at
   ``docs/system_architecture.md``.

Example::

    from pathlib import Path
    from amarooi.core.scaffold import ScaffoldEngine, ComponentSpec

    engine = ScaffoldEngine(project_root=Path("my_project"))

    # Declare two components
    engine.add_component(
        ComponentSpec(name="db", path="logic/db.amarooi",
                      outputs={"user_record": "dict"})
    )
    engine.add_component(
        ComponentSpec(name="auth", path="logic/auth.amarooi",
                      inputs={"user_record": "dict"})
    )

    # Write manifest + detect mismatches
    engine.write_manifest()
    mismatches = engine.validate_contracts()
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class ComponentSpec:
    """Lightweight descriptor for a single ``.amarooi`` component.

    Attributes:
        name: Short identifier for the component (e.g. ``'auth'``).
        path: Relative path to the ``.amarooi`` specification file
              (e.g. ``'logic/auth.amarooi'``).
        inputs: Dict mapping input parameter names to their type strings.
        outputs: Dict mapping output parameter names to their type strings.
        description: Optional human-readable description.
    """

    name: str
    path: str
    inputs: dict[str, str] = field(default_factory=dict)
    outputs: dict[str, str] = field(default_factory=dict)
    description: str = ""


@dataclass
class ContractMismatch:
    """Describes a cross-component interface contract mismatch.

    Attributes:
        producer: Name of the component that produces the value.
        consumer: Name of the component that consumes the value.
        parameter: The parameter/output name that is mismatched.
        producer_type: The type declared by the producer.
        consumer_type: The type expected by the consumer.
        message: Human-readable description of the mismatch.
    """

    producer: str
    consumer: str
    parameter: str
    producer_type: str
    consumer_type: str
    message: str


# ---------------------------------------------------------------------------
# ScaffoldEngine
# ---------------------------------------------------------------------------


class ScaffoldEngine:
    """Generate and validate multi-component scaffold manifests.

    Args:
        project_root: Root directory of the project.  All relative paths in
            component specs are resolved against this directory.
        manifest_filename: Name of the root manifest file (default
            ``'amarooi.json'``).
    """

    def __init__(
        self,
        project_root: str | Path = ".",
        *,
        manifest_filename: str = "amarooi.json",
    ) -> None:
        self._root = Path(project_root)
        self._manifest_filename = manifest_filename
        self._components: dict[str, ComponentSpec] = {}

    # ------------------------------------------------------------------
    # Component registration
    # ------------------------------------------------------------------

    def add_component(self, spec: ComponentSpec) -> None:
        """Register a component specification.

        Args:
            spec: The :class:`ComponentSpec` to register.

        Raises:
            ValueError: If a component with the same name is already registered.
        """
        if spec.name in self._components:
            raise ValueError(
                f"Component '{spec.name}' is already registered. "
                "Use remove_component() first if you intend to replace it."
            )
        self._components[spec.name] = spec

    def remove_component(self, name: str) -> None:
        """Remove a registered component by name.

        Args:
            name: Component identifier to remove.
        """
        self._components.pop(name, None)

    @property
    def components(self) -> dict[str, ComponentSpec]:
        """Read-only view of the currently registered components."""
        return dict(self._components)

    # ------------------------------------------------------------------
    # Manifest serialisation
    # ------------------------------------------------------------------

    def build_manifest(self) -> dict[str, Any]:
        """Build and return the manifest as a plain Python dict.

        Returns:
            JSON-serialisable dict representing the ``amarooi.json`` manifest.
        """
        return {
            "version": "1.0",
            "components": [
                {
                    "name": spec.name,
                    "path": spec.path,
                    "description": spec.description,
                    "inputs": spec.inputs,
                    "outputs": spec.outputs,
                }
                for spec in self._components.values()
            ],
        }

    def write_manifest(self, dest: str | Path | None = None) -> Path:
        """Serialise the manifest to ``amarooi.json`` on disk.

        Args:
            dest: Destination file path.  Defaults to
                ``<project_root>/amarooi.json``.

        Returns:
            The resolved path where the manifest was written.
        """
        manifest_path = Path(dest) if dest else self._root / self._manifest_filename
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(
            json.dumps(self.build_manifest(), indent=2) + "\n",
            encoding="utf-8",
        )
        return manifest_path

    @classmethod
    def load_manifest(cls, path: str | Path) -> "ScaffoldEngine":
        """Reconstruct a :class:`ScaffoldEngine` from an existing manifest.

        Args:
            path: Path to the ``amarooi.json`` manifest file.

        Returns:
            Populated :class:`ScaffoldEngine` instance.

        Raises:
            ValueError: If the file cannot be parsed or is missing required fields.
        """
        manifest_path = Path(path)
        try:
            raw = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"Failed to load manifest from '{manifest_path}': {exc}") from exc

        engine = cls(project_root=manifest_path.parent)
        for comp in raw.get("components", []):
            engine.add_component(
                ComponentSpec(
                    name=comp["name"],
                    path=comp["path"],
                    inputs=comp.get("inputs", {}),
                    outputs=comp.get("outputs", {}),
                    description=comp.get("description", ""),
                )
            )
        return engine

    # ------------------------------------------------------------------
    # Cross-contract validation
    # ------------------------------------------------------------------

    def validate_contracts(self) -> list[ContractMismatch]:
        """Check for cross-component interface contract mismatches.

        For every parameter that a consumer component lists as an input, find
        the producer component whose output matches that parameter name and
        compare the declared types.  A mismatch is recorded when the types
        differ.

        Returns:
            List of :class:`ContractMismatch` objects (empty if all contracts
            are satisfied).
        """
        # Build an output index: param_name → {component_name: type_str}
        output_index: dict[str, dict[str, str]] = {}
        for comp in self._components.values():
            for param, type_str in comp.outputs.items():
                output_index.setdefault(param, {})[comp.name] = type_str

        mismatches: list[ContractMismatch] = []

        for consumer in self._components.values():
            for param, expected_type in consumer.inputs.items():
                if param not in output_index:
                    continue  # no producer found – not necessarily an error
                for producer_name, produced_type in output_index[param].items():
                    if producer_name == consumer.name:
                        continue  # self-reference
                    if produced_type != expected_type:
                        mismatches.append(
                            ContractMismatch(
                                producer=producer_name,
                                consumer=consumer.name,
                                parameter=param,
                                producer_type=produced_type,
                                consumer_type=expected_type,
                                message=(
                                    f"Contract mismatch on '{param}': "
                                    f"'{producer_name}' produces '{produced_type}' "
                                    f"but '{consumer.name}' expects '{expected_type}'."
                                ),
                            )
                        )

        return mismatches

    # ------------------------------------------------------------------
    # Documentation generation
    # ------------------------------------------------------------------

    def generate_architecture_doc(self, dest: str | Path | None = None) -> Path:
        """Generate a Markdown system architecture document.

        Args:
            dest: Destination file path.  Defaults to
                ``<project_root>/docs/system_architecture.md``.

        Returns:
            The resolved path where the document was written.
        """
        doc_path = Path(dest) if dest else self._root / "docs" / "system_architecture.md"
        doc_path.parent.mkdir(parents=True, exist_ok=True)

        lines: list[str] = [
            "# System Architecture\n",
            f"> Auto-generated by Amarooi ScaffoldEngine\n",
            "",
            "## Components\n",
        ]

        for spec in self._components.values():
            lines.append(f"### `{spec.name}`\n")
            if spec.description:
                lines.append(f"{spec.description}\n")
            lines.append(f"- **Spec file:** `{spec.path}`")
            if spec.inputs:
                inputs_str = ", ".join(f"`{k}: {v}`" for k, v in spec.inputs.items())
                lines.append(f"- **Inputs:** {inputs_str}")
            if spec.outputs:
                outputs_str = ", ".join(f"`{k}: {v}`" for k, v in spec.outputs.items())
                lines.append(f"- **Outputs:** {outputs_str}")
            lines.append("")

        # Contract validation summary
        mismatches = self.validate_contracts()
        if mismatches:
            lines.append("## ⚠️ Contract Mismatches\n")
            for m in mismatches:
                lines.append(f"- {m.message}")
            lines.append("")
        else:
            lines.append("## ✅ Contract Validation\n")
            lines.append("All cross-component interface contracts are satisfied.\n")

        doc_path.write_text("\n".join(lines), encoding="utf-8")
        return doc_path
