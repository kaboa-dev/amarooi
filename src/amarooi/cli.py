"""Command-line interface entry point for the Amarooi framework.

Exposes core sub-commands:

* ``amarooi plan``    – generate a ``.amarooi.json`` logic manifest.
* ``amarooi transpile`` – convert a manifest or ``.amarooi`` spec to source code.
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
from amarooi.core.workspace import ProjectWorkspace, TARGET_ALIASES, normalize_target, target_badge
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
    and generates formatted target source code.

    When ``--spec`` / ``--file`` points to a ``.amarooi`` natural-pseudocode file the
    transpiler reads it directly from disk and sends it to the LLM.  When
    ``--manifest`` is used the existing JSON manifest pipeline is followed.

    Args:
        args: Parsed argument namespace containing ``manifest``, ``spec``,
            ``target``, and ``out``.

    Returns:
        Exit code: ``0`` on success, ``1`` on failure.
    """
    _console.print(Panel("[bold cyan]Amarooi · Transpiling[/bold cyan]", expand=False))
    engine = TranspilerEngine()

    # ── Branch: direct .amarooi spec transpilation ─────────────────────
    if getattr(args, "spec", None):
        spec_path = Path(args.spec)
        try:
            canonical_target = normalize_target(args.target)
        except ValueError as exc:
            _err_console.print(f"[bold red]Error:[/bold red] {exc}")
            return 1
        out_path = Path(args.out) if args.out else ProjectWorkspace.from_path(
            spec_path
        ).resolve_generated_path(spec_path, canonical_target)
        _console.print(f"[dim]Reading spec     ← {spec_path}[/dim]")
        _console.print(f"[dim]Target          → {target_badge(canonical_target)}[/dim]")
        _console.print(f"[dim]Writing source   → {out_path}[/dim]")
        try:
            engine.transpile_spec_file(spec_path, out_path, target_language=canonical_target)
        except (AmarooiException, OSError) as exc:
            _err_console.print(f"[bold red]Error:[/bold red] {exc}")
            return 1

        _console.print(
            f"[bold green]✓[/bold green] {target_badge(canonical_target)} "
            f"source written to [bold]{out_path}[/bold]"
        )
        return 0

    # ── Branch: existing JSON manifest pipeline ────────────────────────
    manifest_path = Path(args.manifest)
    try:
        manifest = ManifestEngine.load_manifest(manifest_path)
        canonical_target = normalize_target(args.target or manifest.context.target_language)
        out_path = Path(args.out) if args.out else ProjectWorkspace.from_path(
            manifest_path
        ).resolve_generated_path(manifest_path, canonical_target)
        _console.print(f"[dim]Reading manifest ← {manifest_path}[/dim]")
        _console.print(f"[dim]Target          → {target_badge(canonical_target)}[/dim]")
        _console.print(f"[dim]Writing source   → {out_path}[/dim]")
        engine.transpile_file(
            manifest_path,
            out_path,
            target_language=canonical_target,
        )
    except (AmarooiException, ValueError) as exc:
        _err_console.print(f"[bold red]Error:[/bold red] {exc}")
        return 1

    _console.print(
        f"[bold green]✓[/bold green] {target_badge(canonical_target)} "
        f"source written to [bold]{out_path}[/bold]"
    )
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
      into ``specs/<slug>.amarooi`` without an interactive interview.
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
    workspace = ProjectWorkspace(Path.cwd())
    out_dir = Path(args.out_dir) if args.out_dir else workspace.specs_dir

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
        "[dim]Review the spec, then run [bold]amarooi transpile --spec "
        f"{spec_path}[/bold] to generate Python.[/dim]"
    )
    return 0


def _cmd_run(args: argparse.Namespace) -> int:
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


def _cmd_extract(args: argparse.Namespace) -> int:
    """Execute the ``extract`` sub-command.

    Parses a legacy source file and writes its extracted ``.amarooi``
    :class:`~amarooi.core.spec.SpecContract` to the output path as JSON.

    Args:
        args: Parsed argument namespace containing ``source``, ``lang``,
            and ``out``.

    Returns:
        Exit code: ``0`` on success, ``1`` on failure.
    """
    import json as _json
    from pathlib import Path as _Path

    from amarooi.core.extractor.factory import ExtractorFactory

    source_path = _Path(args.source)
    workspace = ProjectWorkspace.from_path(source_path)
    out_path = _Path(args.out) if args.out else workspace.resolve_extracted_spec_path(source_path)
    lang_key: str = args.lang or source_path.suffix

    _console.print(
        Panel("[bold cyan]Amarooi · Legacy Logic Extraction[/bold cyan]", expand=False)
    )
    _console.print(f"[dim]Source: {source_path}[/dim]")
    _console.print(f"[dim]Lang key: {lang_key!r}[/dim]")

    try:
        source_code = source_path.read_text(encoding="utf-8")
    except OSError as exc:
        _err_console.print(f"[bold red]Error reading source:[/bold red] {exc}")
        return 1

    try:
        factory = ExtractorFactory()
        extractor = factory.get_extractor(lang_key)
    except KeyError as exc:
        _err_console.print(f"[bold red]Error:[/bold red] {exc}")
        return 1

    try:
        spec = extractor.extract(source_code)
    except SyntaxError as exc:
        _err_console.print(f"[bold red]Syntax error in source:[/bold red] {exc}")
        return 1

    try:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(
            _json.dumps(spec.model_dump(), indent=2), encoding="utf-8"
        )
    except OSError as exc:
        _err_console.print(f"[bold red]Error writing output:[/bold red] {exc}")
        return 1

    _console.print(
        f"[bold green]✓[/bold green] Spec written to [bold]{out_path}[/bold]"
    )
    return 0


def _cmd_verify(args: argparse.Namespace) -> int:
    """Execute the ``verify`` sub-command.

    Loads one or two :class:`~amarooi.core.spec.SpecContract` JSON files and
    runs formal Z3 verification.

    * With ``--spec`` only → Invariant / post-condition verification.
    * With ``--spec`` and ``--target`` → Equivalence checking (*F ≡ G*).

    Args:
        args: Parsed argument namespace containing ``spec`` and optionally
            ``target``.

    Returns:
        Exit code: ``0`` on success, ``1`` on failure.
    """
    import json as _json
    from pathlib import Path as _Path

    from amarooi.core.spec import SpecContract
    from amarooi.core.verifier import FormalVerifier

    spec_path = _Path(args.spec)

    _console.print(
        Panel("[bold cyan]Amarooi · Formal Verification[/bold cyan]", expand=False)
    )

    try:
        spec_f = SpecContract.model_validate(
            _json.loads(spec_path.read_text(encoding="utf-8"))
        )
    except (OSError, ValueError) as exc:
        _err_console.print(f"[bold red]Error loading spec:[/bold red] {exc}")
        return 1

    verifier = FormalVerifier()

    if getattr(args, "target", None):
        target_path = _Path(args.target)
        try:
            spec_g = SpecContract.model_validate(
                _json.loads(target_path.read_text(encoding="utf-8"))
            )
        except (OSError, ValueError) as exc:
            _err_console.print(f"[bold red]Error loading target spec:[/bold red] {exc}")
            return 1
        _console.print("[dim]Mode: equivalence checking (F ≡ G)[/dim]")
        result = verifier.check_equivalence(spec_f, spec_g)
    else:
        _console.print("[dim]Mode: invariant / post-condition verification[/dim]")
        result = verifier.verify_invariants(spec_f)

    if result.get("proven"):
        _console.print(
            f"[bold green]✓ PROVEN[/bold green]  result=[bold]{result['result']}[/bold]"
        )
    else:
        _console.print(
            f"[bold red]✗ NOT PROVEN[/bold red]  result=[bold]{result['result']}[/bold]"
        )
        if "counterexample" in result:
            _console.print("[yellow]Counter-example:[/yellow]")
            for k, v in result["counterexample"].items():
                _console.print(f"  {k} = {v}")

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
        help="Convert a logic manifest or .amarooi file to target source code.",
    )
    transpile_parser.add_argument(
        "--manifest",
        type=str,
        default=_DEFAULT_MANIFEST_PATH,
        metavar="PATH",
        help=f"Path to the manifest file (default: {_DEFAULT_MANIFEST_PATH}).",
    )
    transpile_parser.add_argument(
        "--spec",
        "--file",
        dest="spec",
        type=str,
        default=None,
        metavar="PATH",
        help="Path to a hand-written .amarooi natural-pseudocode file.  "
        "When provided, bypasses the JSON manifest pipeline entirely.",
    )
    transpile_parser.add_argument(
        "-t",
        "--target",
        type=str,
        default=None,
        metavar="LANG",
        choices=sorted(TARGET_ALIASES),
        help="Target language alias (py/python, rs/rust, cpp/c++, java, ts/typescript).",
    )
    transpile_parser.add_argument(
        "--out",
        type=str,
        default=None,
        metavar="PATH",
        help="Destination path for the generated source file.  "
        "Defaults to src_generated/<target>/<name>.<ext>.",
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
        default=None,
        metavar="DIR",
        help="Directory to write the .amarooi spec file (default: specs).",
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

    # ── extract ───────────────────────────────────────────────────────────
    extract_parser = subparsers.add_parser(
        "extract",
        help="Extract a .amarooi SpecContract from legacy source code.",
    )
    extract_parser.add_argument(
        "--source",
        type=str,
        required=True,
        metavar="PATH",
        help="Path to the legacy source file to analyse.",
    )
    extract_parser.add_argument(
        "--lang",
        type=str,
        default=None,
        metavar="LANG",
        help="Language / file-extension key (e.g. 'python', '.py').  "
        "Defaults to the file extension of --source.",
    )
    extract_parser.add_argument(
        "--out",
        type=str,
        default=None,
        metavar="PATH",
        help="Destination path for the extracted SpecContract JSON.  "
        "Defaults to extracted_specs/<source>.amarooi.json.",
    )

    # ── verify ────────────────────────────────────────────────────────────
    verify_parser = subparsers.add_parser(
        "verify",
        help="Run formal Z3 verification on a SpecContract.",
    )
    verify_parser.add_argument(
        "--spec",
        type=str,
        required=True,
        metavar="PATH",
        help="Path to the SpecContract JSON file to verify.",
    )
    verify_parser.add_argument(
        "--target",
        type=str,
        default=None,
        metavar="PATH",
        help="Path to a second SpecContract JSON for equivalence checking (F ≡ G).  "
        "When omitted, invariant / post-condition verification is performed.",
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
        "extract": _cmd_extract,
        "verify": _cmd_verify,
    }

    handler = dispatch[args.command]
    exit_code: int = handler(args)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
