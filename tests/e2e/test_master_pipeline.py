"""Master End-to-End Integration Suite for Amarooi.

Exercises the complete SDLC chain across all subsystems:
  Stage A – Unstructured Spec Synthesis
  Stage B – Legacy Python AST Extraction
  Stage C – Z3 Formal Verification (invariants + F≡G equivalence)
  Stage D – Multi-File Scaffolding (amarooi.json manifest)
  Stage E – Polyglot Transpilation across all 9 target languages

All LLM calls are mocked; no real API key is required.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Shared helpers / fixtures
# ---------------------------------------------------------------------------

_MINIMAL_PYTHON_SOURCE = '''\
def check_balance(balance: int, amount: int) -> bool:
    """Return True when the balance covers the amount."""
    remaining: int = balance - amount
    if remaining < 0:
        return False
    return True
'''

_DETAILED_PROMPT = (
    "Build a rate-limiter that tracks state variables request_count and window_start. "
    "Invariant: request_count must never exceed max_requests. "
    "Failure modes: timeout, retry exceeded, invalid token. "
    "Loop: process each incoming request and check the time window. "
    "Transition: reset window when expired."
)


def _make_manifest_dict(target: str = "python") -> dict:
    return {
        "meta": {
            "project_name": "Master Pipeline Test",
            "version": "1.0.0",
            "generated_at": "2026-08-13T00:00:00Z",
            "engine_version": "2.0.0",
        },
        "context": {
            "problem_statement": "Check whether a bank account balance covers a withdrawal amount.",
            "target_language": target,
            "runtime_constraints": [],
        },
        "state_matrix": {
            "variables": [
                {
                    "name": "balance",
                    "type": "int",
                    "description": "Current account balance.",
                    "allowed_values": None,
                },
                {
                    "name": "amount",
                    "type": "int",
                    "description": "Requested withdrawal amount.",
                    "allowed_values": None,
                },
            ],
            "invariants": ["balance >= 0"],
        },
        "logic_gates": [
            {
                "gate_id": "gate-1",
                "condition": "balance >= amount",
                "on_true": "approve",
                "on_false": "reject",
            }
        ],
        "edge_cases": [
            {
                "scenario": "amount is zero",
                "fallback_action": "approve",
            }
        ],
    }


# ---------------------------------------------------------------------------
# Stage A – Unstructured Spec Synthesis
# ---------------------------------------------------------------------------

class TestStageAUnstructuredSpecSynthesis:
    """Stage A: raw prompt → validated .amarooi spec contract."""

    def test_evaluate_detailed_prompt_passes_threshold(self) -> None:
        """A sufficiently detailed prompt should pass the spec-completeness check."""
        from amarooi.core.synthesis import SynthesisEngine

        engine = SynthesisEngine(llm_client=MagicMock())
        result = engine.evaluate_prompt(_DETAILED_PROMPT)

        assert result.is_detailed, (
            f"Expected detailed prompt to pass; keyword_hits={result.keyword_hits}"
        )
        assert len(result.keyword_hits) >= 3

    def test_evaluate_vague_prompt_fails_threshold(self) -> None:
        """A vague one-liner should fail the spec-completeness threshold."""
        from amarooi.core.synthesis import SynthesisEngine

        engine = SynthesisEngine(llm_client=MagicMock())
        result = engine.evaluate_prompt("Build something.")

        assert not result.is_detailed

    def test_synthesize_spec_produces_contract_text(self) -> None:
        """synthesize_spec() should return the LLM-produced contract text."""
        from amarooi.core.synthesis import SynthesisEngine

        mock_client = MagicMock()
        mock_client.generate_completion.return_value = (
            "COMPONENT: rate_limiter\n"
            "STATE: request_count int = 0\n"
            "INVARIANT: request_count >= 0\n"
            "FAILURE: timeout\n"
        )

        engine = SynthesisEngine(llm_client=mock_client)
        contract_text = engine.synthesize_spec(_DETAILED_PROMPT)

        assert isinstance(contract_text, str)
        assert len(contract_text) > 0

    def test_synthesize_writes_file(self, tmp_path: Path) -> None:
        """synthesize() should write the spec contract to disk."""
        from amarooi.core.synthesis import SynthesisEngine

        contract_body = (
            "COMPONENT: rate_limiter\n"
            "STATE: request_count int = 0\n"
            "INVARIANT: request_count >= 0\n"
        )
        mock_client = MagicMock()
        mock_client.generate_completion.return_value = contract_body

        engine = SynthesisEngine(llm_client=mock_client)
        spec_path = engine.synthesize(_DETAILED_PROMPT, output_dir=tmp_path)

        assert spec_path.exists(), f"Expected spec file at {spec_path}"
        assert spec_path.suffix == ".amarooi"
        content = spec_path.read_text(encoding="utf-8")
        assert len(content) > 0


# ---------------------------------------------------------------------------
# Stage B – Legacy AST Extraction
# ---------------------------------------------------------------------------

class TestStageBLegacyExtraction:
    """Stage B: legacy Python source → decompiled SpecContract."""

    def test_extract_returns_spec_contract(self) -> None:
        """PythonExtractor should return a valid SpecContract."""
        from amarooi.core.extractor.python_extractor import PythonExtractor
        from amarooi.core.spec import SpecContract

        extractor = PythonExtractor()
        spec = extractor.extract(_MINIMAL_PYTHON_SOURCE)

        assert isinstance(spec, SpecContract)

    def test_extract_component_name(self) -> None:
        """Component name should match the top-level function name."""
        from amarooi.core.extractor.python_extractor import PythonExtractor

        spec = PythonExtractor().extract(_MINIMAL_PYTHON_SOURCE)
        assert spec.component_name == "check_balance"

    def test_extract_state_variables_populated(self) -> None:
        """State registers should be extracted from annotated assignments."""
        from amarooi.core.extractor.python_extractor import PythonExtractor

        spec = PythonExtractor().extract(_MINIMAL_PYTHON_SOURCE)
        var_names = [sv.name for sv in spec.state_variables]
        assert "remaining" in var_names

    def test_extract_inputs_populated(self) -> None:
        """Input parameters should be extracted from function signature."""
        from amarooi.core.extractor.python_extractor import PythonExtractor

        spec = PythonExtractor().extract(_MINIMAL_PYTHON_SOURCE)
        input_names = [p.name for p in spec.inputs]
        assert "balance" in input_names
        assert "amount" in input_names

    def test_extract_steps_populated(self) -> None:
        """Execution steps (branch, return) should be detected."""
        from amarooi.core.extractor.python_extractor import PythonExtractor

        spec = PythonExtractor().extract(_MINIMAL_PYTHON_SOURCE)
        kinds = {s.kind for s in spec.steps}
        assert "branch" in kinds or "return" in kinds

    def test_extract_via_factory(self) -> None:
        """ExtractorFactory should produce a PythonExtractor for 'python'."""
        from amarooi.core.extractor.factory import ExtractorFactory

        extractor = ExtractorFactory().get_extractor("python")
        spec = extractor.extract(_MINIMAL_PYTHON_SOURCE)
        assert spec.component_name == "check_balance"


# ---------------------------------------------------------------------------
# Stage C – Z3 Formal Verification
# ---------------------------------------------------------------------------

class TestStageCFormalVerification:
    """Stage C: Z3 invariant proof + F≡G equivalence."""

    def _make_spec(self, name: str = "balance_check"):
        from amarooi.core.spec import SpecContract, StateVariable

        return SpecContract(
            component_name=name,
            state_variables=[
                StateVariable(name="balance", type_hint="int", initial_value=100),
                StateVariable(name="amount", type_hint="int", initial_value=50),
            ],
            preconditions=["balance >= 0", "amount >= 0"],
            postconditions=["balance >= 0"],
            invariants=["balance >= 0"],
        )

    def test_verify_invariants_returns_unsat_for_valid_spec(self) -> None:
        """Post-condition verification should return unsat (proven) for a valid spec."""
        from amarooi.core.verifier import FormalVerifier

        spec = self._make_spec()
        result = FormalVerifier().verify_invariants(spec)

        assert result["result"] == "unsat"
        assert result["proven"] is True

    def test_verify_invariants_returns_sat_for_violated_spec(self) -> None:
        """A spec whose invariant can be violated should return sat + counterexample."""
        from amarooi.core.spec import SpecContract, StateVariable
        from amarooi.core.verifier import FormalVerifier

        spec = SpecContract(
            component_name="broken_check",
            state_variables=[
                StateVariable(name="balance", type_hint="int", initial_value=0),
            ],
            # No pre-condition restricts balance; invariant requires balance > 0
            invariants=["balance > 0"],
        )
        result = FormalVerifier().verify_invariants(spec)

        assert result["result"] == "sat"
        assert result["proven"] is False
        assert "counterexample" in result

    def test_equivalence_identical_specs_are_proven(self) -> None:
        """F≡G: two identical specs should be formally equivalent (unsat)."""
        from amarooi.core.verifier import FormalVerifier

        spec_f = self._make_spec("legacy_model")
        spec_g = self._make_spec("transpiled_model")
        result = FormalVerifier().check_equivalence(spec_f, spec_g)

        assert result["result"] == "unsat"
        assert result["proven"] is True

    def test_equivalence_divergent_specs_return_sat(self) -> None:
        """F≡G: specs with contradictory post-conditions should diverge (sat)."""
        from amarooi.core.spec import SpecContract, StateVariable
        from amarooi.core.verifier import FormalVerifier

        spec_f = SpecContract(
            component_name="model_f",
            state_variables=[StateVariable(name="x", type_hint="int")],
            invariants=["x >= 0"],
        )
        spec_g = SpecContract(
            component_name="model_g",
            state_variables=[StateVariable(name="x", type_hint="int")],
            invariants=["x < 0"],
        )
        result = FormalVerifier().check_equivalence(spec_f, spec_g)

        assert result["result"] == "sat"
        assert result["proven"] is False


# ---------------------------------------------------------------------------
# Stage D – Multi-File Scaffolding
# ---------------------------------------------------------------------------

class TestStageDScaffolding:
    """Stage D: amarooi.json manifest generation + cross-contract linking."""

    def test_manifest_generated_with_all_components(self, tmp_path: Path) -> None:
        """write_manifest() should produce a valid amarooi.json file."""
        from amarooi.core.scaffold import ComponentSpec, ScaffoldEngine

        engine = ScaffoldEngine(project_root=tmp_path)
        engine.add_component(ComponentSpec(
            name="Database",
            path="logic/database.amarooi",
            outputs={"user_record": "dict"},
            description="Database access layer.",
        ))
        engine.add_component(ComponentSpec(
            name="SecurityAuth",
            path="logic/auth.amarooi",
            inputs={"user_record": "dict"},
            outputs={"auth_token": "str"},
            description="Security/Auth component.",
        ))
        engine.add_component(ComponentSpec(
            name="ExecutionLoop",
            path="logic/execution.amarooi",
            inputs={"auth_token": "str"},
            description="Main execution loop.",
        ))

        manifest_path = engine.write_manifest()

        assert manifest_path.exists()
        raw = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert raw["version"] == "1.0"
        component_names = [c["name"] for c in raw["components"]]
        assert "Database" in component_names
        assert "SecurityAuth" in component_names
        assert "ExecutionLoop" in component_names

    def test_cross_contract_interface_linking_no_mismatches(self, tmp_path: Path) -> None:
        """Components with matching interface types should pass validation."""
        from amarooi.core.scaffold import ComponentSpec, ScaffoldEngine

        engine = ScaffoldEngine(project_root=tmp_path)
        engine.add_component(ComponentSpec(
            name="Database",
            path="logic/db.amarooi",
            outputs={"user_record": "dict"},
        ))
        engine.add_component(ComponentSpec(
            name="SecurityAuth",
            path="logic/auth.amarooi",
            inputs={"user_record": "dict"},
        ))

        mismatches = engine.validate_contracts()
        assert mismatches == []

    def test_cross_contract_mismatch_detected(self, tmp_path: Path) -> None:
        """Type mismatch between producer output and consumer input is surfaced."""
        from amarooi.core.scaffold import ComponentSpec, ScaffoldEngine

        engine = ScaffoldEngine(project_root=tmp_path)
        engine.add_component(ComponentSpec(
            name="Database",
            path="logic/db.amarooi",
            outputs={"user_record": "dict"},
        ))
        engine.add_component(ComponentSpec(
            name="SecurityAuth",
            path="logic/auth.amarooi",
            inputs={"user_record": "str"},  # type mismatch
        ))

        mismatches = engine.validate_contracts()
        assert len(mismatches) == 1
        assert mismatches[0].parameter == "user_record"

    def test_load_manifest_round_trip(self, tmp_path: Path) -> None:
        """A written manifest can be reloaded with all components intact."""
        from amarooi.core.scaffold import ComponentSpec, ScaffoldEngine

        engine = ScaffoldEngine(project_root=tmp_path)
        engine.add_component(ComponentSpec(name="Database", path="logic/db.amarooi"))
        engine.write_manifest()

        loaded = ScaffoldEngine.load_manifest(tmp_path / "amarooi.json")
        assert "Database" in loaded.components


# ---------------------------------------------------------------------------
# Stage E – Polyglot Transpilation across all 9 languages
# ---------------------------------------------------------------------------

_ALL_TARGETS = [
    ("py", "python", ".py"),
    ("rs", "rust", ".rs"),
    ("cpp", "c++", ".cpp"),
    ("java", "java", ".java"),
    ("ts", "typescript", ".ts"),
    ("cobol", "cobol", ".cbl"),
    ("js", "javascript", ".js"),
    ("go", "go", ".go"),
    ("cs", "csharp", ".cs"),
]

_VALID_PYTHON_CODE = (
    "def check_balance(balance: int, amount: int) -> bool:\n"
    "    return balance >= amount\n"
)
_GENERIC_CODE = "// generated code placeholder"


def _mock_client_for_target(target: str) -> MagicMock:
    """Return a mock LLM client whose response is valid for *target*."""
    client = MagicMock()
    if target == "python":
        client.generate_completion.return_value = _VALID_PYTHON_CODE
    else:
        client.generate_completion.return_value = _GENERIC_CODE
    return client


class TestStageEPolyglotTranspilation:
    """Stage E: transpile a single .amarooi spec across all 9 target languages."""

    @pytest.mark.parametrize("alias,canonical,expected_ext", _ALL_TARGETS)
    def test_alias_resolves_to_canonical(
        self, alias: str, canonical: str, expected_ext: str
    ) -> None:
        """Each CLI alias should resolve to the correct canonical language name."""
        from amarooi.core.workspace import normalize_target

        assert normalize_target(alias) == canonical

    @pytest.mark.parametrize("alias,canonical,expected_ext", _ALL_TARGETS)
    def test_extension_matches_language(
        self, alias: str, canonical: str, expected_ext: str
    ) -> None:
        """target_extension() should return the correct file extension."""
        from amarooi.core.workspace import target_extension

        assert target_extension(canonical) == expected_ext

    @pytest.mark.parametrize("alias,canonical,expected_ext", _ALL_TARGETS)
    def test_transpile_produces_output(
        self, alias: str, canonical: str, expected_ext: str, tmp_path: Path
    ) -> None:
        """TranspilerEngine.transpile() should return non-empty code for every target."""
        from amarooi.planner.schemas import LogicManifest
        from amarooi.transpiler.engine import TranspilerEngine

        manifest = LogicManifest.model_validate(_make_manifest_dict(canonical))
        client = _mock_client_for_target(canonical)

        with patch("amarooi.transpiler.engine.get_settings"):
            engine = TranspilerEngine(client=client)

        code = engine.transpile(manifest, target_language=canonical)
        assert isinstance(code, str)
        assert len(code) > 0

    @pytest.mark.parametrize("alias,canonical,expected_ext", _ALL_TARGETS)
    def test_transpile_file_written_with_correct_extension(
        self, alias: str, canonical: str, expected_ext: str, tmp_path: Path
    ) -> None:
        """transpile_file() should write output with the correct extension under src_generated/<lang>/."""
        from amarooi.planner.manifest import ManifestEngine
        from amarooi.planner.schemas import LogicManifest
        from amarooi.transpiler.engine import TranspilerEngine

        manifest_dict = _make_manifest_dict(canonical)
        manifest_dict["context"]["target_language"] = canonical
        manifest = LogicManifest.model_validate(manifest_dict)

        manifest_path = tmp_path / "test.amarooi.json"
        ManifestEngine.save_manifest(manifest, manifest_path)

        client = _mock_client_for_target(canonical)
        output_path = tmp_path / "src_generated" / canonical / f"check_balance{expected_ext}"

        with patch("amarooi.transpiler.engine.get_settings"):
            engine = TranspilerEngine(client=client)

        engine.transpile_file(
            manifest_path=manifest_path,
            output_path=output_path,
            target_language=canonical,
        )

        assert output_path.exists(), f"Expected output at {output_path}"
        assert output_path.suffix == expected_ext
        assert output_path.read_text(encoding="utf-8").strip() != ""


# ---------------------------------------------------------------------------
# Full smoke-test: chain all stages together
# ---------------------------------------------------------------------------

class TestFullPipelineSmokeTest:
    """Smoke test: chain Stages B → C → D → E in a single pass."""

    def test_extract_verify_scaffold_transpile(self, tmp_path: Path) -> None:
        """Full pipeline: extract spec → verify → scaffold → transpile to Python."""
        from amarooi.core.extractor.python_extractor import PythonExtractor
        from amarooi.core.scaffold import ComponentSpec, ScaffoldEngine
        from amarooi.core.spec import SpecContract
        from amarooi.core.verifier import FormalVerifier
        from amarooi.planner.manifest import ManifestEngine
        from amarooi.planner.schemas import LogicManifest
        from amarooi.transpiler.engine import TranspilerEngine

        # Stage B: extract
        spec: SpecContract = PythonExtractor().extract(_MINIMAL_PYTHON_SOURCE)
        assert spec.component_name == "check_balance"

        # Stage C: verify
        verifier = FormalVerifier()
        inv_result = verifier.verify_invariants(spec)
        # No numeric invariants in the minimal source → vacuously proven
        assert inv_result["proven"] is True

        # Stage D: scaffold
        engine = ScaffoldEngine(project_root=tmp_path)
        engine.add_component(ComponentSpec(
            name="Database",
            path="logic/db.amarooi",
            outputs={"user_record": "dict"},
        ))
        engine.add_component(ComponentSpec(
            name="SecurityAuth",
            path="logic/auth.amarooi",
            inputs={"user_record": "dict"},
        ))
        engine.add_component(ComponentSpec(
            name="ExecutionLoop",
            path="logic/execution.amarooi",
            inputs={"auth_token": "str"},
        ))
        manifest_path = engine.write_manifest()
        assert manifest_path.exists()
        mismatches = engine.validate_contracts()
        assert mismatches == []

        # Stage E: transpile to Python
        logic_manifest = LogicManifest.model_validate(_make_manifest_dict("python"))
        lm_path = tmp_path / "master.amarooi.json"
        ManifestEngine.save_manifest(logic_manifest, lm_path)

        client = _mock_client_for_target("python")
        out_path = tmp_path / "src_generated" / "python" / "check_balance.py"

        with patch("amarooi.transpiler.engine.get_settings"):
            transpiler = TranspilerEngine(client=client)

        transpiler.transpile_file(
            manifest_path=lm_path,
            output_path=out_path,
            target_language="python",
        )

        assert out_path.exists()
        assert out_path.suffix == ".py"
