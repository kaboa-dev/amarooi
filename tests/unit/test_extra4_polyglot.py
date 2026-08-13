"""Unit tests for Phase 10 Extra 4: Polyglot target transpilers.

Covers:
- Target flag resolution for cobol, js, go, and csharp aliases.
- AST / syntax generation for each target.
- Output directory resolution to ``src_generated/<language>/``.
"""

from __future__ import annotations

import pytest

from amarooi.core.workspace import normalize_target, target_extension, TARGET_ALIASES
from amarooi.core.transpiler import (
    BaseTargetTranspiler,
    CobolTranspiler,
    CSharpTranspiler,
    GoTranspiler,
    JavaScriptTranspiler,
)
from amarooi.planner.schemas import LogicManifest


# ---------------------------------------------------------------------------
# Shared manifest fixture
# ---------------------------------------------------------------------------

def _make_manifest(target: str = "python") -> LogicManifest:
    return LogicManifest.model_validate(
        {
            "meta": {
                "project_name": "Even Odd Checker",
                "version": "1.0.0",
                "generated_at": "2026-08-13T00:00:00Z",
                "engine_version": "2.0.0",
            },
            "context": {
                "problem_statement": "Determine if a number is even or odd.",
                "target_language": target,
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
    )


# ---------------------------------------------------------------------------
# Target flag resolution
# ---------------------------------------------------------------------------

class TestTargetFlagResolution:
    """normalize_target() resolves all new language aliases."""

    @pytest.mark.parametrize("alias,expected", [
        ("cobol", "cobol"),
        ("cob", "cobol"),
        ("js", "javascript"),
        ("javascript", "javascript"),
        ("go", "go"),
        ("golang", "go"),
        ("cs", "csharp"),
        ("csharp", "csharp"),
    ])
    def test_alias_resolves(self, alias: str, expected: str) -> None:
        assert normalize_target(alias) == expected

    @pytest.mark.parametrize("alias,expected_ext", [
        ("cobol", ".cbl"),
        ("cob", ".cbl"),
        ("js", ".js"),
        ("javascript", ".js"),
        ("go", ".go"),
        ("golang", ".go"),
        ("cs", ".cs"),
        ("csharp", ".cs"),
    ])
    def test_extension(self, alias: str, expected_ext: str) -> None:
        assert target_extension(alias) == expected_ext


# ---------------------------------------------------------------------------
# COBOL generator
# ---------------------------------------------------------------------------

class TestCobolTranspiler:
    """CobolTranspiler generates structurally correct COBOL."""

    def setup_method(self) -> None:
        self.transpiler = CobolTranspiler()
        self.manifest = _make_manifest("cobol")

    def test_contains_identification_division(self) -> None:
        code = self.transpiler.generate(self.manifest)
        assert "IDENTIFICATION DIVISION" in code

    def test_contains_environment_division(self) -> None:
        code = self.transpiler.generate(self.manifest)
        assert "ENVIRONMENT DIVISION" in code

    def test_contains_data_division(self) -> None:
        code = self.transpiler.generate(self.manifest)
        assert "DATA DIVISION" in code

    def test_contains_working_storage_section(self) -> None:
        code = self.transpiler.generate(self.manifest)
        assert "WORKING-STORAGE SECTION" in code

    def test_contains_procedure_division(self) -> None:
        code = self.transpiler.generate(self.manifest)
        assert "PROCEDURE DIVISION" in code

    def test_state_variable_mapped(self) -> None:
        code = self.transpiler.generate(self.manifest)
        assert "WS-NUMBER" in code

    def test_invariant_gate_present(self) -> None:
        code = self.transpiler.generate(self.manifest)
        assert "EVALUATE" in code

    def test_logic_gate_present(self) -> None:
        code = self.transpiler.generate(self.manifest)
        assert "IF" in code

    def test_registered_in_base(self) -> None:
        t = BaseTargetTranspiler.for_target("cobol")
        assert isinstance(t, CobolTranspiler)


# ---------------------------------------------------------------------------
# JavaScript generator
# ---------------------------------------------------------------------------

class TestJavaScriptTranspiler:
    """JavaScriptTranspiler generates structurally correct ES6+ JS."""

    def setup_method(self) -> None:
        self.transpiler = JavaScriptTranspiler()
        self.manifest = _make_manifest("javascript")

    def test_contains_async_function(self) -> None:
        code = self.transpiler.generate(self.manifest)
        assert "async function" in code

    def test_contains_type_error(self) -> None:
        code = self.transpiler.generate(self.manifest)
        assert "TypeError" in code

    def test_contains_module_exports(self) -> None:
        code = self.transpiler.generate(self.manifest)
        assert "module.exports" in code

    def test_contains_export_default(self) -> None:
        code = self.transpiler.generate(self.manifest)
        assert "export default" in code

    def test_logic_gate_present(self) -> None:
        code = self.transpiler.generate(self.manifest)
        assert "if (" in code

    def test_registered_in_base(self) -> None:
        t = BaseTargetTranspiler.for_target("javascript")
        assert isinstance(t, JavaScriptTranspiler)


# ---------------------------------------------------------------------------
# Go generator
# ---------------------------------------------------------------------------

class TestGoTranspiler:
    """GoTranspiler generates structurally correct Go."""

    def setup_method(self) -> None:
        self.transpiler = GoTranspiler()
        self.manifest = _make_manifest("go")

    def test_contains_package_main(self) -> None:
        code = self.transpiler.generate(self.manifest)
        assert "package main" in code

    def test_contains_state_struct(self) -> None:
        code = self.transpiler.generate(self.manifest)
        assert "type State struct" in code

    def test_contains_multi_return(self) -> None:
        code = self.transpiler.generate(self.manifest)
        assert "(Result, error)" in code

    def test_invariant_check_uses_fmt_errorf(self) -> None:
        code = self.transpiler.generate(self.manifest)
        assert "fmt.Errorf" in code

    def test_logic_gate_present(self) -> None:
        code = self.transpiler.generate(self.manifest)
        assert "if " in code

    def test_registered_in_base(self) -> None:
        t = BaseTargetTranspiler.for_target("go")
        assert isinstance(t, GoTranspiler)


# ---------------------------------------------------------------------------
# C# generator
# ---------------------------------------------------------------------------

class TestCSharpTranspiler:
    """CSharpTranspiler generates structurally correct C#."""

    def setup_method(self) -> None:
        self.transpiler = CSharpTranspiler()
        self.manifest = _make_manifest("csharp")

    def test_contains_namespace(self) -> None:
        code = self.transpiler.generate(self.manifest)
        assert "namespace" in code

    def test_contains_record(self) -> None:
        code = self.transpiler.generate(self.manifest)
        assert "record State" in code

    def test_contains_static_class(self) -> None:
        code = self.transpiler.generate(self.manifest)
        assert "public static class" in code

    def test_contains_argument_exception(self) -> None:
        code = self.transpiler.generate(self.manifest)
        assert "ArgumentException" in code

    def test_logic_gate_present(self) -> None:
        code = self.transpiler.generate(self.manifest)
        assert "if (" in code

    def test_registered_in_base(self) -> None:
        t = BaseTargetTranspiler.for_target("csharp")
        assert isinstance(t, CSharpTranspiler)


# ---------------------------------------------------------------------------
# Output directory resolution
# ---------------------------------------------------------------------------

class TestOutputDirectoryResolution:
    """ProjectWorkspace derives src_generated/<language>/ for new targets."""

    @pytest.mark.parametrize("alias,expected_dir", [
        ("cobol", "cobol"),
        ("cob", "cobol"),
        ("js", "javascript"),
        ("javascript", "javascript"),
        ("go", "go"),
        ("golang", "go"),
        ("cs", "csharp"),
        ("csharp", "csharp"),
    ])
    def test_generated_dir_for_target(
        self, alias: str, expected_dir: str, tmp_path: pytest.TempdirFactory
    ) -> None:
        from amarooi.core.workspace import ProjectWorkspace

        workspace = ProjectWorkspace(root_dir=tmp_path)
        gen_dir = workspace.ensure_generated_dir(alias)
        assert gen_dir.name == expected_dir
        assert gen_dir.parent.name == "src_generated"
        assert gen_dir.exists()
