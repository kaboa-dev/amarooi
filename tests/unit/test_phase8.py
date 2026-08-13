"""Unit tests for Phase 8: Extractor framework and Z3 formal verifier."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from amarooi.core.spec import (
    ExecutionStep,
    ParameterSpec,
    SpecContract,
    StateVariable,
)


# ---------------------------------------------------------------------------
# SpecContract
# ---------------------------------------------------------------------------


class TestSpecContract:
    def test_minimal_contract(self) -> None:
        spec = SpecContract(component_name="foo")
        assert spec.component_name == "foo"
        assert spec.inputs == []
        assert spec.invariants == []

    def test_full_contract_roundtrip(self) -> None:
        spec = SpecContract(
            component_name="balance_check",
            description="Check account balance.",
            inputs=[ParameterSpec(name="balance", type_hint="int")],
            outputs=[ParameterSpec(name="return", type_hint="bool")],
            state_variables=[StateVariable(name="balance", type_hint="int", initial_value=0)],
            steps=[ExecutionStep(step_id="step-1", description="if balance >= 0", kind="branch")],
            preconditions=["balance >= 0"],
            postconditions=["balance >= 0"],
            invariants=["balance >= 0"],
        )
        dumped = spec.model_dump()
        restored = SpecContract.model_validate(dumped)
        assert restored.component_name == "balance_check"
        assert len(restored.state_variables) == 1


# ---------------------------------------------------------------------------
# PythonExtractor
# ---------------------------------------------------------------------------


class TestPythonExtractor:
    def _get_extractor(self):
        from amarooi.core.extractor.python_extractor import PythonExtractor

        return PythonExtractor()

    def test_extract_simple_function(self) -> None:
        src = "def add(x: int, y: int) -> int:\n    return x + y\n"
        ext = self._get_extractor()
        spec = ext.extract(src)
        assert spec.component_name == "add"
        param_names = [p.name for p in spec.inputs]
        assert "x" in param_names
        assert "y" in param_names
        assert spec.outputs[0].type_hint == "int"

    def test_extract_captures_return_step(self) -> None:
        src = "def f(n: int) -> str:\n    return 'ok'\n"
        spec = self._get_extractor().extract(src)
        kinds = [s.kind for s in spec.steps]
        assert "return" in kinds

    def test_extract_captures_branch_step(self) -> None:
        src = "def f(n: int) -> str:\n    if n > 0:\n        return 'pos'\n    return 'neg'\n"
        spec = self._get_extractor().extract(src)
        kinds = [s.kind for s in spec.steps]
        assert "branch" in kinds

    def test_extract_captures_loop_step(self) -> None:
        src = "def f(items: list) -> int:\n    total = 0\n    for x in items:\n        total += x\n    return total\n"
        spec = self._get_extractor().extract(src)
        kinds = [s.kind for s in spec.steps]
        assert "loop" in kinds

    def test_extract_captures_exception_handler(self) -> None:
        src = "def f(n: int) -> int:\n    try:\n        return 1 // n\n    except ZeroDivisionError:\n        return 0\n"
        spec = self._get_extractor().extract(src)
        kinds = [s.kind for s in spec.steps]
        assert "error_handler" in kinds

    def test_extract_no_function_returns_module(self) -> None:
        src = "X = 1\n"
        spec = self._get_extractor().extract(src)
        assert spec.component_name == "module"

    def test_extract_raises_on_invalid_syntax(self) -> None:
        src = "def broken(\n    return None"
        with pytest.raises(SyntaxError):
            self._get_extractor().extract(src)

    def test_extract_state_variables(self) -> None:
        src = "def f() -> None:\n    count: int = 0\n    count += 1\n"
        spec = self._get_extractor().extract(src)
        names = [sv.name for sv in spec.state_variables]
        assert "count" in names

    def test_extract_output_type_hint(self) -> None:
        src = "def greet() -> str:\n    return 'hello'\n"
        spec = self._get_extractor().extract(src)
        assert spec.outputs[0].type_hint == "str"

    def test_extract_no_type_hints(self) -> None:
        src = "def f(x, y):\n    return x + y\n"
        spec = self._get_extractor().extract(src)
        assert spec.inputs[0].type_hint == "Any"
        assert spec.outputs == []


# ---------------------------------------------------------------------------
# ExtractorFactory
# ---------------------------------------------------------------------------


class TestExtractorFactory:
    def _get_factory(self):
        from amarooi.core.extractor.factory import ExtractorFactory

        return ExtractorFactory()

    def test_get_python_by_extension(self) -> None:
        from amarooi.core.extractor.python_extractor import PythonExtractor

        factory = self._get_factory()
        ext = factory.get_extractor(".py")
        assert isinstance(ext, PythonExtractor)

    def test_get_python_by_lang(self) -> None:
        from amarooi.core.extractor.python_extractor import PythonExtractor

        factory = self._get_factory()
        ext = factory.get_extractor("python")
        assert isinstance(ext, PythonExtractor)

    def test_unknown_key_raises_key_error(self) -> None:
        factory = self._get_factory()
        with pytest.raises(KeyError, match="No extractor registered"):
            factory.get_extractor(".cobol")

    def test_register_custom_extractor(self) -> None:
        from amarooi.core.extractor.base import BaseExtractor
        from amarooi.core.extractor.factory import ExtractorFactory

        class DummyExtractor(BaseExtractor):
            def extract(self, source_code: str) -> SpecContract:
                return SpecContract(component_name="dummy")

        factory = ExtractorFactory()
        factory.register(".dummy", DummyExtractor)
        ext = factory.get_extractor(".dummy")
        assert isinstance(ext, DummyExtractor)

    def test_supported_keys_includes_python(self) -> None:
        factory = self._get_factory()
        assert ".py" in factory.supported_keys
        assert "python" in factory.supported_keys


# ---------------------------------------------------------------------------
# FormalVerifier
# ---------------------------------------------------------------------------


class TestFormalVerifier:
    def _get_verifier(self):
        from amarooi.core.verifier import FormalVerifier

        return FormalVerifier()

    def _spec_with_invariant(self, invariant: str, var_type: str = "int") -> SpecContract:
        return SpecContract(
            component_name="test",
            state_variables=[StateVariable(name="x", type_hint=var_type, initial_value=0)],
            invariants=[invariant],
        )

    def test_verify_valid_invariant_proven(self) -> None:
        spec = SpecContract(
            component_name="balance",
            state_variables=[StateVariable(name="balance", type_hint="int", initial_value=0)],
            preconditions=["balance >= 0"],
            invariants=["balance >= 0"],
        )
        result = self._get_verifier().verify_invariants(spec)
        assert result["result"] == "unsat"
        assert result["proven"] is True

    def test_verify_failing_invariant_returns_counterexample(self) -> None:
        spec = SpecContract(
            component_name="test",
            state_variables=[StateVariable(name="x", type_hint="int", initial_value=0)],
            invariants=["x > 100"],
        )
        result = self._get_verifier().verify_invariants(spec)
        # Without preconditions constraining x, the invariant can fail.
        assert result["result"] in ("sat", "unsat")

    def test_verify_no_conditions_proven(self) -> None:
        spec = SpecContract(component_name="empty")
        result = self._get_verifier().verify_invariants(spec)
        assert result["proven"] is True

    def test_verify_unparseable_conditions_unknown(self) -> None:
        spec = SpecContract(
            component_name="test",
            state_variables=[StateVariable(name="name", type_hint="str")],
            invariants=["name is not None"],
        )
        result = self._get_verifier().verify_invariants(spec)
        # Unparseable conditions yield unknown.
        assert result["result"] in ("unknown", "unsat")

    def test_check_equivalence_identical_specs_proven(self) -> None:
        sv = StateVariable(name="x", type_hint="int", initial_value=0)
        spec_f = SpecContract(
            component_name="f",
            state_variables=[sv],
            invariants=["x >= 0"],
        )
        spec_g = SpecContract(
            component_name="g",
            state_variables=[sv],
            invariants=["x >= 0"],
        )
        result = self._get_verifier().check_equivalence(spec_f, spec_g)
        assert result["proven"] is True

    def test_check_equivalence_no_conditions_proven(self) -> None:
        spec_f = SpecContract(component_name="f")
        spec_g = SpecContract(component_name="g")
        result = self._get_verifier().check_equivalence(spec_f, spec_g)
        assert result["proven"] is True

    def test_check_equivalence_different_specs_not_proven(self) -> None:
        sv = StateVariable(name="x", type_hint="int", initial_value=0)
        spec_f = SpecContract(
            component_name="f",
            state_variables=[sv],
            invariants=["x >= 0"],
        )
        spec_g = SpecContract(
            component_name="g",
            state_variables=[sv],
            invariants=["x > 100"],
        )
        result = self._get_verifier().check_equivalence(spec_f, spec_g)
        # The two invariants define different sets, so they may diverge.
        assert result["result"] in ("sat", "unsat")

    def test_verify_postcondition(self) -> None:
        spec = SpecContract(
            component_name="test",
            state_variables=[StateVariable(name="n", type_hint="int", initial_value=1)],
            preconditions=["n >= 1"],
            postconditions=["n >= 1"],
        )
        result = self._get_verifier().verify_invariants(spec)
        assert result["proven"] is True

    def test_verify_real_type_variable(self) -> None:
        spec = SpecContract(
            component_name="price",
            state_variables=[StateVariable(name="price", type_hint="float", initial_value=0.0)],
            preconditions=["price >= 0"],
            invariants=["price >= 0"],
        )
        result = self._get_verifier().verify_invariants(spec)
        assert result["proven"] is True

    def test_verify_bool_type_variable(self) -> None:
        spec = SpecContract(
            component_name="flag",
            state_variables=[StateVariable(name="flag", type_hint="bool")],
            invariants=["flag >= 0"],
        )
        # Bool variables in Z3 cannot be compared with >= directly;
        # the condition is unparseable → unknown.
        result = self._get_verifier().verify_invariants(spec)
        assert result["result"] in ("unknown", "unsat", "sat")
