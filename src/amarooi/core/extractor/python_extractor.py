"""Python AST-based logic extractor.

Walks the Python Abstract Syntax Tree of the supplied source code and
decompiles its structure into an :class:`~amarooi.core.spec.SpecContract`.
"""

from __future__ import annotations

import ast
from typing import Any

from amarooi.core.extractor.base import BaseExtractor
from amarooi.core.spec import (
    ExecutionStep,
    ParameterSpec,
    SpecContract,
    StateVariable,
)


def _annotation_to_str(annotation: ast.expr | None) -> str:
    """Convert an AST annotation node to a string.

    Args:
        annotation: AST expression node representing a type annotation.

    Returns:
        String representation of the annotation, or ``"Any"`` if *None*.
    """
    if annotation is None:
        return "Any"
    return ast.unparse(annotation)


def _const_to_value(node: ast.expr | None) -> Any:
    """Safely evaluate a constant AST node to a Python value.

    Args:
        node: AST expression node.

    Returns:
        The Python value if the node is a constant, otherwise ``None``.
    """
    if isinstance(node, ast.Constant):
        return node.value
    return None


class PythonExtractor(BaseExtractor):
    """Extracts a :class:`SpecContract` from Python source code.

    Uses Python's built-in :mod:`ast` module to walk the syntax tree and
    extract function signatures, type hints, mutable variable assignments,
    conditional branches, exception handlers, and loop boundaries.
    """

    def extract(self, source_code: str) -> SpecContract:
        """Parse *source_code* and return a :class:`SpecContract`.

        Args:
            source_code: Python source code string.

        Returns:
            A populated :class:`SpecContract` instance.

        Raises:
            SyntaxError: If *source_code* is not valid Python.
        """
        tree = ast.parse(source_code)

        # Extract top-level module docstring as description.
        module_doc = ast.get_docstring(tree) or ""

        # Find the first top-level function definition to use as the component.
        func_node: ast.FunctionDef | ast.AsyncFunctionDef | None = None
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                func_node = node
                break

        if func_node is None:
            # No function found – build a minimal contract.
            return SpecContract(
                component_name="module",
                description=module_doc,
            )

        component_name = func_node.name
        func_doc = ast.get_docstring(func_node) or module_doc

        # ── Inputs ─────────────────────────────────────────────────────
        inputs: list[ParameterSpec] = []
        args = func_node.args
        annotations_map: dict[str, ast.expr | None] = {
            arg.arg: arg.annotation for arg in args.args + args.posonlyargs + args.kwonlyargs
        }
        if args.vararg:
            annotations_map[args.vararg.arg] = args.vararg.annotation
        if args.kwarg:
            annotations_map[args.kwarg.arg] = args.kwarg.annotation

        for arg_name, ann in annotations_map.items():
            if arg_name == "self":
                continue
            inputs.append(
                ParameterSpec(name=arg_name, type_hint=_annotation_to_str(ann))
            )

        # ── Output ─────────────────────────────────────────────────────
        outputs: list[ParameterSpec] = []
        if func_node.returns is not None:
            outputs.append(
                ParameterSpec(
                    name="return",
                    type_hint=_annotation_to_str(func_node.returns),
                )
            )

        # ── State variables (mutable assignments) ──────────────────────
        state_variables: list[StateVariable] = []
        seen_vars: set[str] = set()
        for node in ast.walk(func_node):
            if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                var_name = node.target.id
                if var_name not in seen_vars:
                    seen_vars.add(var_name)
                    state_variables.append(
                        StateVariable(
                            name=var_name,
                            type_hint=_annotation_to_str(node.annotation),
                            initial_value=_const_to_value(node.value),
                        )
                    )
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id not in seen_vars:
                        seen_vars.add(target.id)
                        state_variables.append(
                            StateVariable(name=target.id, initial_value=_const_to_value(node.value))
                        )

        # ── Execution steps ────────────────────────────────────────────
        steps: list[ExecutionStep] = []
        step_counter = 0

        for node in ast.walk(func_node):
            if isinstance(node, ast.Return):
                step_counter += 1
                steps.append(
                    ExecutionStep(
                        step_id=f"step-{step_counter}",
                        description=f"return {ast.unparse(node.value) if node.value else 'None'}",
                        kind="return",
                    )
                )
            elif isinstance(node, ast.If):
                step_counter += 1
                steps.append(
                    ExecutionStep(
                        step_id=f"step-{step_counter}",
                        description=f"branch: if {ast.unparse(node.test)}",
                        kind="branch",
                    )
                )
            elif isinstance(node, (ast.For, ast.While)):
                step_counter += 1
                test_str = ast.unparse(node.test) if isinstance(node, ast.While) else ast.unparse(node.iter)
                steps.append(
                    ExecutionStep(
                        step_id=f"step-{step_counter}",
                        description=f"loop: {test_str}",
                        kind="loop",
                    )
                )
            elif isinstance(node, ast.ExceptHandler):
                step_counter += 1
                exc_type = ast.unparse(node.type) if node.type else "Exception"
                steps.append(
                    ExecutionStep(
                        step_id=f"step-{step_counter}",
                        description=f"except {exc_type}",
                        kind="error_handler",
                    )
                )

        # ── Conditions / invariants from decorators & docstring ────────
        preconditions: list[str] = []
        postconditions: list[str] = []
        invariants: list[str] = []

        for decorator in func_node.decorator_list:
            dec_str = ast.unparse(decorator)
            if "pre" in dec_str.lower():
                preconditions.append(dec_str)
            elif "post" in dec_str.lower():
                postconditions.append(dec_str)
            elif "invariant" in dec_str.lower():
                invariants.append(dec_str)

        return SpecContract(
            component_name=component_name,
            description=func_doc,
            inputs=inputs,
            outputs=outputs,
            state_variables=state_variables,
            steps=steps,
            preconditions=preconditions,
            postconditions=postconditions,
            invariants=invariants,
        )
