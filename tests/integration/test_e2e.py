"""End-to-end integration tests for the Amarooi CLI and pipeline.

These tests exercise the full pipeline with mocked LLM calls:
    Prompt → LogicManifest → Python Source Code

All network calls are replaced with mocks; no real Groq API key is required.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from amarooi.core.exceptions import AmarooiException, LLMExecutionError
from amarooi.planner.schemas import LogicManifest


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _manifest_payload() -> dict:
    """Return a minimal valid manifest payload that satisfies the schema."""
    return {
        "meta": {
            "project_name": "E2E Test Project",
            "version": "1.0.0",
            "generated_at": "2026-08-11T21:00:00Z",
            "engine_version": "1.0.0",
        },
        "context": {
            "problem_statement": "Return whether a number is even or odd.",
            "target_language": "python",
            "runtime_constraints": [],
        },
        "state_matrix": {
            "variables": [
                {
                    "name": "number",
                    "type": "int",
                    "description": "The number to check.",
                    "allowed_values": None,
                }
            ],
            "invariants": ["number must be an integer"],
        },
        "logic_gates": [
            {
                "gate_id": "gate-1",
                "condition": "number % 2 == 0",
                "on_true": "return 'even'",
                "on_false": "return 'odd'",
            }
        ],
        "edge_cases": [
            {
                "scenario": "number is zero",
                "fallback_action": "return 'even'",
            }
        ],
    }


def _make_groq_client_mock(manifest_payload: dict, generated_code: str) -> MagicMock:
    """Create a GroqClientWrapper mock that returns *manifest_payload* and *generated_code*.

    Args:
        manifest_payload: Dict that the mock's ``generate_structured_json`` will return.
        generated_code: String returned by ``generate_completion``.

    Returns:
        A configured :class:`unittest.mock.MagicMock` mimicking GroqClientWrapper.
    """
    client = MagicMock()
    client.generate_structured_json.return_value = LogicManifest.model_validate(
        manifest_payload
    )
    client.generate_completion.return_value = generated_code
    return client


# ---------------------------------------------------------------------------
# Full pipeline integration tests
# ---------------------------------------------------------------------------


class TestFullPipeline:
    """Tests for the complete Prompt → LogicManifest → Python Source pipeline."""

    def test_plan_then_transpile(self, tmp_path: Path) -> None:
        """Full pipeline: PlannerSession produces manifest, TranspilerEngine produces code."""
        from amarooi.core.state import PlannerSession
        from amarooi.planner.manifest import ManifestEngine
        from amarooi.transpiler.engine import TranspilerEngine

        manifest_payload = _manifest_payload()
        valid_code = "def check(n: int) -> str:\n    return 'even' if n % 2 == 0 else 'odd'\n"

        client_mock = _make_groq_client_mock(manifest_payload, valid_code)

        manifest_path = tmp_path / "logic.amarooi.json"
        output_path = tmp_path / "logic.py"

        # ── Phase 1: plan ────────────────────────────────────────────────
        with patch("amarooi.core.state.GroqClientWrapper", return_value=client_mock):
            with patch("amarooi.core.state.get_settings", create=True):
                session = PlannerSession(client=client_mock)
                manifest = session.generate_manifest_from_prompt(
                    "Return whether a number is even or odd."
                )

        ManifestEngine.save_manifest(manifest, manifest_path)
        assert manifest_path.exists()

        loaded = ManifestEngine.load_manifest(manifest_path)
        assert loaded.meta.project_name == manifest_payload["meta"]["project_name"]

        # ── Phase 2: transpile ────────────────────────────────────────────
        transpile_client = MagicMock()
        transpile_client.generate_completion.return_value = valid_code

        with patch("amarooi.transpiler.engine.get_settings"):
            engine = TranspilerEngine(client=transpile_client)
            result = engine.transpile_file(manifest_path, output_path)

        assert output_path.exists()
        assert "def check" in result

    def test_session_state_transitions(self) -> None:
        """PlannerSession transitions IDLE → PLANNING → MANIFEST_GENERATED."""
        from amarooi.core.state import PlannerSession, SessionState

        manifest_payload = _manifest_payload()
        client_mock = MagicMock()
        client_mock.generate_structured_json.return_value = LogicManifest.model_validate(
            manifest_payload
        )

        session = PlannerSession(client=client_mock)
        assert session.state is SessionState.IDLE

        session.generate_manifest_from_prompt("some prompt")

        assert session.state is SessionState.MANIFEST_GENERATED
        assert session.manifest is not None

    def test_session_state_failed_on_llm_error(self) -> None:
        """PlannerSession transitions to FAILED when the LLM raises."""
        from amarooi.core.state import PlannerSession, SessionState

        client_mock = MagicMock()
        client_mock.generate_structured_json.side_effect = LLMExecutionError(
            "Groq down", status_code=500
        )

        session = PlannerSession(client=client_mock)

        with pytest.raises(LLMExecutionError):
            session.generate_manifest_from_prompt("some prompt")

        assert session.state is SessionState.FAILED
        assert session.manifest is None


# ---------------------------------------------------------------------------
# CLI argument-parsing tests
# ---------------------------------------------------------------------------


class TestCLIArgParsing:
    """Verify that CLI entry-point arguments parse correctly."""

    def _get_parser(self):
        """Import and return the CLI argument parser."""
        from amarooi.cli import _build_parser

        return _build_parser()

    def test_plan_defaults(self) -> None:
        """``amarooi plan`` uses default output path when --out is not given."""
        parser = self._get_parser()
        args = parser.parse_args(["plan", "--prompt", "my prompt"])
        assert args.command == "plan"
        assert args.prompt == "my prompt"
        assert args.out == ".amarooi.json"

    def test_plan_custom_out(self) -> None:
        """``amarooi plan --out custom.json`` stores the custom path."""
        parser = self._get_parser()
        args = parser.parse_args(["plan", "--prompt", "p", "--out", "custom.json"])
        assert args.out == "custom.json"

    def test_transpile_defaults_output_and_manifest(self) -> None:
        """``amarooi transpile`` can rely on default manifest and output resolution."""
        parser = self._get_parser()
        args = parser.parse_args(["transpile"])
        assert args.command == "transpile"
        assert args.manifest == ".amarooi.json"
        assert args.out is None

    def test_transpile_parses_spec_and_target_alias(self) -> None:
        """``amarooi transpile`` accepts ``--spec`` and short target aliases."""
        parser = self._get_parser()
        args = parser.parse_args(
            ["transpile", "--spec", "specs/order_router.amarooi", "-t", "rs"]
        )
        assert args.command == "transpile"
        assert args.spec == "specs/order_router.amarooi"
        assert args.target == "rs"
        assert args.out is None

    def test_run_requires_out(self) -> None:
        """``amarooi run`` without --out exits with error."""
        parser = self._get_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["run", "--prompt", "p"])

    def test_run_parses_correctly(self) -> None:
        """``amarooi run`` stores prompt and out path."""
        parser = self._get_parser()
        args = parser.parse_args(["run", "--prompt", "make stuff", "--out", "out.py"])
        assert args.command == "run"
        assert args.prompt == "make stuff"
        assert args.out == "out.py"


# ---------------------------------------------------------------------------
# CLI sub-command invocation tests (with mocked LLM)
# ---------------------------------------------------------------------------


class TestCLISubCommands:
    """Tests that invoke CLI sub-command functions with mocked LLM dependencies."""

    def test_cmd_plan_writes_manifest(self, tmp_path: Path) -> None:
        """_cmd_plan() writes a manifest file and returns exit code 0."""
        from amarooi.cli import _cmd_plan

        manifest_payload = _manifest_payload()
        client_mock = MagicMock()
        client_mock.generate_structured_json.return_value = LogicManifest.model_validate(
            manifest_payload
        )

        out_path = tmp_path / "output.amarooi.json"

        args = MagicMock()
        args.prompt = "test prompt"
        args.out = str(out_path)

        with patch("amarooi.cli.PlannerSession") as MockSession:
            instance = MockSession.return_value
            instance.generate_manifest_from_prompt.return_value = (
                LogicManifest.model_validate(manifest_payload)
            )
            exit_code = _cmd_plan(args)

        assert exit_code == 0
        assert out_path.exists()

    def test_cmd_plan_returns_1_on_error(self, tmp_path: Path) -> None:
        """_cmd_plan() returns exit code 1 when an AmarooiException is raised."""
        from amarooi.cli import _cmd_plan

        args = MagicMock()
        args.prompt = "test"
        args.out = str(tmp_path / "out.json")

        with patch("amarooi.cli.PlannerSession") as MockSession:
            instance = MockSession.return_value
            instance.generate_manifest_from_prompt.side_effect = LLMExecutionError(
                "API down"
            )
            exit_code = _cmd_plan(args)

        assert exit_code == 1

    def test_cmd_transpile_writes_source(self, tmp_path: Path) -> None:
        """_cmd_transpile() writes a .py file and returns exit code 0."""
        from amarooi.cli import _cmd_transpile

        # Write a valid manifest to disk.
        manifest_file = tmp_path / "logic.amarooi.json"
        manifest_file.write_text(
            json.dumps(_manifest_payload()), encoding="utf-8"
        )

        out_path = tmp_path / "logic.py"
        valid_code = "def check(n: int) -> bool:\n    return n % 2 == 0\n"

        args = MagicMock()
        args.manifest = str(manifest_file)
        args.spec = None
        args.target = None
        args.out = str(out_path)

        with patch("amarooi.cli.TranspilerEngine") as MockEngine:
            instance = MockEngine.return_value
            instance.transpile_file.return_value = valid_code
            exit_code = _cmd_transpile(args)

        assert exit_code == 0
        instance.transpile_file.assert_called_once()

    def test_cmd_transpile_spec_uses_target_isolated_default_output(self, tmp_path: Path) -> None:
        """_cmd_transpile() resolves ``src_generated/<target>/`` for ``--spec`` inputs."""
        from amarooi.cli import _cmd_transpile

        spec_file = tmp_path / "specs" / "order_router.amarooi"
        spec_file.parent.mkdir()
        spec_file.write_text("Component: order_router\n", encoding="utf-8")

        args = MagicMock()
        args.manifest = ".amarooi.json"
        args.spec = str(spec_file)
        args.target = "rs"
        args.out = None

        with patch("amarooi.cli.TranspilerEngine") as MockEngine:
            instance = MockEngine.return_value
            instance.transpile_spec_file.return_value = "fn order_router() {}\n"
            exit_code = _cmd_transpile(args)

        assert exit_code == 0
        called_out = instance.transpile_spec_file.call_args.args[1]
        assert Path(called_out) == tmp_path / "src_generated" / "rust" / "order_router.rs"

    def test_cmd_run_full_pipeline(self, tmp_path: Path) -> None:
        """_cmd_run() executes plan + transpile and returns exit code 0."""
        from amarooi.cli import _cmd_run

        manifest_payload = _manifest_payload()
        valid_code = "x = 1\n"

        out_path = tmp_path / "output.py"

        args = MagicMock()
        args.prompt = "build something"
        args.out = str(out_path)

        with patch("amarooi.cli.PlannerSession") as MockSession, patch(
            "amarooi.cli.TranspilerEngine"
        ) as MockEngine:
            session_instance = MockSession.return_value
            session_instance.generate_manifest_from_prompt.return_value = (
                LogicManifest.model_validate(manifest_payload)
            )
            engine_instance = MockEngine.return_value
            engine_instance.transpile_file.return_value = valid_code

            exit_code = _cmd_run(args)

        assert exit_code == 0
        session_instance.generate_manifest_from_prompt.assert_called_once_with(
            "build something"
        )
        engine_instance.transpile_file.assert_called_once()

    def test_cmd_extract_defaults_to_extracted_specs_directory(self, tmp_path: Path) -> None:
        """_cmd_extract() resolves extracted output into ``extracted_specs/`` by default."""
        from amarooi.cli import _cmd_extract

        source_file = tmp_path / "legacy.py"
        source_file.write_text("x = 1\n", encoding="utf-8")

        args = MagicMock()
        args.source = str(source_file)
        args.lang = "python"
        args.out = None

        spec_mock = MagicMock()
        spec_mock.model_dump.return_value = {"component_name": "legacy"}

        with patch("amarooi.core.extractor.factory.PythonExtractor.extract", return_value=spec_mock):
            exit_code = _cmd_extract(args)

        assert exit_code == 0
        assert (tmp_path / "extracted_specs" / "legacy.amarooi.json").exists()
