"""Pydantic schemas for the visual logic planner manifest format."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ManifestMeta(BaseModel):
    """Metadata that identifies a generated logic manifest.

    Attributes:
        project_name: Human-readable project name.
        version: Manifest schema or document version.
        generated_at: Timestamp recorded when the manifest was created.
        engine_version: Version of the generator that produced the manifest.
    """

    project_name: str
    version: str
    generated_at: str
    engine_version: str


class DomainContext(BaseModel):
    """Problem-domain details that guide transpilation.

    Attributes:
        problem_statement: Natural-language description of the logic problem.
        target_language: Desired transpilation target language.
        runtime_constraints: Runtime constraints that must be respected.
    """

    problem_statement: str
    target_language: str = "python"
    runtime_constraints: list[str] = Field(default_factory=list)


class StateVariable(BaseModel):
    """A single state variable tracked by the planner.

    Attributes:
        name: Variable identifier.
        type: Data type for the variable.
        description: Human-readable meaning of the variable.
        allowed_values: Optional explicit set of accepted values.
    """

    name: str
    type: str
    description: str
    allowed_values: list[str] | None = None


class StateMatrix(BaseModel):
    """Collection of state variables and invariants for the planner.

    Attributes:
        variables: Variables used to describe planner state.
        invariants: Logical rules that must always hold true.
    """

    variables: list[StateVariable]
    invariants: list[str] = Field(default_factory=list)


class LogicGate(BaseModel):
    """A branching rule within the planner graph.

    Attributes:
        gate_id: Unique identifier for the gate.
        condition: Expression or statement evaluated by the gate.
        on_true: Action or next node selected when the condition is true.
        on_false: Action or next node selected when the condition is false.
    """

    gate_id: str
    condition: str
    on_true: str
    on_false: str


class EdgeCase(BaseModel):
    """Fallback handling for exceptional planner scenarios.

    Attributes:
        scenario: Description of the exceptional condition.
        fallback_action: Action to execute when the scenario occurs.
    """

    scenario: str
    fallback_action: str


class LogicManifest(BaseModel):
    """Top-level manifest describing visual planner logic.

    Attributes:
        meta: Manifest metadata.
        context: Domain-level execution context.
        state_matrix: State variables and invariants.
        logic_gates: Planner logic gates.
        edge_cases: Declared fallback scenarios.
    """

    meta: ManifestMeta
    context: DomainContext
    state_matrix: StateMatrix
    logic_gates: list[LogicGate] = Field(default_factory=list)
    edge_cases: list[EdgeCase] = Field(default_factory=list)
