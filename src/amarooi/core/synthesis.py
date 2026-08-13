"""Two-Stage Unstructured Spec Synthesis Engine.

This module implements the mandatory `.amarooi` spec synthesis pipeline:

Stage 1 – **Spec Evaluation**: determines whether the input prompt contains
  sufficient detail (state registers, invariants, failure modes).  Vague
  prompts are routed to the interactive Architect Wizard; detailed prompts are
  parsed directly into a ``.amarooi`` logic contract.

Stage 2 – **Deterministic Transpilation**: the ``.amarooi`` contract produced
  in Stage 1 is always reviewed before any Python is generated.

The strict guardrail ensures raw text *never* compiles directly to Python;
``.amarooi`` is the mandatory intermediate contract.

Example::

    from amarooi.core.synthesis import SynthesisEngine
    engine = SynthesisEngine()
    spec_path = engine.synthesize("Build a rate-limiter…", output_dir=Path("specs"))
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

from amarooi.core.exceptions import AmarooiException

if TYPE_CHECKING:
    pass


# ---------------------------------------------------------------------------
# Constants – minimum spec-completeness thresholds
# ---------------------------------------------------------------------------

#: Minimum word count for a prompt to be considered "detailed".
_MIN_WORD_COUNT = 30

#: Keywords that signal the presence of state/invariants/failure modes.
_SPEC_SIGNAL_KEYWORDS: frozenset[str] = frozenset(
    {
        # state / data
        "state", "variable", "register", "field", "attribute",
        # invariants / constraints
        "invariant", "constraint", "must", "should", "always", "never",
        # failure / edge cases
        "failure", "error", "exception", "edge", "timeout", "retry",
        "fallback", "invalid", "missing",
        # flow / logic
        "loop", "step", "sequence", "transition", "condition", "branch",
    }
)

#: Number of distinct signal keywords required to pass the spec threshold.
_MIN_KEYWORD_HITS = 3


class SpecEvaluationResult:
    """Result returned by :meth:`SynthesisEngine.evaluate_prompt`.

    Attributes:
        is_detailed: ``True`` if the prompt passed the spec-completeness
            threshold and should bypass the Architect Wizard.
        word_count: Number of words found in the prompt.
        keyword_hits: Set of spec-signal keywords matched in the prompt.
        missing_signals: Human-readable list of signal categories that were
            absent from the prompt.
    """

    def __init__(
        self,
        *,
        is_detailed: bool,
        word_count: int,
        keyword_hits: set[str],
        missing_signals: list[str],
    ) -> None:
        self.is_detailed = is_detailed
        self.word_count = word_count
        self.keyword_hits = keyword_hits
        self.missing_signals = missing_signals

    def __repr__(self) -> str:
        return (
            f"SpecEvaluationResult(is_detailed={self.is_detailed}, "
            f"word_count={self.word_count}, "
            f"keyword_hits={sorted(self.keyword_hits)})"
        )


class SynthesisEngine:
    """Two-Stage Unstructured Spec Synthesis Engine.

    Evaluates free-form user prompts and routes them through the correct
    pipeline to produce a ``.amarooi`` logic contract.

    Args:
        llm_client: Optional :class:`~amarooi.utils.llm.GroqClientWrapper`
            instance.  When *None* a fresh instance is created lazily on first
            use so that tests can inject mocks.
    """

    def __init__(self, llm_client=None) -> None:  # noqa: ANN001
        self._llm_client = llm_client

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def evaluate_prompt(self, prompt: str) -> SpecEvaluationResult:
        """Stage 1 – evaluate whether *prompt* meets spec-completeness criteria.

        A prompt is considered *detailed* when it contains at least
        ``_MIN_WORD_COUNT`` words **and** at least ``_MIN_KEYWORD_HITS``
        distinct spec-signal keywords.

        Args:
            prompt: Raw user-supplied text.

        Returns:
            A :class:`SpecEvaluationResult` describing the evaluation outcome.
        """
        words = prompt.split()
        word_count = len(words)
        lowered = prompt.lower()

        keyword_hits: set[str] = {
            kw for kw in _SPEC_SIGNAL_KEYWORDS if re.search(r"\b" + re.escape(kw) + r"\b", lowered)
        }

        missing_signals: list[str] = []
        _state_kws = {"state", "variable", "register", "field", "attribute"}
        _invariant_kws = {"invariant", "constraint", "must", "should", "always", "never"}
        _failure_kws = {"failure", "error", "exception", "edge", "timeout", "retry", "fallback", "invalid", "missing"}

        if not keyword_hits & _state_kws:
            missing_signals.append("state registers / variables")
        if not keyword_hits & _invariant_kws:
            missing_signals.append("invariants / constraints")
        if not keyword_hits & _failure_kws:
            missing_signals.append("failure modes / edge cases")

        is_detailed = word_count >= _MIN_WORD_COUNT and len(keyword_hits) >= _MIN_KEYWORD_HITS

        return SpecEvaluationResult(
            is_detailed=is_detailed,
            word_count=word_count,
            keyword_hits=keyword_hits,
            missing_signals=missing_signals,
        )

    def synthesize_spec(self, prompt: str) -> str:
        """Stage 1 (Scenario 2) – synthesise a ``.amarooi`` spec from a detailed prompt.

        Calls the LLM to convert the rich user prompt into a structured
        Amarooi logic contract (natural pseudocode format).

        Args:
            prompt: A *detailed* user-supplied prompt that has already passed
                :meth:`evaluate_prompt`.

        Returns:
            The synthesised ``.amarooi`` spec as a UTF-8 string.

        Raises:
            :class:`~amarooi.core.exceptions.AmarooiException`: If the LLM
                call fails.
        """
        client = self._get_client()
        messages = [
            {
                "role": "system",
                "content": (
                    "You are an expert software architect specialising in "
                    "Logic-Driven Development (LDD).  "
                    "Your task is to convert the user's detailed requirement "
                    "description into a structured Amarooi `.amarooi` logic "
                    "contract.  The contract MUST include:\n"
                    "  1. COMPONENT – a short name for the component.\n"
                    "  2. STATE REGISTERS – all mutable state variables with "
                    "types and initial values.\n"
                    "  3. INVARIANTS – conditions that must always hold.\n"
                    "  4. EXECUTION LOOP – ordered steps describing the logic.\n"
                    "  5. FAILURE MODES – explicit error/edge-case handling.\n\n"
                    "Return ONLY the `.amarooi` spec text.  "
                    "Do NOT include explanations, Markdown fences, or Python code."
                ),
            },
            {"role": "user", "content": prompt},
        ]
        return client.generate_completion(messages, temperature=0.2, max_tokens=2048)

    def synthesize(self, prompt: str, output_dir: Path) -> Path:
        """Run the full Stage-1 synthesis pipeline.

        * **Vague prompt** → raises :class:`VaguePromptError` so the caller
          (CLI / extension) can launch the Architect Wizard instead.
        * **Detailed prompt** → synthesises a ``.amarooi`` spec and writes it
          to *output_dir* using a slug derived from the first words of the
          prompt.

        Args:
            prompt: Raw user-supplied text.
            output_dir: Directory where the ``.amarooi`` file will be written.

        Returns:
            Path to the written ``.amarooi`` file.

        Raises:
            :class:`VaguePromptError`: When the prompt fails spec-completeness
                criteria (caller should launch the Architect Wizard).
            :class:`~amarooi.core.exceptions.AmarooiException`: For LLM
                failures.
        """
        result = self.evaluate_prompt(prompt)

        if not result.is_detailed:
            raise VaguePromptError(
                "Prompt does not meet spec-completeness criteria.  "
                "Please provide more detail about state registers, invariants, "
                f"and failure modes.  Missing: {', '.join(result.missing_signals)}.",
                evaluation=result,
            )

        spec_text = self.synthesize_spec(prompt)

        output_dir.mkdir(parents=True, exist_ok=True)
        slug = _make_slug(prompt)
        out_path = output_dir / f"{slug}.amarooi"
        out_path.write_text(spec_text, encoding="utf-8")
        return out_path

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _get_client(self):  # noqa: ANN202
        if self._llm_client is None:
            from amarooi.utils.llm import GroqClientWrapper

            self._llm_client = GroqClientWrapper()
        return self._llm_client


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_slug(prompt: str, max_words: int = 5) -> str:
    """Derive a filesystem-safe slug from the first words of *prompt*.

    Args:
        prompt: Raw user text.
        max_words: Maximum number of words to include in the slug.

    Returns:
        A lowercase, hyphen-separated string suitable for a filename.
    """
    words = re.sub(r"[^a-zA-Z0-9\s]", "", prompt).split()[:max_words]
    return "-".join(w.lower() for w in words) or "spec"


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class VaguePromptError(AmarooiException):
    """Raised when a prompt fails spec-completeness evaluation.

    The caller should route the user through the interactive Architect Wizard.

    Attributes:
        evaluation: The :class:`SpecEvaluationResult` that triggered this
            error.
    """

    def __init__(self, message: str, evaluation: SpecEvaluationResult) -> None:
        super().__init__(message)
        self.evaluation = evaluation
