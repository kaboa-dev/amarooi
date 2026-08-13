"""Unit tests for Phase 9: Multi-File Component Scaffolding (scaffold.py)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from amarooi.core.scaffold import ComponentSpec, ContractMismatch, ScaffoldEngine


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_engine(tmp_path: Path) -> ScaffoldEngine:
    return ScaffoldEngine(project_root=tmp_path)


def _db_spec() -> ComponentSpec:
    return ComponentSpec(
        name="db",
        path="logic/db.amarooi",
        outputs={"user_record": "dict", "user_id": "int"},
        description="Database access layer",
    )


def _auth_spec() -> ComponentSpec:
    return ComponentSpec(
        name="auth",
        path="logic/auth.amarooi",
        inputs={"user_record": "dict"},
        outputs={"token": "str"},
        description="Authentication component",
    )


def _router_spec() -> ComponentSpec:
    return ComponentSpec(
        name="order_router",
        path="logic/order_router.amarooi",
        inputs={"user_id": "int"},
        outputs={"order_id": "str"},
        description="Order routing component",
    )


# ---------------------------------------------------------------------------
# ComponentSpec
# ---------------------------------------------------------------------------


class TestComponentSpec:
    def test_defaults(self) -> None:
        spec = ComponentSpec(name="foo", path="foo.amarooi")
        assert spec.inputs == {}
        assert spec.outputs == {}
        assert spec.description == ""


# ---------------------------------------------------------------------------
# ScaffoldEngine – registration
# ---------------------------------------------------------------------------


class TestScaffoldEngineRegistration:
    def test_add_and_retrieve_component(self, tmp_path: Path) -> None:
        engine = _make_engine(tmp_path)
        engine.add_component(_db_spec())
        assert "db" in engine.components

    def test_duplicate_name_raises(self, tmp_path: Path) -> None:
        engine = _make_engine(tmp_path)
        engine.add_component(_db_spec())
        with pytest.raises(ValueError, match="already registered"):
            engine.add_component(_db_spec())

    def test_remove_component(self, tmp_path: Path) -> None:
        engine = _make_engine(tmp_path)
        engine.add_component(_db_spec())
        engine.remove_component("db")
        assert "db" not in engine.components

    def test_remove_nonexistent_is_noop(self, tmp_path: Path) -> None:
        engine = _make_engine(tmp_path)
        engine.remove_component("nonexistent")  # should not raise

    def test_components_is_copy(self, tmp_path: Path) -> None:
        engine = _make_engine(tmp_path)
        engine.add_component(_db_spec())
        snap = engine.components
        snap["db"] = ComponentSpec(name="db", path="other.amarooi")
        assert engine.components["db"].path == "logic/db.amarooi"


# ---------------------------------------------------------------------------
# ScaffoldEngine – manifest generation
# ---------------------------------------------------------------------------


class TestManifestGeneration:
    def test_build_manifest_structure(self, tmp_path: Path) -> None:
        engine = _make_engine(tmp_path)
        engine.add_component(_db_spec())
        engine.add_component(_auth_spec())
        manifest = engine.build_manifest()
        assert manifest["version"] == "1.0"
        assert len(manifest["components"]) == 2
        names = [c["name"] for c in manifest["components"]]
        assert "db" in names
        assert "auth" in names

    def test_write_manifest_creates_file(self, tmp_path: Path) -> None:
        engine = _make_engine(tmp_path)
        engine.add_component(_db_spec())
        manifest_path = engine.write_manifest()
        assert manifest_path.exists()
        data = json.loads(manifest_path.read_text())
        assert data["version"] == "1.0"

    def test_write_manifest_custom_dest(self, tmp_path: Path) -> None:
        engine = _make_engine(tmp_path)
        engine.add_component(_db_spec())
        custom = tmp_path / "sub" / "custom.json"
        engine.write_manifest(dest=custom)
        assert custom.exists()

    def test_manifest_components_include_inputs_outputs(self, tmp_path: Path) -> None:
        engine = _make_engine(tmp_path)
        engine.add_component(_auth_spec())
        manifest = engine.build_manifest()
        auth_comp = manifest["components"][0]
        assert auth_comp["inputs"] == {"user_record": "dict"}
        assert auth_comp["outputs"] == {"token": "str"}


# ---------------------------------------------------------------------------
# ScaffoldEngine – round-trip load
# ---------------------------------------------------------------------------


class TestManifestRoundTrip:
    def test_load_manifest_restores_components(self, tmp_path: Path) -> None:
        engine = _make_engine(tmp_path)
        engine.add_component(_db_spec())
        engine.add_component(_auth_spec())
        path = engine.write_manifest()

        loaded = ScaffoldEngine.load_manifest(path)
        assert set(loaded.components.keys()) == {"db", "auth"}

    def test_load_manifest_preserves_types(self, tmp_path: Path) -> None:
        engine = _make_engine(tmp_path)
        engine.add_component(_auth_spec())
        path = engine.write_manifest()
        loaded = ScaffoldEngine.load_manifest(path)
        auth = loaded.components["auth"]
        assert auth.inputs["user_record"] == "dict"
        assert auth.outputs["token"] == "str"

    def test_load_manifest_bad_path_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError):
            ScaffoldEngine.load_manifest(tmp_path / "nonexistent.json")


# ---------------------------------------------------------------------------
# ScaffoldEngine – contract validation (no mismatches)
# ---------------------------------------------------------------------------


class TestContractValidationClean:
    def test_no_mismatches_when_types_agree(self, tmp_path: Path) -> None:
        engine = _make_engine(tmp_path)
        engine.add_component(_db_spec())     # outputs user_record: dict, user_id: int
        engine.add_component(_auth_spec())   # inputs  user_record: dict
        engine.add_component(_router_spec()) # inputs  user_id: int
        mismatches = engine.validate_contracts()
        assert mismatches == []

    def test_no_mismatches_with_no_cross_references(self, tmp_path: Path) -> None:
        engine = _make_engine(tmp_path)
        engine.add_component(ComponentSpec(name="a", path="a.amarooi", outputs={"x": "int"}))
        engine.add_component(ComponentSpec(name="b", path="b.amarooi", outputs={"y": "str"}))
        assert engine.validate_contracts() == []

    def test_missing_producer_not_flagged_as_mismatch(self, tmp_path: Path) -> None:
        """A consumer expecting a param with no producer is NOT a mismatch (just unresolved)."""
        engine = _make_engine(tmp_path)
        engine.add_component(
            ComponentSpec(name="consumer", path="c.amarooi", inputs={"orphan_input": "str"})
        )
        assert engine.validate_contracts() == []


# ---------------------------------------------------------------------------
# ScaffoldEngine – contract validation (with mismatches)
# ---------------------------------------------------------------------------


class TestContractValidationMismatches:
    def test_type_mismatch_detected(self, tmp_path: Path) -> None:
        engine = _make_engine(tmp_path)
        engine.add_component(
            ComponentSpec(name="producer", path="p.amarooi", outputs={"user_id": "int"})
        )
        engine.add_component(
            ComponentSpec(name="consumer", path="c.amarooi", inputs={"user_id": "str"})
        )
        mismatches = engine.validate_contracts()
        assert len(mismatches) == 1
        m = mismatches[0]
        assert isinstance(m, ContractMismatch)
        assert m.producer == "producer"
        assert m.consumer == "consumer"
        assert m.parameter == "user_id"
        assert m.producer_type == "int"
        assert m.consumer_type == "str"

    def test_multiple_mismatches_detected(self, tmp_path: Path) -> None:
        engine = _make_engine(tmp_path)
        engine.add_component(
            ComponentSpec(
                name="src", path="src.amarooi",
                outputs={"a": "int", "b": "float"},
            )
        )
        engine.add_component(
            ComponentSpec(
                name="dst", path="dst.amarooi",
                inputs={"a": "str", "b": "str"},
            )
        )
        mismatches = engine.validate_contracts()
        assert len(mismatches) == 2
        params = {m.parameter for m in mismatches}
        assert params == {"a", "b"}

    def test_mismatch_message_is_descriptive(self, tmp_path: Path) -> None:
        engine = _make_engine(tmp_path)
        engine.add_component(
            ComponentSpec(name="P", path="p.amarooi", outputs={"val": "int"})
        )
        engine.add_component(
            ComponentSpec(name="C", path="c.amarooi", inputs={"val": "str"})
        )
        mismatches = engine.validate_contracts()
        assert "P" in mismatches[0].message
        assert "C" in mismatches[0].message
        assert "val" in mismatches[0].message


# ---------------------------------------------------------------------------
# ScaffoldEngine – documentation generation
# ---------------------------------------------------------------------------


class TestDocumentationGeneration:
    def test_generates_markdown_file(self, tmp_path: Path) -> None:
        engine = _make_engine(tmp_path)
        engine.add_component(_db_spec())
        engine.add_component(_auth_spec())
        doc_path = engine.generate_architecture_doc()
        assert doc_path.exists()
        content = doc_path.read_text()
        assert "# System Architecture" in content

    def test_doc_includes_component_names(self, tmp_path: Path) -> None:
        engine = _make_engine(tmp_path)
        engine.add_component(_db_spec())
        engine.add_component(_auth_spec())
        doc_path = engine.generate_architecture_doc()
        content = doc_path.read_text()
        assert "db" in content
        assert "auth" in content

    def test_doc_reports_mismatches(self, tmp_path: Path) -> None:
        engine = _make_engine(tmp_path)
        engine.add_component(
            ComponentSpec(name="A", path="a.amarooi", outputs={"x": "int"})
        )
        engine.add_component(
            ComponentSpec(name="B", path="b.amarooi", inputs={"x": "str"})
        )
        doc_path = engine.generate_architecture_doc()
        content = doc_path.read_text()
        assert "Mismatch" in content or "mismatch" in content

    def test_doc_confirms_clean_contracts(self, tmp_path: Path) -> None:
        engine = _make_engine(tmp_path)
        engine.add_component(_db_spec())
        engine.add_component(_auth_spec())
        doc_path = engine.generate_architecture_doc()
        content = doc_path.read_text()
        assert "✅" in content or "satisfied" in content.lower()

    def test_custom_doc_destination(self, tmp_path: Path) -> None:
        engine = _make_engine(tmp_path)
        engine.add_component(_db_spec())
        custom = tmp_path / "custom_docs" / "arch.md"
        doc_path = engine.generate_architecture_doc(dest=custom)
        assert doc_path == custom
        assert custom.exists()
