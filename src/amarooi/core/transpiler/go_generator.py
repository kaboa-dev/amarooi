"""Go target transpiler generator for the Amarooi framework.

Generates idiomatic Go source code from a
:class:`~amarooi.planner.schemas.LogicManifest`.
"""

from __future__ import annotations

from amarooi.core.transpiler.base import BaseTargetTranspiler
from amarooi.planner.schemas import LogicManifest


class GoTranspiler(BaseTargetTranspiler):
    """Generate idiomatic Go source code.

    Produces:

    * A ``package main`` declaration.
    * A ``State`` struct whose fields are derived from the manifest's state
      matrix variables.
    * A function with multi-return ``(Result, error)`` signature.
    * Strict invariant checks returning ``fmt.Errorf`` on violation.
    * ``if/else`` logic gates for each manifest gate.
    """

    target_name = "go"

    def generate(self, manifest: LogicManifest) -> str:
        """Generate Go source from *manifest*.

        Args:
            manifest: A validated :class:`~amarooi.planner.schemas.LogicManifest`.

        Returns:
            A string containing complete Go source code.
        """
        pkg = _go_ident(manifest.meta.project_name)
        fn_name = _go_exported(manifest.meta.project_name)
        lines: list[str] = [
            f"// {manifest.context.problem_statement}",
            "package main",
            "",
            'import "fmt"',
            "",
        ]

        # State struct
        lines += ["// State holds the input state variables.", "type State struct {"]
        for var in manifest.state_matrix.variables:
            go_name = _go_exported(var.name)
            go_type = self._map_type(var.type)
            lines.append(f"\t{go_name} {go_type} // {var.description}")
        lines += ["}", ""]

        # Result type alias
        lines += [
            "// Result is the return value of the operation.",
            "type Result = string",
            "",
        ]

        # Function signature
        params = ", ".join(
            f"{_go_ident(v.name)} {self._map_type(v.type)}"
            for v in manifest.state_matrix.variables
        )
        lines += [
            f"// {fn_name} executes the {pkg} logic.",
            f"func {fn_name}({params}) (Result, error) {{",
        ]

        # Invariant checks
        for inv in manifest.state_matrix.invariants:
            lines += [
                f"\t// Invariant: {inv}",
                f"\tif !({inv}) {{",
                f'\t\treturn "", fmt.Errorf("invariant violated: {inv}")',
                "\t}",
            ]

        # Logic gates
        for gate in manifest.logic_gates:
            lines += [
                f"\t// Gate {gate.gate_id}",
                f"\tif {gate.condition} {{",
                f'\t\treturn "{gate.on_true}", nil',
                "\t} else {",
                f'\t\treturn "{gate.on_false}", nil',
                "\t}",
            ]

        lines += [
            "}",
            "",
            "func main() {}",
        ]

        return "\n".join(lines)

    @staticmethod
    def _map_type(python_type: str) -> str:
        """Map a Python type annotation to a Go type."""
        mapping: dict[str, str] = {
            "int": "int",
            "float": "float64",
            "str": "string",
            "bool": "bool",
        }
        return mapping.get(python_type.lower(), "interface{}")


def _go_ident(name: str) -> str:
    """Return a lowercase Go identifier from *name*."""
    return name.replace(" ", "_").replace("-", "_").lower()


def _go_exported(name: str) -> str:
    """Return a PascalCase exported Go identifier from *name*."""
    parts = name.replace("_", " ").replace("-", " ").split()
    return "".join(p.capitalize() for p in parts)
