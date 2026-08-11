"""Unit tests for Phase 5: SDLC Wizard (NaturalLogicGenerator & SDLCArchitect)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from amarooi.planner.generator import NaturalLogicGenerator, WorkspaceManager


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def workspace(tmp_path: Path) -> WorkspaceManager:
    """Return a WorkspaceManager pointing at a temporary directory."""
    return WorkspaceManager(workspace_dir=tmp_path / "logic")


@pytest.fixture()
def generator(workspace: WorkspaceManager) -> NaturalLogicGenerator:
    """Return a NaturalLogicGenerator backed by the tmp workspace."""
    return NaturalLogicGenerator(workspace=workspace)


def _sample_answers() -> dict:
    """Return a representative set of interview answers."""
    return {
        "inputs_outputs": "city name → weather JSON",
        "state_variables": "last_fetched_at, cache",
        "execution_steps": "Fetch URL, Parse JSON, Update cache",
        "edge_cases": "API timeout, Empty response",
    }


# ---------------------------------------------------------------------------
# WorkspaceManager tests
# ---------------------------------------------------------------------------


class TestWorkspaceManager:
    def test_ensure_dir_creates_directory(self, tmp_path: Path) -> None:
        wm = WorkspaceManager(workspace_dir=tmp_path / "logic")
        assert not wm.workspace_dir.exists()
        wm.ensure_dir()
        assert wm.workspace_dir.is_dir()

    def test_filepath_returns_amarooi_extension(self, workspace: WorkspaceManager) -> None:
        path = workspace.filepath("rate_limiter")
        assert path.suffix == ".amarooi"
        assert path.name == "rate_limiter.amarooi"

    def test_filepath_normalises_spaces(self, workspace: WorkspaceManager) -> None:
        path = workspace.filepath("My Component")
        assert path.name == "my_component.amarooi"

    def test_write_creates_file_with_content(self, workspace: WorkspaceManager) -> None:
        content = "Component: rate_limiter\n"
        path = workspace.write("rate_limiter", content)
        assert path.exists()
        assert path.read_text(encoding="utf-8") == content


# ---------------------------------------------------------------------------
# NaturalLogicGenerator.render tests
# ---------------------------------------------------------------------------


class TestNaturalLogicGeneratorRender:
    def test_render_contains_component_name(self, generator: NaturalLogicGenerator) -> None:
        text = generator.render("api_fetcher", _sample_answers())
        assert "Component: api_fetcher" in text

    def test_render_contains_initialize_block(self, generator: NaturalLogicGenerator) -> None:
        text = generator.render("api_fetcher", _sample_answers())
        assert "Initialize:" in text

    def test_render_contains_inputs_outputs(self, generator: NaturalLogicGenerator) -> None:
        text = generator.render("api_fetcher", _sample_answers())
        assert "city name → weather JSON" in text

    def test_render_contains_state_variables(self, generator: NaturalLogicGenerator) -> None:
        text = generator.render("api_fetcher", _sample_answers())
        assert "last_fetched_at, cache" in text

    def test_render_numbers_execution_steps(self, generator: NaturalLogicGenerator) -> None:
        text = generator.render("api_fetcher", _sample_answers())
        assert "Step 1:" in text
        assert "Step 2:" in text
        assert "Step 3:" in text

    def test_render_formats_edge_cases(self, generator: NaturalLogicGenerator) -> None:
        text = generator.render("api_fetcher", _sample_answers())
        assert "Edge Cases:" in text
        assert "If API timeout: End" in text
        assert "If Empty response: End" in text

    def test_render_handles_list_steps(self, generator: NaturalLogicGenerator) -> None:
        answers = {
            "inputs_outputs": "x → y",
            "state_variables": "count",
            "execution_steps": ["Step A", "Step B"],
            "edge_cases": [],
        }
        text = generator.render("comp", answers)
        assert "Step 1: Step A" in text
        assert "Step 2: Step B" in text

    def test_render_handles_empty_answers(self, generator: NaturalLogicGenerator) -> None:
        text = generator.render("empty_comp", {})
        assert "Component: empty_comp" in text
        assert "(none)" in text

    def test_render_ends_with_newline(self, generator: NaturalLogicGenerator) -> None:
        text = generator.render("comp", _sample_answers())
        assert text.endswith("\n")


# ---------------------------------------------------------------------------
# NaturalLogicGenerator.generate tests
# ---------------------------------------------------------------------------


class TestNaturalLogicGeneratorGenerate:
    def test_generate_writes_file(self, generator: NaturalLogicGenerator) -> None:
        path = generator.generate("api_fetcher", _sample_answers())
        assert path.exists()
        assert path.suffix == ".amarooi"

    def test_generate_file_content_is_correct(self, generator: NaturalLogicGenerator) -> None:
        path = generator.generate("api_fetcher", _sample_answers())
        content = path.read_text(encoding="utf-8")
        assert "Component: api_fetcher" in content

    def test_generate_all_creates_multiple_files(
        self, generator: NaturalLogicGenerator
    ) -> None:
        components = {
            "api_fetcher": _sample_answers(),
            "rate_limiter": {
                "inputs_outputs": "request → bool",
                "state_variables": "window_start, count",
                "execution_steps": "Check window, Increment count, Return allowed",
                "edge_cases": "Window expired",
            },
        }
        result = generator.generate_all(components)
        assert len(result) == 2
        for name, path in result.items():
            assert Path(path).exists()
            assert Path(path).suffix == ".amarooi"


# ---------------------------------------------------------------------------
# SDLCArchitect._parse_component_list tests
# ---------------------------------------------------------------------------


class TestSDLCArchitectParseComponentList:
    def _parse(self, raw: str) -> list[str]:
        from amarooi.planner.architect import SDLCArchitect

        return SDLCArchitect._parse_component_list(raw)

    def test_parse_plain_json_array(self) -> None:
        raw = '["api_fetcher", "rate_limiter"]'
        result = self._parse(raw)
        assert result == ["api_fetcher", "rate_limiter"]

    def test_parse_strips_markdown_fences(self) -> None:
        raw = '```json\n["api_fetcher", "rate_limiter"]\n```'
        result = self._parse(raw)
        assert result == ["api_fetcher", "rate_limiter"]

    def test_parse_raises_on_invalid_json(self) -> None:
        from amarooi.core.exceptions import AmarooiException

        with pytest.raises(AmarooiException):
            self._parse("{not valid json}")

    def test_parse_raises_on_empty_list(self) -> None:
        from amarooi.core.exceptions import AmarooiException

        with pytest.raises(AmarooiException):
            self._parse("[]")

    def test_parse_raises_on_non_list(self) -> None:
        from amarooi.core.exceptions import AmarooiException

        with pytest.raises(AmarooiException):
            self._parse('{"key": "value"}')


# ---------------------------------------------------------------------------
# SDLCArchitect.run (mocked) workspace structure test
# ---------------------------------------------------------------------------


class TestSDLCArchitectRun:
    def test_run_produces_workspace_files(self, tmp_path: Path) -> None:
        """Mocked architect run should yield .amarooi files in the workspace."""
        from amarooi.planner.architect import SDLCArchitect

        workspace = WorkspaceManager(workspace_dir=tmp_path / "logic")
        mock_client = MagicMock()
        mock_client.generate_completion.return_value = json.dumps(
            ["component_a", "component_b"]
        )

        interview_responses = iter(
            [
                # component_a
                "input_a → output_a",  # inputs_outputs
                "state_a",  # state_variables
                "step 1, step 2",  # execution_steps
                "edge case a",  # edge_cases
                # component_b
                "input_b → output_b",
                "state_b",
                "step x",
                "edge case b",
            ]
        )

        with (
            patch("amarooi.planner.architect.get_settings"),
            patch(
                "amarooi.planner.architect.Prompt.ask",
                side_effect=lambda *a, **kw: next(interview_responses),
            ),
        ):
            architect = SDLCArchitect(client=mock_client, workspace=workspace)
            result = architect.run("Build a test app")

        assert "component_a" in result
        assert "component_b" in result

        for name in ("component_a", "component_b"):
            path = Path(result[name])
            assert path.exists(), f"{path} was not created"
            content = path.read_text(encoding="utf-8")
            assert f"Component: {name}" in content
