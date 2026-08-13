"""Structured .amarooi logic specification contract.

:class:`SpecContract` is the canonical Pydantic model that represents a
fully-parsed ``.amarooi`` logic specification.  It is the exchange format
between the extractor framework and the formal verification engine.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ParameterSpec(BaseModel):
    """Describes a single input or output parameter."""

    name: str = Field(..., description="Parameter identifier.")
    type_hint: str = Field(default="Any", description="Python type annotation string.")
    description: str = Field(default="", description="Human-readable description.")


class StateVariable(BaseModel):
    """Mutable state register extracted from source code."""

    name: str = Field(..., description="Variable identifier.")
    type_hint: str = Field(default="Any", description="Python type annotation string.")
    initial_value: Any = Field(default=None, description="Default or initial value.")


class ExecutionStep(BaseModel):
    """A single step in the extracted execution flow."""

    step_id: str = Field(..., description="Unique step identifier (e.g. 'step-1').")
    description: str = Field(..., description="Human-readable description of the step.")
    kind: str = Field(
        default="statement",
        description="Step kind: 'statement', 'branch', 'loop', 'call', 'return', 'error_handler'.",
    )


class SpecContract(BaseModel):
    """Full .amarooi logic specification extracted from legacy source code.

    This model is produced by :class:`~amarooi.core.extractor.base.BaseExtractor`
    implementations and consumed by :class:`~amarooi.core.verifier.FormalVerifier`.
    """

    component_name: str = Field(..., description="Name of the extracted component.")
    description: str = Field(default="", description="High-level component description.")
    inputs: list[ParameterSpec] = Field(default_factory=list, description="Input parameters.")
    outputs: list[ParameterSpec] = Field(default_factory=list, description="Output parameters.")
    state_variables: list[StateVariable] = Field(
        default_factory=list, description="Mutable state registers."
    )
    steps: list[ExecutionStep] = Field(
        default_factory=list, description="Ordered execution flow steps."
    )
    preconditions: list[str] = Field(
        default_factory=list, description="Pre-condition expressions (string form)."
    )
    postconditions: list[str] = Field(
        default_factory=list, description="Post-condition expressions (string form)."
    )
    invariants: list[str] = Field(
        default_factory=list, description="Invariant boundary expressions (string form)."
    )
