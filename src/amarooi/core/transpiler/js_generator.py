"""JavaScript target transpiler generator for the Amarooi framework.

Generates ES6+ JavaScript (Node.js / browser) source from a
:class:`~amarooi.planner.schemas.LogicManifest`.
"""

from __future__ import annotations

from amarooi.core.transpiler.base import BaseTargetTranspiler
from amarooi.planner.schemas import LogicManifest


class JavaScriptTranspiler(BaseTargetTranspiler):
    """Generate ES6+ JavaScript source code.

    Produces an ``async`` function with:

    * Explicit ``TypeError`` throw conditions for each invariant.
    * ``if/else`` logic gates derived from the manifest.
    * Clean ``module.exports`` at the module boundary.
    """

    target_name = "javascript"

    def generate(self, manifest: LogicManifest) -> str:
        """Generate JavaScript source from *manifest*.

        Args:
            manifest: A validated :class:`~amarooi.planner.schemas.LogicManifest`.

        Returns:
            A string containing complete ES6+ JavaScript source code.
        """
        fn_name = _camel_case(manifest.meta.project_name)
        params = ", ".join(
            v.name for v in manifest.state_matrix.variables
        )
        lines: list[str] = [
            f"// {manifest.context.problem_statement}",
            "",
            f"async function {fn_name}({params}) {{",
        ]

        # Invariant checks
        for inv in manifest.state_matrix.invariants:
            lines += [
                f"  // Invariant: {inv}",
                f"  if (!({inv})) {{",
                f'    throw new TypeError("Invariant violated: {inv}");',
                "  }",
            ]

        # Logic gates
        for gate in manifest.logic_gates:
            lines += [
                f"  // Gate {gate.gate_id}",
                f"  if ({gate.condition}) {{",
                f"    return {gate.on_true};",
                "  } else {",
                f"    return {gate.on_false};",
                "  }",
            ]

        lines += [
            "}",
            "",
            f"module.exports = {{ {fn_name} }};",
            f"export default {fn_name};",
        ]

        return "\n".join(lines)


def _camel_case(name: str) -> str:
    """Convert a space- or underscore-separated *name* to camelCase."""
    parts = name.replace("_", " ").split()
    return parts[0].lower() + "".join(p.capitalize() for p in parts[1:])
