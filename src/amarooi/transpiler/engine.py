"""Transpiler engine for converting LogicManifest objects into executable code.

This module provides :class:`TranspilerEngine`, which accepts a validated
:class:`~amarooi.planner.schemas.LogicManifest` and produces clean, type-
annotated, executable Python 3.10+ source code by prompting an LLM via
:class:`~amarooi.utils.llm.GroqClientWrapper`.

Example:
    >>> from amarooi.transpiler.engine import TranspilerEngine
    >>> engine = TranspilerEngine()
    >>> code = engine.transpile(manifest)
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

from amarooi.core.config import get_settings
from amarooi.core.exceptions import TranspilationError
from amarooi.core.workspace import ProjectWorkspace, normalize_target
from amarooi.planner.manifest import ManifestEngine
from amarooi.planner.schemas import LogicManifest
from amarooi.utils.llm import GroqClientWrapper

# Pattern that matches Markdown code fences (``` or ```python … ```)
_CODE_FENCE_RE = re.compile(
    r"```(?:[a-zA-Z0-9_\-]*)?\n(.*?)```",
    re.DOTALL,
)

_TARGET_GENERATION_HINTS: dict[str, str] = {
    "python": "Generate clean, complete, type-annotated, executable Python 3.10+ code.",
    "rust": "Generate clean, complete, idiomatic Rust code with explicit types and ownership-safe structure.",
    "c++": "Generate clean, complete, modern C++ code with clear types and headers included when needed.",
    "java": "Generate clean, complete, idiomatic Java code with explicit classes and types.",
    "typescript": "Generate clean, complete, strongly typed TypeScript code.",
    "cobol": "Generate clean, complete ANSI COBOL / IBM Enterprise COBOL with IDENTIFICATION DIVISION, ENVIRONMENT DIVISION, DATA DIVISION (WORKING-STORAGE SECTION), and PROCEDURE DIVISION.",
    "javascript": "Generate clean, complete ES6+ JavaScript with async/await, explicit TypeError throw conditions, and module.exports.",
    "go": "Generate clean, complete idiomatic Go code with explicit struct state definitions, multi-return error handling, and strict invariant checks.",
    "csharp": "Generate clean, complete modern C# 10/11 code with record types, strong static typing, ArgumentException gates, and namespace organization.",
}


def _strip_code_fences(text: str) -> str:
    """Remove Markdown code fences from *text*.

    If the text contains at least one fenced block the content of the first
    block is returned.  Otherwise the original text is returned unchanged so
    that raw source code (without fences) passes through unmodified.

    Args:
        text: Raw LLM output that may contain Markdown code fences.

    Returns:
        The cleaned source code string.
    """
    match = _CODE_FENCE_RE.search(text)
    if match:
        return match.group(1).strip()
    return text.strip()


class TranspilerEngine:
    """Transpile a :class:`~amarooi.planner.schemas.LogicManifest` to source code.

    The engine constructs a deterministic prompt from the manifest, delegates
    code generation to an LLM via :class:`~amarooi.utils.llm.GroqClientWrapper`,
    strips Markdown fences from the response, and validates the output with
    :func:`ast.parse` before returning it.

    Attributes:
        _client: The LLM wrapper used for completion requests.
        _settings: Cached application settings.
    """

    def __init__(self, client: GroqClientWrapper | None = None) -> None:
        """Initialise the transpiler engine.

        Args:
            client: Optional pre-configured :class:`~amarooi.utils.llm.GroqClientWrapper`
                instance.  If *None*, a new instance is created using the
                default application settings.
        """
        self._settings = get_settings()
        self._client: GroqClientWrapper = client or GroqClientWrapper()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def transpile(
        self,
        manifest: LogicManifest,
        target_language: str = "python",
    ) -> str:
        """Transpile a logic manifest to source code.

        Constructs a deterministic prompt from the manifest's state variables,
        invariants, logic gates, and edge cases, then calls the LLM to generate
        target source code.  The response is cleaned of Markdown fences and
        validated as syntactically correct Python.

        Args:
            manifest: A fully validated :class:`~amarooi.planner.schemas.LogicManifest`.
            target_language: The desired output language.  Defaults to
                ``"python"``.

        Returns:
            A string containing the generated, AST-validated source code.

        Raises:
            TranspilationError: If the LLM output is not syntactically valid
                Python (when *target_language* is ``"python"``).
            LLMExecutionError: If the underlying LLM call fails.
        """
        canonical_target = normalize_target(target_language)
        prompt = self._build_prompt(manifest, canonical_target)
        return self._generate_code(prompt, canonical_target)

    def transpile_file(
        self,
        manifest_path: str | Path,
        output_path: str | Path | None = None,
        target_language: str | None = None,
    ) -> str:
        """Load a manifest from disk, transpile it, and write the result.

        Args:
            manifest_path: Path to an ``.amarooi.json`` manifest file.
            output_path: Destination path for the generated source file. When
                *None*, a target-isolated path under ``src_generated/<target>/``
                is derived automatically.
            target_language: Optional explicit target override. When omitted,
                the manifest's declared target is used.

        Returns:
            The generated source code string (same content written to
            *output_path*).

        Raises:
            ManifestValidationError: If the manifest file cannot be read or
                fails schema validation.
            TranspilationError: If the generated code fails AST validation.
            LLMExecutionError: If the underlying LLM call fails.
        """
        manifest = ManifestEngine.load_manifest(manifest_path)
        canonical_target = normalize_target(target_language or manifest.context.target_language)
        code = self.transpile(manifest, target_language=canonical_target)

        output = Path(output_path) if output_path is not None else ProjectWorkspace.from_path(
            manifest_path
        ).resolve_generated_path(manifest_path, canonical_target)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(code, encoding="utf-8")
        return code

    def transpile_spec_file(
        self,
        spec_path: str | Path,
        output_path: str | Path | None = None,
        target_language: str = "python",
    ) -> str:
        """Transpile a hand-authored ``.amarooi`` spec into source code."""
        canonical_target = normalize_target(target_language)
        spec_text = Path(spec_path).read_text(encoding="utf-8")
        prompt = self._build_spec_prompt(spec_text, canonical_target)
        code = self._generate_code(prompt, canonical_target)

        output = Path(output_path) if output_path is not None else ProjectWorkspace.from_path(
            spec_path
        ).resolve_generated_path(spec_path, canonical_target)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(code, encoding="utf-8")
        return code

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_prompt(self, manifest: LogicManifest, target_language: str) -> str:
        """Construct a deterministic transpilation prompt from the manifest.

        Args:
            manifest: The logic manifest to transpile.
            target_language: The target programming language for the output.

        Returns:
            A formatted prompt string ready to be sent to the LLM.
        """
        state_vars = "\n".join(
            f"  - {v.name} ({v.type}): {v.description}"
            + (f" [allowed: {', '.join(v.allowed_values)}]" if v.allowed_values else "")
            for v in manifest.state_matrix.variables
        )
        invariants = "\n".join(
            f"  - {inv}" for inv in manifest.state_matrix.invariants
        ) or "  (none)"

        gates = "\n".join(
            f"  - [{g.gate_id}] if ({g.condition}) → {g.on_true} else → {g.on_false}"
            for g in manifest.logic_gates
        ) or "  (none)"

        edge_cases = "\n".join(
            f"  - Scenario: {e.scenario} → fallback: {e.fallback_action}"
            for e in manifest.edge_cases
        ) or "  (none)"

        return (
            f"You are an expert {target_language} engineer.\n"
            f"{_TARGET_GENERATION_HINTS[target_language]}\n"
            f"Return ONLY the source code, with NO explanations and NO Markdown fences.\n\n"
            f"Project: {manifest.meta.project_name}\n"
            f"Problem: {manifest.context.problem_statement}\n\n"
            f"State Variables:\n{state_vars}\n\n"
            f"Invariants:\n{invariants}\n\n"
            f"Logic Gates:\n{gates}\n\n"
            f"Edge Cases:\n{edge_cases}\n"
        )

    def _build_spec_prompt(self, spec_text: str, target_language: str) -> str:
        """Construct a transpilation prompt from natural Amarooi pseudocode."""
        return (
            f"You are an expert {target_language} engineer.\n"
            f"{_TARGET_GENERATION_HINTS[target_language]}\n"
            "Convert the following Amarooi natural pseudocode into production-ready "
            f"{target_language} source code.\n"
            "Return ONLY the source code, with NO explanations and NO Markdown fences.\n\n"
            f"{spec_text.strip()}\n"
        )

    def _generate_code(self, prompt: str, target_language: str) -> str:
        """Generate and validate source code for *target_language*."""
        messages = [{"role": "user", "content": prompt}]
        raw_output = self._client.generate_completion(
            messages,
            model=self._settings.REASONING_MODEL,
            temperature=0.1,
            max_tokens=4096,
        )
        code = _strip_code_fences(raw_output)
        if target_language == "python":
            self._validate_python_ast(code)
        return code

    @staticmethod
    def _validate_python_ast(code: str) -> None:
        """Validate that *code* is syntactically valid Python using :func:`ast.parse`.

        Args:
            code: Python source code string to validate.

        Raises:
            TranspilationError: If *code* contains a syntax error, with details
                about the line and column of the failure.
        """
        try:
            ast.parse(code)
        except SyntaxError as exc:
            raise TranspilationError(
                f"Generated code failed AST validation: {exc.msg} "
                f"(line {exc.lineno}, col {exc.offset})"
            ) from exc
