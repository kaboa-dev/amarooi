"""Unit tests for Phase 7: Two-Stage Unstructured Spec Synthesis Engine.

Covers:
- Scenario 1: Vague prompt correctly fails spec-completeness evaluation and
  raises ``VaguePromptError``.
- Scenario 2: Detailed prompt passes evaluation and synthesises a ``.amarooi``
  spec via the LLM, writing the file to disk.
- Guardrail: ``synthesize()`` never writes raw text directly as Python.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from amarooi.core.synthesis import (
    SynthesisEngine,
    VaguePromptError,
    _make_slug,
    _MIN_KEYWORD_HITS,
    _MIN_WORD_COUNT,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_VAGUE_PROMPT = "Build me a thing that does stuff."

_DETAILED_PROMPT = (
    "Design a rate-limiter component that tracks request counts in a state "
    "register keyed by client ID.  The invariant is that no client must exceed "
    "100 requests per minute.  Include failure modes for timeout, missing "
    "client ID, and invalid token.  The execution loop should check the counter "
    "state on each request, increment it, and return an error response when the "
    "constraint is violated."
)


def _mock_client(spec_text: str = "COMPONENT: rate_limiter\nSTATE: counter int 0") -> MagicMock:
    client = MagicMock()
    client.generate_completion.return_value = spec_text
    return client


# ---------------------------------------------------------------------------
# evaluate_prompt – Scenario 1 (vague)
# ---------------------------------------------------------------------------


class TestEvaluatePromptVague:
    """Vague prompts must fail spec-completeness evaluation."""

    def test_vague_prompt_is_not_detailed(self) -> None:
        engine = SynthesisEngine()
        result = engine.evaluate_prompt(_VAGUE_PROMPT)
        assert result.is_detailed is False

    def test_vague_prompt_low_word_count(self) -> None:
        engine = SynthesisEngine()
        result = engine.evaluate_prompt(_VAGUE_PROMPT)
        assert result.word_count < _MIN_WORD_COUNT

    def test_vague_prompt_insufficient_keywords(self) -> None:
        engine = SynthesisEngine()
        result = engine.evaluate_prompt(_VAGUE_PROMPT)
        assert len(result.keyword_hits) < _MIN_KEYWORD_HITS

    def test_vague_prompt_reports_missing_signals(self) -> None:
        engine = SynthesisEngine()
        result = engine.evaluate_prompt(_VAGUE_PROMPT)
        assert len(result.missing_signals) > 0

    def test_empty_prompt_is_not_detailed(self) -> None:
        engine = SynthesisEngine()
        result = engine.evaluate_prompt("")
        assert result.is_detailed is False


# ---------------------------------------------------------------------------
# evaluate_prompt – Scenario 2 (detailed)
# ---------------------------------------------------------------------------


class TestEvaluatePromptDetailed:
    """Detailed prompts must pass spec-completeness evaluation."""

    def test_detailed_prompt_is_detailed(self) -> None:
        engine = SynthesisEngine()
        result = engine.evaluate_prompt(_DETAILED_PROMPT)
        assert result.is_detailed is True

    def test_detailed_prompt_sufficient_word_count(self) -> None:
        engine = SynthesisEngine()
        result = engine.evaluate_prompt(_DETAILED_PROMPT)
        assert result.word_count >= _MIN_WORD_COUNT

    def test_detailed_prompt_sufficient_keyword_hits(self) -> None:
        engine = SynthesisEngine()
        result = engine.evaluate_prompt(_DETAILED_PROMPT)
        assert len(result.keyword_hits) >= _MIN_KEYWORD_HITS

    def test_detailed_prompt_no_missing_signals(self) -> None:
        engine = SynthesisEngine()
        result = engine.evaluate_prompt(_DETAILED_PROMPT)
        assert result.missing_signals == []


# ---------------------------------------------------------------------------
# synthesize – Scenario 1: vague prompt raises VaguePromptError
# ---------------------------------------------------------------------------


class TestSynthesizeVaguePrompt:
    """Vague prompts must raise VaguePromptError without calling the LLM."""

    def test_vague_prompt_raises_vague_prompt_error(self, tmp_path: Path) -> None:
        client = _mock_client()
        engine = SynthesisEngine(llm_client=client)

        with pytest.raises(VaguePromptError):
            engine.synthesize(_VAGUE_PROMPT, output_dir=tmp_path)

    def test_vague_prompt_llm_not_called(self, tmp_path: Path) -> None:
        client = _mock_client()
        engine = SynthesisEngine(llm_client=client)

        with pytest.raises(VaguePromptError):
            engine.synthesize(_VAGUE_PROMPT, output_dir=tmp_path)

        client.generate_completion.assert_not_called()

    def test_vague_prompt_error_carries_evaluation(self, tmp_path: Path) -> None:
        client = _mock_client()
        engine = SynthesisEngine(llm_client=client)

        with pytest.raises(VaguePromptError) as exc_info:
            engine.synthesize(_VAGUE_PROMPT, output_dir=tmp_path)

        assert exc_info.value.evaluation is not None
        assert exc_info.value.evaluation.is_detailed is False

    def test_vague_prompt_no_file_written(self, tmp_path: Path) -> None:
        client = _mock_client()
        engine = SynthesisEngine(llm_client=client)

        with pytest.raises(VaguePromptError):
            engine.synthesize(_VAGUE_PROMPT, output_dir=tmp_path)

        assert list(tmp_path.glob("*.amarooi")) == []


# ---------------------------------------------------------------------------
# synthesize – Scenario 2: detailed prompt auto-synthesises spec
# ---------------------------------------------------------------------------


class TestSynthesizeDetailedPrompt:
    """Detailed prompts must call the LLM and write a .amarooi spec file."""

    def test_detailed_prompt_writes_amarooi_file(self, tmp_path: Path) -> None:
        spec_text = "COMPONENT: rate_limiter\nSTATE: counter int 0\n"
        client = _mock_client(spec_text)
        engine = SynthesisEngine(llm_client=client)

        path = engine.synthesize(_DETAILED_PROMPT, output_dir=tmp_path)

        assert path.exists()
        assert path.suffix == ".amarooi"

    def test_detailed_prompt_file_contains_llm_output(self, tmp_path: Path) -> None:
        spec_text = "COMPONENT: rate_limiter\nSTATE: counter int 0\n"
        client = _mock_client(spec_text)
        engine = SynthesisEngine(llm_client=client)

        path = engine.synthesize(_DETAILED_PROMPT, output_dir=tmp_path)

        assert path.read_text(encoding="utf-8") == spec_text

    def test_detailed_prompt_llm_called_once(self, tmp_path: Path) -> None:
        client = _mock_client()
        engine = SynthesisEngine(llm_client=client)

        engine.synthesize(_DETAILED_PROMPT, output_dir=tmp_path)

        client.generate_completion.assert_called_once()

    def test_detailed_prompt_creates_output_dir(self, tmp_path: Path) -> None:
        nested = tmp_path / "deep" / "logic"
        client = _mock_client()
        engine = SynthesisEngine(llm_client=client)

        path = engine.synthesize(_DETAILED_PROMPT, output_dir=nested)

        assert nested.exists()
        assert path.parent == nested

    def test_detailed_prompt_returns_path_object(self, tmp_path: Path) -> None:
        client = _mock_client()
        engine = SynthesisEngine(llm_client=client)

        path = engine.synthesize(_DETAILED_PROMPT, output_dir=tmp_path)

        assert isinstance(path, Path)


# ---------------------------------------------------------------------------
# Guardrail: raw text must never become Python without a .amarooi contract
# ---------------------------------------------------------------------------


class TestSpecGuardrail:
    """The synthesis engine must never return Python code – only .amarooi."""

    def test_spec_file_extension_is_always_amarooi(self, tmp_path: Path) -> None:
        client = _mock_client("some spec")
        engine = SynthesisEngine(llm_client=client)

        path = engine.synthesize(_DETAILED_PROMPT, output_dir=tmp_path)

        assert path.suffix == ".amarooi", "Output must be a .amarooi spec, not Python."

    def test_no_py_file_written_during_synthesis(self, tmp_path: Path) -> None:
        client = _mock_client("some spec")
        engine = SynthesisEngine(llm_client=client)

        engine.synthesize(_DETAILED_PROMPT, output_dir=tmp_path)

        py_files = list(tmp_path.rglob("*.py"))
        assert py_files == [], "synthesize() must not write any Python files."


# ---------------------------------------------------------------------------
# Slug helper
# ---------------------------------------------------------------------------


class TestMakeSlug:
    def test_basic_slug(self) -> None:
        assert _make_slug("Build a rate limiter component") == "build-a-rate-limiter-component"

    def test_slug_strips_punctuation(self) -> None:
        slug = _make_slug("Hello, world! This is great.")
        assert "," not in slug
        assert "!" not in slug

    def test_slug_max_words(self) -> None:
        slug = _make_slug("one two three four five six seven", max_words=3)
        assert slug == "one-two-three"

    def test_empty_prompt_returns_spec(self) -> None:
        assert _make_slug("") == "spec"
