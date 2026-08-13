"""COBOL target transpiler generator for the Amarooi framework.

Generates ANSI COBOL / IBM Enterprise COBOL source from a
:class:`~amarooi.planner.schemas.LogicManifest`.
"""

from __future__ import annotations

from amarooi.core.transpiler.base import BaseTargetTranspiler
from amarooi.planner.schemas import LogicManifest


class CobolTranspiler(BaseTargetTranspiler):
    """Generate ANSI COBOL / IBM Enterprise COBOL source code.

    Produces all four standard COBOL divisions:

    * ``IDENTIFICATION DIVISION`` – program metadata.
    * ``ENVIRONMENT DIVISION``    – configuration section stub.
    * ``DATA DIVISION``           – ``WORKING-STORAGE SECTION`` with ``01``
      level variables mapped from the manifest's state matrix.
    * ``PROCEDURE DIVISION``      – ``EVALUATE`` / ``IF`` validation gates
      derived from the manifest's invariants and logic gates.
    """

    target_name = "cobol"

    def generate(self, manifest: LogicManifest) -> str:
        """Generate COBOL source from *manifest*.

        Args:
            manifest: A validated :class:`~amarooi.planner.schemas.LogicManifest`.

        Returns:
            A string containing complete COBOL source code.
        """
        program_id = manifest.meta.project_name.replace(" ", "-").upper()
        lines: list[str] = []

        # IDENTIFICATION DIVISION
        lines += [
            "       IDENTIFICATION DIVISION.",
            f"       PROGRAM-ID. {program_id}.",
            f"       AUTHOR. AMAROOI-GENERATED.",
            "      *",
            f"      * {manifest.context.problem_statement}",
            "      *",
        ]

        # ENVIRONMENT DIVISION
        lines += [
            "       ENVIRONMENT DIVISION.",
            "       CONFIGURATION SECTION.",
            "       SOURCE-COMPUTER. IBM-ENTERPRISE.",
            "       OBJECT-COMPUTER. IBM-ENTERPRISE.",
            "      *",
        ]

        # DATA DIVISION – WORKING-STORAGE SECTION
        lines += [
            "       DATA DIVISION.",
            "       WORKING-STORAGE SECTION.",
        ]
        for i, var in enumerate(manifest.state_matrix.variables, start=1):
            cobol_name = var.name.replace("_", "-").upper()
            cobol_type = self._map_type(var.type)
            lines.append(f"       01  WS-{cobol_name} {cobol_type}.")
        lines.append("      *")

        # PROCEDURE DIVISION
        lines += [
            "       PROCEDURE DIVISION.",
            "       MAIN-PARA.",
        ]

        # Invariant validation gates
        for inv in manifest.state_matrix.invariants:
            lines += [
                f"           *> Invariant: {inv}",
                "           EVALUATE TRUE",
                f"               WHEN NOT ({inv})",
                "                   DISPLAY 'INVARIANT VIOLATION'",
                "                   STOP RUN",
                "           END-EVALUATE",
            ]

        # Logic gates
        for gate in manifest.logic_gates:
            lines += [
                f"           *> Gate {gate.gate_id}",
                f"           IF {gate.condition}",
                f"               {gate.on_true}",
                "           ELSE",
                f"               {gate.on_false}",
                "           END-IF",
            ]

        lines += [
            "           STOP RUN.",
            "       END PROGRAM.",
        ]

        return "\n".join(lines)

    @staticmethod
    def _map_type(python_type: str) -> str:
        """Map a Python type annotation to a COBOL picture clause."""
        mapping: dict[str, str] = {
            "int": "PIC S9(9) COMP",
            "float": "PIC S9(9)V99 COMP-3",
            "str": "PIC X(100)",
            "bool": "PIC 9(1)",
        }
        return mapping.get(python_type.lower(), "PIC X(100)")
