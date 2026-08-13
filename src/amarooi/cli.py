"""Command-line interface entry point for the Amarooi framework.

Exposes three sub-commands:

* ``amarooi plan``    – generate a ``.amarooi.json`` logic manifest.
* ``amarooi transpile`` – convert a manifest to Python source code.
* ``amarooi run``    – plan *and* transpile in a single pipeline.

Example:
    $ amarooi plan --prompt "Build an even/odd checker" --out logic.amarooi.json
    $ amarooi transpile --manifest logic.amarooi.json --out logic.py
    $ amarooi run --prompt "Build an even/odd checker" --out output.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel

from amarooi.core.exceptions import AmarooiException
from amarooi.core.state import PlannerSession
from amarooi.core.synthesis import SynthesisEngine, VaguePromptError
from amarooi.core.usage import UsageTracker
from amarooi.planner.architect import SDLCArchitect
from amarooi.planner.manifest import ManifestEngine
from amarooi.transpiler.engine import TranspilerEngine

_console = Console()
_err_console = Console(stderr=True)

_DEFAULT_MANIFEST_PATH = ".amarooi.json"


# ---------------------------------------------------------------------------
# Sub-command handlers
# ---------------------------------------------------------------------------


def _cmd_plan(args: argparse.Namespace) -> int:
    """Execute the ``plan`` sub-command.

    Generates a logic manifest from a natural-language prompt and writes it to
    the output path as ``.amarooi.json``.

    Args:
        args: Parsed argument namespace containing ``prompt`` and ``out``.

    Returns:
        Exit code: ``0`` on success, ``1`` on failure.
    """
    prompt: str = args.prompt or _prompt_interactively("Enter your system requirements")
    out_path = Path(args.out)

    _console.print(Panel("[bold cyan]Amarooi · Planning[/bold cyan]", expand=False))
    _console.print(f"[dim]Generating manifest → {out_path}[/dim]")

    try:
        session = PlannerSession()
        manifest = session.generate_manifest_from_prompt(prompt)
        ManifestEngine.save_manifest(manifest, out_path)
    except AmarooiException as exc:
        _err_console.print(f"[bold red]Error:[/bold red] {exc}")
        return 1

    _console.print(f"[bold green]✓[/bold green] Manifest saved to [bold]{out_path}[/bold]")
    return 0


def _cmd_transpile(args: argparse.Namespace) -> int:
    """Execute the ``transpile`` sub-command.

    Reads an existing manifest (JSON) **or** a hand-written ``.amarooi`` file
    and generates formatted Python source code.

    When ``--file`` points to a ``.amarooi`` natural-pseudocode file the
    transpiler reads it directly from disk and sends it to the LLM.  When
    ``--manifest`` is used the existing JSON manifest pipeline is followed.

    Args:
        args: Parsed argument namespace containing ``manifest``, ``file``,
            and ``out``.

    Returns:
        Exit code: ``0`` on success, ``1`` on failure.
    """
    _console.print(Panel("[bold cyan]Amarooi · Transpiling[/bold cyan]", expand=False))

    # ── Branch: direct .amarooi file bypass ───────────────────────────
    if getattr(args, "file", None):
        amarooi_path = Path(args.file)
        out_path = Path(args.out)
        _console.print(f"[dim]Reading .amarooi ← {amarooi_path}[/dim]")
        _console.print(f"[dim]Writing source   → {out_path}[/dim]")
        try:
            from amarooi.core.config import get_settings
            from amarooi.utils.llm import GroqClientWrapper

            pseudocode = amarooi_path.read_text(encoding="utf-8")
            settings = get_settings()
            client = GroqClientWrapper()
            messages = [
                {
                    "role": "system",
                    "content": (
                        "You are an expert Python engineer. "
                        "Convert the following Amarooi natural pseudocode into clean, "
                        "complete, type-annotated Python 3.10+ source code. "
                        "Return ONLY the source code — no explanations, no Markdown fences."
                    ),
                },
                {"role": "user", "content": pseudocode},
            ]
            raw = client.generate_completion(
                messages,
                model=settings.REASONING_MODEL,
                temperature=0.1,
                max_tokens=4096,
            )
            # Strip any accidental code fences from the response.
            import re as _re

            code = _re.sub(r"```[a-zA-Z0-9_\-]*\n?", "", raw).strip("` \n")
            out_path.write_text(code, encoding="utf-8")
        except AmarooiException as exc:
            _err_console.print(f"[bold red]Error:[/bold red] {exc}")
            return 1
        except OSError as exc:
            _err_console.print(f"[bold red]Error:[/bold red] {exc}")
            return 1

        _console.print(f"[bold green]✓[/bold green] Source written to [bold]{out_path}[/bold]")
        return 0

    # ── Branch: existing JSON manifest pipeline ────────────────────────
    manifest_path = Path(args.manifest)
    out_path = Path(args.out)
    _console.print(f"[dim]Reading manifest ← {manifest_path}[/dim]")
    _console.print(f"[dim]Writing source   → {out_path}[/dim]")

    try:
        engine = TranspilerEngine()
        engine.transpile_file(manifest_path, out_path)
    except AmarooiException as exc:
        _err_console.print(f"[bold red]Error:[/bold red] {exc}")
        return 1

    _console.print(f"[bold green]✓[/bold green] Source written to [bold]{out_path}[/bold]")
    return 0


def _cmd_architect(args: argparse.Namespace) -> int:
    """Execute the ``architect`` sub-command.

    Launches the full interactive SDLC Wizard powered by :class:`SDLCArchitect`.

    Args:
        args: Parsed argument namespace containing ``prompt``.

    Returns:
        Exit code: ``0`` on success, ``1`` on failure.
    """
    prompt: str = args.prompt or _prompt_interactively(
        "Describe your project at a high level"
    )

    try:
        architect = SDLCArchitect()
        architect.run(prompt)
    except AmarooiException as exc:
        _err_console.print(f"[bold red]Error:[/bold red] {exc}")
        return 1

    return 0


def _cmd_synthesize(args: argparse.Namespace) -> int:
    """Execute the ``synthesize`` sub-command.

    Stage 1 of the Two-Stage Spec Pipeline:

    * **Detailed prompt** → synthesises a ``.amarooi`` logic spec directly
      into ``logic/<slug>.amarooi`` without an interactive interview.
    * **Vague prompt** → prints guidance and exits with code 2, directing the
      user to run ``amarooi architect`` instead.

    Args:
        args: Parsed argument namespace containing ``prompt`` and ``out_dir``.

    Returns:
        Exit code: ``0`` on success, ``1`` on LLM failure, ``2`` when the
        prompt is too vague.
    """
    prompt: str = args.prompt or _prompt_interactively(
        "Describe the component you want to synthesise (be detailed)"
    )
    out_dir = Path(args.out_dir)

    _console.print(
        Panel("[bold cyan]Amarooi · Spec Synthesis[/bold cyan]", expand=False)
    )

    tracker = UsageTracker()
    limit_msg = tracker.check_limit("transpile")
    if limit_msg:
        _console.print(f"[yellow]{limit_msg}[/yellow]")
        return 1

    engine = SynthesisEngine()
    try:
        spec_path = engine.synthesize(prompt, output_dir=out_dir)
    except VaguePromptError as exc:
        _err_console.print(
            f"[bold yellow]Prompt is too vague:[/bold yellow] {exc}\n\n"
            "Run [bold]amarooi architect[/bold] to launch the interactive "
            "Architect Wizard and refine your requirements."
        )
        return 2
    except AmarooiException as exc:
        _err_console.print(f"[bold red]Error:[/bold red] {exc}")
        return 1

    tracker.increment("transpile")
    _console.print(
        f"[bold green]✓[/bold green] Spec written to [bold]{spec_path}[/bold]\n"
        "[dim]Review the spec, then run [bold]amarooi transpile --file "
        f"{spec_path}[/bold] to generate Python.[/dim]"
    )
    return 0



    """Execute the ``run`` sub-command.

    Runs the full pipeline: plan (generate manifest) then transpile (generate
    Python source) in a single invocation.

    Args:
        args: Parsed argument namespace containing ``prompt`` and ``out``.

    Returns:
        Exit code: ``0`` on success, ``1`` on failure.
    """
    prompt: str = args.prompt or _prompt_interactively("Enter your system requirements")
    out_path = Path(args.out)
    manifest_path = out_path.with_suffix(".amarooi.json")

    _console.print(Panel("[bold cyan]Amarooi · Run Pipeline[/bold cyan]", expand=False))

    # Step 1 – plan
    _console.print("[dim]Step 1/2 – Generating manifest…[/dim]")
    try:
        session = PlannerSession()
        manifest = session.generate_manifest_from_prompt(prompt)
        ManifestEngine.save_manifest(manifest, manifest_path)
    except AmarooiException as exc:
        _err_console.print(f"[bold red]Planning failed:[/bold red] {exc}")
        return 1

    _console.print(f"[bold green]✓[/bold green] Manifest saved to [bold]{manifest_path}[/bold]")

    # Step 2 – transpile
    _console.print("[dim]Step 2/2 – Transpiling manifest…[/dim]")
    try:
        engine = TranspilerEngine()
        engine.transpile_file(manifest_path, out_path)
    except AmarooiException as exc:
        _err_console.print(f"[bold red]Transpilation failed:[/bold red] {exc}")
        return 1

    _console.print(f"[bold green]✓[/bold green] Source written to [bold]{out_path}[/bold]")
    return 0


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    """Construct and return the top-level argument parser.

    Returns:
        A configured :class:`argparse.ArgumentParser` with all sub-commands
        registered.
    """
    parser = argparse.ArgumentParser(
        prog="amarooi",
        description="Deterministic AI-Driven Infrastructure & Logic Transpiler Engine",
    )
    subparsers = parser.add_subparsers(dest="command", metavar="<command>")
    subparsers.required = True

    # ── plan ──────────────────────────────────────────────────────────────
    plan_parser = subparsers.add_parser(
        "plan",
        help="Generate a logic manifest from a natural-language prompt.",
    )
    plan_parser.add_argument(
        "--prompt",
        type=str,
        default=None,
        help="Natural-language description of the system to plan.  "
        "If omitted, you will be prompted interactively.",
    )
    plan_parser.add_argument(
        "--out",
        type=str,
        default=_DEFAULT_MANIFEST_PATH,
        metavar="PATH",
        help=f"Output path for the manifest file (default: {_DEFAULT_MANIFEST_PATH}).",
    )

    # ── transpile ─────────────────────────────────────────────────────────
    transpile_parser = subparsers.add_parser(
        "transpile",
        help="Convert a logic manifest or .amarooi file to Python source code.",
    )
    transpile_parser.add_argument(
        "--manifest",
        type=str,
        default=_DEFAULT_MANIFEST_PATH,
        metavar="PATH",
        help=f"Path to the manifest file (default: {_DEFAULT_MANIFEST_PATH}).",
    )
    transpile_parser.add_argument(
        "--file",
        type=str,
        default=None,
        metavar="PATH",
        help="Path to a hand-written .amarooi natural-pseudocode file.  "
        "When provided, bypasses the JSON manifest pipeline entirely.",
    )
    transpile_parser.add_argument(
        "--out",
        type=str,
        required=True,
        metavar="PATH",
        help="Destination path for the generated Python source file.",
    )

    # ── architect ─────────────────────────────────────────────────────────
    architect_parser = subparsers.add_parser(
        "architect",
        help="Launch the interactive SDLC Architect Wizard.",
    )
    architect_parser.add_argument(
        "--prompt",
        type=str,
        default=None,
        help="High-level project description.  "
        "If omitted, you will be prompted interactively.",
    )

    # ── synthesize ────────────────────────────────────────────────────────
    synthesize_parser = subparsers.add_parser(
        "synthesize",
        help="Stage 1: synthesise a .amarooi spec from a detailed prompt.",
    )
    synthesize_parser.add_argument(
        "--prompt",
        type=str,
        default=None,
        help="Detailed description of the component.  "
        "If omitted, you will be prompted interactively.",
    )
    synthesize_parser.add_argument(
        "--out-dir",
        dest="out_dir",
        type=str,
        default="logic",
        metavar="DIR",
        help="Directory to write the .amarooi spec file (default: logic).",
    )

    # ── run ───────────────────────────────────────────────────────────────
    run_parser = subparsers.add_parser(
        "run",
        help="Plan and transpile in a single pipeline.",
    )
    run_parser.add_argument(
        "--prompt",
        type=str,
        default=None,
        help="Natural-language description of the system to plan.  "
        "If omitted, you will be prompted interactively.",
    )
    run_parser.add_argument(
        "--out",
        type=str,
        required=True,
        metavar="PATH",
        help="Destination path for the generated Python source file.",
    )

    return parser


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _prompt_interactively(message: str) -> str:
    """Read multi-line input from the user interactively.

    Prompts the user to type their input and finish with ``Ctrl+D`` (Unix) or
    ``Ctrl+Z`` (Windows) on an empty line.

    Args:
        message: Prompt message shown to the user.

    Returns:
        The concatenated lines entered by the user.
    """
    _console.print(f"[bold]{message}[/bold] (press Ctrl+D when done):")
    lines: list[str] = []
    try:
        while True:
            line = input()
            lines.append(line)
    except EOFError:
        pass
    return "\n".join(lines).strip()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Entry point for the ``amarooi`` CLI.

    Parses command-line arguments, dispatches to the appropriate sub-command
    handler, and exits with the returned exit code.
    """
    parser = _build_parser()
    args = parser.parse_args()

    dispatch = {
        "plan": _cmd_plan,
        "transpile": _cmd_transpile,
        "run": _cmd_run,
        "architect": _cmd_architect,
        "synthesize": _cmd_synthesize,
    }

    handler = dispatch[args.command]
    exit_code: int = handler(args)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
