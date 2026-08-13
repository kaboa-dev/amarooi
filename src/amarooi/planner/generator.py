"""Natural Pseudocode Generator for the Amarooi framework.

This module provides :class:`NaturalLogicGenerator`, which converts validated
interview answers collected by :class:`~amarooi.planner.architect.SDLCArchitect`
into ``.amarooi`` natural pseudocode files, and :class:`WorkspaceManager`, which
manages the spec workspace directory where those files are saved.

Example::

    from amarooi.planner.generator import NaturalLogicGenerator, WorkspaceManager

    wm = WorkspaceManager()
    gen = NaturalLogicGenerator(workspace=wm)
    path = gen.generate(component_name="rate_limiter", answers={...})
"""

from __future__ import annotations

from typing import Any

from amarooi.core.workspace import WorkspaceManager

# ---------------------------------------------------------------------------
# NaturalLogicGenerator
# ---------------------------------------------------------------------------

# Keys expected in the *answers* dict produced by SDLCArchitect per component.
_KEY_INPUTS = "inputs_outputs"
_KEY_STATE = "state_variables"
_KEY_STEPS = "execution_steps"
_KEY_EDGE = "edge_cases"


class NaturalLogicGenerator:
    """Convert interview answers into ``.amarooi`` natural pseudocode files.

    The generator takes the structured dictionary produced for each component
    by :class:`~amarooi.planner.architect.SDLCArchitect` and renders it into the
    canonical ``.amarooi`` DSL format before saving it via the
    :class:`WorkspaceManager`.

    Attributes:
        workspace: The :class:`WorkspaceManager` used to persist generated files.
    """

    def __init__(self, workspace: WorkspaceManager | None = None) -> None:
        """Initialise the generator.

        Args:
            workspace: Optional :class:`WorkspaceManager`.  A default instance
                (targeting ``specs/``) is created when *None*.
        """
        self.workspace: WorkspaceManager = workspace or WorkspaceManager()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def render(self, component_name: str, answers: dict[str, Any]) -> str:
        """Render interview answers as ``.amarooi`` pseudocode text.

        The generated text follows this structure::

            Component: <component_name>

            Initialize:
              Inputs/Outputs: <inputs_outputs>
              State: <state_variables>

            When <component_name> runs:
              Step 1: <first step>
              Step 2: <second step>
              ...

            Edge Cases:
              If <case>: End

        Args:
            component_name: Logical name of the component.
            answers: Mapping of interview answer keys to their values.  Expected
                keys are ``"inputs_outputs"``, ``"state_variables"``,
                ``"execution_steps"``, and ``"edge_cases"``.

        Returns:
            A formatted ``.amarooi`` pseudocode string.
        """
        inputs_outputs: str = answers.get(_KEY_INPUTS, "").strip()
        state_variables: str = answers.get(_KEY_STATE, "").strip()
        raw_steps: Any = answers.get(_KEY_STEPS, "")
        raw_edge: Any = answers.get(_KEY_EDGE, "")

        steps: list[str] = _to_lines(raw_steps)
        edge_cases: list[str] = _to_lines(raw_edge)

        lines: list[str] = [
            f"Component: {component_name}",
            "",
            "Initialize:",
            f"  Inputs/Outputs: {inputs_outputs}" if inputs_outputs else "  Inputs/Outputs: (none)",
            f"  State: {state_variables}" if state_variables else "  State: (none)",
            "",
            f"When {component_name} runs:",
        ]

        if steps:
            for idx, step in enumerate(steps, start=1):
                lines.append(f"  Step {idx}: {step.strip()}")
        else:
            lines.append("  (no steps defined)")

        if edge_cases:
            lines.append("")
            lines.append("Edge Cases:")
            for case in edge_cases:
                lines.append(f"  If {case.strip()}: End")

        lines.append("")  # trailing newline
        return "\n".join(lines)

    def generate(self, component_name: str, answers: dict[str, Any]) -> Path:
        """Render and persist the ``.amarooi`` file for a component.

        Args:
            component_name: Logical name of the component.
            answers: Interview answers for this component.

        Returns:
            The :class:`~pathlib.Path` of the written ``.amarooi`` file.
        """
        content = self.render(component_name, answers)
        return self.workspace.write(component_name, content)

    def generate_all(
        self,
        components: dict[str, dict[str, Any]],
    ) -> dict[str, Path]:
        """Generate ``.amarooi`` files for multiple components.

        Args:
            components: Mapping of component name → interview answers.

        Returns:
            Mapping of component name → written file path.
        """
        return {name: self.generate(name, answers) for name, answers in components.items()}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _to_lines(value: Any) -> list[str]:
    """Normalise a value to a list of non-empty strings.

    Accepts a pre-split :class:`list`, or a newline/comma-delimited
    :class:`str`.

    Args:
        value: Raw interview answer value.

    Returns:
        A list of stripped, non-empty strings.
    """
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        # Try newlines first, fall back to commas.
        lines = value.splitlines() if "\n" in value else value.split(",")
        return [line.strip() for line in lines if line.strip()]
    return []
