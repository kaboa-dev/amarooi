"""Unit tests for workspace resolution and target metadata helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from amarooi.core.workspace import ProjectWorkspace, normalize_target, target_badge, target_extension


class TestTargetHelpers:
    def test_normalize_target_supports_aliases(self) -> None:
        assert normalize_target("py") == "python"
        assert normalize_target("rs") == "rust"
        assert normalize_target("cpp") == "c++"
        assert normalize_target("ts") == "typescript"

    def test_target_extension_matches_canonical_target(self) -> None:
        assert target_extension("python") == ".py"
        assert target_extension("rust") == ".rs"
        assert target_extension("c++") == ".cpp"
        assert target_extension("java") == ".java"
        assert target_extension("typescript") == ".ts"

    def test_target_badge_returns_rich_markup(self) -> None:
        badge = target_badge("rust")
        assert "RUST" in badge
        assert "white on red" in badge

    def test_normalize_target_rejects_unknown_value(self) -> None:
        with pytest.raises(ValueError, match="Unsupported target"):
            normalize_target("go")


class TestProjectWorkspace:
    def test_resolve_spec_path_uses_specs_directory(self, tmp_path: Path) -> None:
        workspace = ProjectWorkspace(tmp_path)
        path = workspace.resolve_spec_path("Order Router")
        assert path == tmp_path / "specs" / "order_router.amarooi"

    def test_resolve_generated_path_is_target_isolated(self, tmp_path: Path) -> None:
        workspace = ProjectWorkspace(tmp_path)
        path = workspace.resolve_generated_path(tmp_path / "specs" / "order_router.amarooi", "rs")
        assert path == tmp_path / "src_generated" / "rust" / "order_router.rs"

    def test_resolve_extracted_spec_path_uses_extracted_specs_directory(self, tmp_path: Path) -> None:
        workspace = ProjectWorkspace(tmp_path)
        path = workspace.resolve_extracted_spec_path(tmp_path / "legacy.py")
        assert path == tmp_path / "extracted_specs" / "legacy.amarooi.json"

    def test_from_path_uses_repo_root_above_specs_directory(self, tmp_path: Path) -> None:
        spec_path = tmp_path / "specs" / "order_router.amarooi"
        spec_path.parent.mkdir()
        spec_path.write_text("Component: order_router\n", encoding="utf-8")
        workspace = ProjectWorkspace.from_path(spec_path)
        assert workspace.root_dir == tmp_path
