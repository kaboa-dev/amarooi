"""SDLC Architect Wizard for the Amarooi framework.

This module provides :class:`SDLCArchitect`, an interactive terminal wizard that
guides developers through a three-phase Software Development Life Cycle (SDLC)
interview for a high-level project prompt:

1. **Domain Analysis & Architecture** – The LLM decomposes the prompt into a
   list of logical components (e.g. ``api_fetcher``, ``rate_limiter``).
2. **Component Logic Interview** – For every component the user is asked guided
   questions about inputs/outputs, state, and execution steps using ``rich``.
3. **Testing Strategy** – The user defines edge cases for each component.

After the interview, :class:`~amarooi.planner.generator.NaturalLogicGenerator`
converts all collected answers into ``.amarooi`` pseudocode files saved in the
workspace.

Example::

    from amarooi.planner.architect import SDLCArchitect

    architect = SDLCArchitect()
    paths = architect.run("Build a weather dashboard")
"""

from __future__ import annotations

import json
import logging
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

from amarooi.core.config import get_settings
from amarooi.core.exceptions import AmarooiException
from amarooi.planner.generator import NaturalLogicGenerator, WorkspaceManager
from amarooi.utils.llm import GroqClientWrapper

logger = logging.getLogger(__name__)

_console = Console()

# System prompt used during Phase 1 (architecture decomposition).
_ARCHITECTURE_SYSTEM_PROMPT = """\
You are an expert software architect assistant for the Amarooi framework.
Your task is to analyse a high-level project description and propose a list of
logical software components (modules / services) that together implement the project.

Return ONLY a JSON array of component name strings.
Each name must be a concise snake_case identifier, for example:
["api_fetcher", "ui_state", "rate_limiter", "error_handler"]

Return ONLY the JSON array — no explanations, no Markdown fences.
"""


class SDLCArchitect:
    """Interactive SDLC Architect Wizard.

    The wizard orchestrates a three-phase terminal interview, collects answers,
    and delegates file generation to :class:`~amarooi.planner.generator.NaturalLogicGenerator`.

    Attributes:
        _client: LLM wrapper used for architecture decomposition.
        _generator: Generator that converts answers to ``.amarooi`` files.
        _console: Rich console used for all terminal output.
    """

    def __init__(
        self,
        client: GroqClientWrapper | None = None,
        workspace: WorkspaceManager | None = None,
    ) -> None:
        """Initialise the SDLC Architect.

        Args:
            client: Optional pre-configured
                :class:`~amarooi.utils.llm.GroqClientWrapper`.  A default
                instance is created when *None*.
            workspace: Optional :class:`~amarooi.planner.generator.WorkspaceManager`
                that determines where ``.amarooi`` files are saved.  Defaults to
                ``logic/`` relative to the current working directory.
        """
        self._settings = get_settings()
        self._client: GroqClientWrapper = client or GroqClientWrapper()
        self._generator = NaturalLogicGenerator(workspace=workspace or WorkspaceManager())

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self, prompt: str) -> dict[str, Any]:
        """Execute the full three-phase SDLC interview.

        Args:
            prompt: High-level project description supplied by the user (e.g.
                ``"Build a weather dashboard"``).

        Returns:
            A mapping of component names to their written ``.amarooi`` file
            paths (as strings).

        Raises:
            AmarooiException: If the LLM fails to return a valid component list
                during Phase 1.
        """
        _console.print(
            Panel(
                "[bold cyan]Amarooi · SDLC Architect Wizard[/bold cyan]\n"
                f"[dim]Project: {prompt}[/dim]",
                expand=False,
            )
        )

        # ── Phase 1: Architecture ────────────────────────────────────────
        components = self._phase_architecture(prompt)

        # ── Phase 2 & 3: Component interviews ────────────────────────────
        all_answers: dict[str, dict[str, Any]] = {}
        for component in components:
            all_answers[component] = self._phase_interview(component)

        # ── Generate .amarooi files ───────────────────────────────────────
        _console.print(
            Panel("[bold green]Generating .amarooi files…[/bold green]", expand=False)
        )
        written = self._generator.generate_all(all_answers)

        result: dict[str, Any] = {}
        for name, path in written.items():
            _console.print(f"  [bold green]✓[/bold green] {name} → [bold]{path}[/bold]")
            result[name] = str(path)

        _console.print(
            Panel(
                f"[bold green]Done![/bold green]  {len(result)} component(s) written.",
                expand=False,
            )
        )
        return result

    # ------------------------------------------------------------------
    # Phase implementations
    # ------------------------------------------------------------------

    def _phase_architecture(self, prompt: str) -> list[str]:
        """Phase 1: Ask the LLM to decompose *prompt* into components.

        Args:
            prompt: High-level project description.

        Returns:
            Ordered list of snake_case component name strings.

        Raises:
            AmarooiException: If the LLM response cannot be parsed as a JSON
                array of strings.
        """
        _console.print(
            Panel(
                "[bold yellow]Phase 1 — Domain Analysis & Architecture[/bold yellow]",
                expand=False,
            )
        )
        _console.print("[dim]Consulting the LLM to decompose your project…[/dim]")

        messages = [
            {"role": "system", "content": _ARCHITECTURE_SYSTEM_PROMPT},
            {"role": "user", "content": f"Project description: {prompt}"},
        ]

        try:
            raw = self._client.generate_completion(
                messages=messages,
                model=self._settings.REASONING_MODEL,
                temperature=0.2,
                max_tokens=512,
            )
        except AmarooiException:
            logger.error("SDLCArchitect: LLM call failed during Phase 1.")
            raise

        components = self._parse_component_list(raw)

        _console.print(
            f"[bold]Proposed components:[/bold] "
            + ", ".join(f"[cyan]{c}[/cyan]" for c in components)
        )
        return components

    def _phase_interview(self, component: str) -> dict[str, Any]:
        """Phases 2 & 3: Conduct the guided interview for one component.

        Args:
            component: Snake_case component name.

        Returns:
            A dictionary with keys ``inputs_outputs``, ``state_variables``,
            ``execution_steps``, and ``edge_cases``.
        """
        _console.print(
            Panel(
                f"[bold yellow]Phase 2 — Component Logic Interview[/bold yellow]\n"
                f"[bold]Component:[/bold] [cyan]{component}[/cyan]",
                expand=False,
            )
        )

        inputs_outputs = Prompt.ask(
            f"  [bold]What are the inputs and outputs for [cyan]{component}[/cyan]?[/bold]"
        )
        state_variables = Prompt.ask(
            f"  [bold]What state variables / data registers need to be tracked?[/bold]"
        )
        execution_steps = Prompt.ask(
            f"  [bold]Step-by-step, what is the core execution loop "
            f"when [cyan]{component}[/cyan] runs?[/bold]\n"
            f"  [dim](Separate steps with commas or newlines)[/dim]"
        )

        # Phase 3: Edge cases
        _console.print(
            Panel(
                f"[bold yellow]Phase 3 — Testing Strategy[/bold yellow]\n"
                f"[bold]Component:[/bold] [cyan]{component}[/cyan]",
                expand=False,
            )
        )
        edge_cases = Prompt.ask(
            f"  [bold]What edge cases should be handled for [cyan]{component}[/cyan]?[/bold]\n"
            f"  [dim](e.g. 'API times out', 'empty input' — separate with commas)[/dim]"
        )

        return {
            "inputs_outputs": inputs_outputs,
            "state_variables": state_variables,
            "execution_steps": execution_steps,
            "edge_cases": edge_cases,
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_component_list(raw: str) -> list[str]:
        """Parse the LLM response into a list of component name strings.

        Strips Markdown fences if present before attempting JSON parsing.

        Args:
            raw: Raw LLM response text expected to be a JSON array.

        Returns:
            A non-empty list of component name strings.

        Raises:
            AmarooiException: If the response cannot be parsed or is empty.
        """
        # Strip optional Markdown fences.
        text = raw.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            # Drop first and last fence lines.
            text = "\n".join(lines[1:-1]).strip()

        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:
            raise AmarooiException(
                f"SDLCArchitect: could not parse component list from LLM response: {exc}\n"
                f"Raw response: {raw!r}"
            ) from exc

        if not isinstance(parsed, list) or not parsed:
            raise AmarooiException(
                "SDLCArchitect: expected a non-empty JSON array of component names, "
                f"got: {parsed!r}"
            )

        return [str(item) for item in parsed]
