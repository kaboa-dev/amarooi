"""Unit tests for Phase 3: TranspilerEngine."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from amarooi.core.exceptions import TranspilationError
from amarooi.transpiler.engine import TranspilerEngine


def _manifest_payload() -> dict:
    """Return a minimal valid manifest payload."""
    return {
        "meta": {
            "project_name": "Test Project",
            "version": "1.0.0",
            "generated_at": "2026-08-11T20:00:00Z",
            "engine_version": "2.0.0",
        },
        "context": {
            "problem_statement": "Determine if a number is even or odd.",
            "target_language": "python",
            "runtime_constraints": [],
        },
        "state_matrix": {
            "variables": [
                {
                    "name": "number",
                    "type": "int",
                    "description": "The number to evaluate.",
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


def _make_mock_client(response: str) -> MagicMock:
    """Create a mock GroqClientWrapper returning *response*."""
    client = MagicMock()
    client.generate_completion.return_value = response
    return client


class TestTranspilerEngineSuccessful:
    """Tests for successful transpilation."""

    def test_transpile_valid_python_returns_code(self) -> None:
        """LLM returns valid Python; transpile() should return it unchanged."""
        valid_code = "def is_even(number: int) -> str:\n    return 'even' if number % 2 == 0 else 'odd'\n"
        client = _make_mock_client(valid_code)

        from amarooi.planner.schemas import LogicManifest

        manifest = LogicManifest.model_validate(_manifest_payload())

        with patch("amarooi.transpiler.engine.get_settings"):
            engine = TranspilerEngine(client=client)

        result = engine.transpile(manifest)

        assert result == valid_code.strip()
        client.generate_completion.assert_called_once()

    def test_transpile_strips_markdown_code_fences(self) -> None:
        """LLM wraps code in Markdown fences; they should be stripped."""
        inner_code = "def greet() -> str:\n    return 'hello'"
        fenced_output = f"```python\n{inner_code}\n```"
        client = _make_mock_client(fenced_output)

        from amarooi.planner.schemas import LogicManifest

        manifest = LogicManifest.model_validate(_manifest_payload())

        with patch("amarooi.transpiler.engine.get_settings"):
            engine = TranspilerEngine(client=client)

        result = engine.transpile(manifest)

        assert "```" not in result
        assert result == inner_code

    def test_transpile_strips_plain_code_fences(self) -> None:
        """LLM wraps code in plain ``` fences; they should be stripped."""
        inner_code = "x: int = 1"
        fenced_output = f"```\n{inner_code}\n```"
        client = _make_mock_client(fenced_output)

        from amarooi.planner.schemas import LogicManifest

        manifest = LogicManifest.model_validate(_manifest_payload())

        with patch("amarooi.transpiler.engine.get_settings"):
            engine = TranspilerEngine(client=client)

        result = engine.transpile(manifest)

        assert result == inner_code


class TestTranspilerEngineSyntaxErrors:
    """Tests for invalid Python from the LLM."""

    def test_transpile_raises_on_invalid_syntax(self) -> None:
        """LLM returns invalid Python; TranspilationError must be raised."""
        invalid_code = "def broken(\n    return None"
        client = _make_mock_client(invalid_code)

        from amarooi.planner.schemas import LogicManifest

        manifest = LogicManifest.model_validate(_manifest_payload())

        with patch("amarooi.transpiler.engine.get_settings"):
            engine = TranspilerEngine(client=client)

        with pytest.raises(TranspilationError) as exc_info:
            engine.transpile(manifest)

        assert "AST validation" in str(exc_info.value)

    def test_transpilation_error_contains_line_info(self) -> None:
        """TranspilationError message includes line/column details."""
        invalid_code = "x = (\ny = 1"
        client = _make_mock_client(invalid_code)

        from amarooi.planner.schemas import LogicManifest

        manifest = LogicManifest.model_validate(_manifest_payload())

        with patch("amarooi.transpiler.engine.get_settings"):
            engine = TranspilerEngine(client=client)

        with pytest.raises(TranspilationError) as exc_info:
            engine.transpile(manifest)

        error_message = str(exc_info.value)
        assert "line" in error_message


class TestTranspilerEngineFile:
    """End-to-end tests using tmp_path fixtures."""

    def test_transpile_file_writes_output(self, tmp_path: Path) -> None:
        """transpile_file() writes generated code to output_path and returns it."""
        manifest_file = tmp_path / "logic.amarooi.json"
        manifest_file.write_text(json.dumps(_manifest_payload()), encoding="utf-8")

        valid_code = "def is_even(n: int) -> bool:\n    return n % 2 == 0\n"
        client = _make_mock_client(valid_code)

        output_file = tmp_path / "output.py"

        with patch("amarooi.transpiler.engine.get_settings"):
            engine = TranspilerEngine(client=client)

        result = engine.transpile_file(manifest_file, output_file)

        assert output_file.exists()
        assert output_file.read_text(encoding="utf-8") == valid_code.strip()
        assert result == valid_code.strip()

    def test_transpile_file_raises_on_bad_manifest(self, tmp_path: Path) -> None:
        """transpile_file() raises ManifestValidationError for invalid manifests."""
        from amarooi.core.exceptions import ManifestValidationError

        bad_manifest = tmp_path / "bad.amarooi.json"
        bad_manifest.write_text("{invalid json{{", encoding="utf-8")

        with patch("amarooi.transpiler.engine.get_settings"):
            engine = TranspilerEngine(client=MagicMock())

        with pytest.raises(ManifestValidationError):
            engine.transpile_file(bad_manifest, tmp_path / "out.py")
