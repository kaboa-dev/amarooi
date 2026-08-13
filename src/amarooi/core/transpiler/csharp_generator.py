"""C# target transpiler generator for the Amarooi framework.

Generates modern C# 10/11 source code from a
:class:`~amarooi.planner.schemas.LogicManifest`.
"""

from __future__ import annotations

from amarooi.core.transpiler.base import BaseTargetTranspiler
from amarooi.planner.schemas import LogicManifest


class CSharpTranspiler(BaseTargetTranspiler):
    """Generate modern C# 10/11 source code.

    Produces:

    * A ``namespace`` block derived from the project name.
    * A ``record`` type whose properties map to state matrix variables.
    * A ``static`` method with ``ArgumentException`` guards for each invariant.
    * ``if/else`` logic gates for each manifest gate.
    """

    target_name = "csharp"

    def generate(self, manifest: LogicManifest) -> str:
        """Generate C# source from *manifest*.

        Args:
            manifest: A validated :class:`~amarooi.planner.schemas.LogicManifest`.

        Returns:
            A string containing complete C# source code.
        """
        ns = _pascal(manifest.meta.project_name)
        class_name = ns
        fn_name = "Execute"
        lines: list[str] = [
            f"// {manifest.context.problem_statement}",
            f"namespace {ns};",
            "",
        ]

        # State record
        record_props = ", ".join(
            f"{self._map_type(v.type)} {_pascal(v.name)}"
            for v in manifest.state_matrix.variables
        )
        lines += [
            f"public record State({record_props});",
            "",
            f"public static class {class_name}",
            "{",
        ]

        # Method signature
        params = ", ".join(
            f"{self._map_type(v.type)} {_camel(v.name)}"
            for v in manifest.state_matrix.variables
        )
        lines += [
            f"    public static string {fn_name}({params})",
            "    {",
        ]

        # Invariant guards
        for inv in manifest.state_matrix.invariants:
            lines += [
                f"        // Invariant: {inv}",
                f"        if (!({inv}))",
                "        {",
                f'            throw new ArgumentException("Invariant violated: {inv}");',
                "        }",
            ]

        # Logic gates
        for gate in manifest.logic_gates:
            lines += [
                f"        // Gate {gate.gate_id}",
                f"        if ({gate.condition})",
                "        {",
                f'            return "{gate.on_true}";',
                "        }",
                "        else",
                "        {",
                f'            return "{gate.on_false}";',
                "        }",
            ]

        lines += [
            "    }",
            "}",
        ]

        return "\n".join(lines)

    @staticmethod
    def _map_type(python_type: str) -> str:
        """Map a Python type annotation to a C# type."""
        mapping: dict[str, str] = {
            "int": "int",
            "float": "double",
            "str": "string",
            "bool": "bool",
        }
        return mapping.get(python_type.lower(), "object")


def _pascal(name: str) -> str:
    """Return a PascalCase identifier from *name*."""
    parts = name.replace("_", " ").replace("-", " ").split()
    return "".join(p.capitalize() for p in parts)


def _camel(name: str) -> str:
    """Return a camelCase identifier from *name*."""
    parts = name.replace("_", " ").replace("-", " ").split()
    return parts[0].lower() + "".join(p.capitalize() for p in parts[1:])
