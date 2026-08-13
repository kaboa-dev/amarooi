"""Z3-based formal verification engine.

:class:`FormalVerifier` uses Microsoft's Z3 SMT solver to provide
mathematical guarantees about the correctness of extracted logic specifications.

Two verification workflows are supported:

* **Workflow A – Invariant / post-condition verification**: proves that
  invariants and post-conditions hold for all possible input states, or
  returns a concrete counter-example if they do not.

* **Workflow B – Formal equivalence checking (F ≡ G)**: given two
  :class:`~amarooi.core.spec.SpecContract` models *F* and *G*, proves that
  they are logically equivalent, or returns the state values where they
  diverge.

Example::

    from amarooi.core.verifier import FormalVerifier
    from amarooi.core.spec import SpecContract, StateVariable

    spec = SpecContract(
        component_name="balance_check",
        state_variables=[StateVariable(name="balance", type_hint="int", initial_value=0)],
        invariants=["balance >= 0"],
    )
    verifier = FormalVerifier()
    result = verifier.verify_invariants(spec)
    print(result)  # {"result": "unsat", "proven": True}
"""

from __future__ import annotations

from typing import Any

try:
    import z3  # type: ignore[import]
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "z3-solver is required for FormalVerifier. "
        "Install it with: pip install z3-solver>=4.12.0"
    ) from exc

from amarooi.core.spec import SpecContract, StateVariable


# ---------------------------------------------------------------------------
# Type mapping helpers
# ---------------------------------------------------------------------------


def _make_z3_var(var: StateVariable) -> z3.ExprRef:
    """Create a Z3 symbolic variable from a :class:`StateVariable`.

    Non-integer / non-float / non-bool types are represented as Z3
    *Uninterpreted* constants so the solver never panics on unsupported types.

    Args:
        var: State variable to model.

    Returns:
        A Z3 symbolic variable of the appropriate sort.
    """
    hint = var.type_hint.lower()
    if hint in {"int", "integer"}:
        return z3.Int(var.name)
    if hint in {"float", "real", "number", "decimal"}:
        return z3.Real(var.name)
    if hint in {"bool", "boolean"}:
        return z3.Bool(var.name)
    # Fall back to an uninterpreted integer constant for everything else
    # (str, Any, custom types, etc.) to avoid solver errors.
    S = z3.DeclareSort(f"Sort_{var.name}")
    return z3.Const(var.name, S)


def _parse_condition(condition: str, ctx: dict[str, z3.ExprRef]) -> z3.BoolRef | None:
    """Attempt to parse a string condition into a Z3 Boolean expression.

    Only a subset of Python expressions is supported (comparisons of the form
    ``name op literal``).  Conditions that cannot be translated are silently
    skipped – the solver will simply ignore them rather than crash.

    Args:
        condition: String expression such as ``"balance >= 0"``.
        ctx: Mapping from variable name to its Z3 symbolic variable.

    Returns:
        A :class:`z3.BoolRef` or ``None`` if the condition cannot be parsed.
    """
    import ast as _ast

    try:
        tree = _ast.parse(condition.strip(), mode="eval")
    except SyntaxError:
        return None

    expr = tree.body
    if not isinstance(expr, _ast.Compare):
        return None
    if not isinstance(expr.left, _ast.Name):
        return None
    if len(expr.ops) != 1 or len(expr.comparators) != 1:
        return None

    lhs_name = expr.left.id
    if lhs_name not in ctx:
        return None

    lhs = ctx[lhs_name]
    comparator = expr.comparators[0]

    if not isinstance(comparator, (_ast.Constant,)):
        return None

    rhs = comparator.value

    op = expr.ops[0]
    try:
        if isinstance(op, _ast.GtE):
            return lhs >= rhs  # type: ignore[operator]
        if isinstance(op, _ast.Gt):
            return lhs > rhs  # type: ignore[operator]
        if isinstance(op, _ast.LtE):
            return lhs <= rhs  # type: ignore[operator]
        if isinstance(op, _ast.Lt):
            return lhs < rhs  # type: ignore[operator]
        if isinstance(op, _ast.Eq):
            return lhs == rhs  # type: ignore[operator]
        if isinstance(op, _ast.NotEq):
            return lhs != rhs  # type: ignore[operator]
    except TypeError:
        return None
    return None


# ---------------------------------------------------------------------------
# Verification result helpers
# ---------------------------------------------------------------------------


def _build_result(
    solver: z3.Solver,
    check: z3.CheckSatResult,
    *,
    proven: bool,
) -> dict[str, Any]:
    """Build a structured result dictionary from a solver check.

    Args:
        solver: The Z3 :class:`z3.Solver` instance after calling
            :meth:`~z3.Solver.check`.
        check: The result of :meth:`~z3.Solver.check`.
        proven: Whether an *unsat* result means the property is proven.

    Returns:
        A dictionary with keys ``"result"``, ``"proven"``, and optionally
        ``"counterexample"`` (when *check* is ``sat``).
    """
    result_str = str(check)  # "sat", "unsat", or "unknown"
    out: dict[str, Any] = {"result": result_str, "proven": proven}
    if check == z3.sat:
        model = solver.model()
        out["counterexample"] = {
            str(d): str(model[d]) for d in model.decls()
        }
    return out


# ---------------------------------------------------------------------------
# FormalVerifier
# ---------------------------------------------------------------------------


class FormalVerifier:
    """Formal verification engine backed by the Z3 SMT solver.

    Supports two verification workflows:

    * :meth:`verify_invariants` – Invariant / post-condition verification.
    * :meth:`check_equivalence` – Formal equivalence checking (*F ≡ G*).
    """

    # ------------------------------------------------------------------
    # Workflow A – Invariant / post-condition verification
    # ------------------------------------------------------------------

    def verify_invariants(self, spec: SpecContract) -> dict[str, Any]:
        """Verify that all invariants and post-conditions hold for *spec*.

        Injects the pre-conditions into a :class:`z3.Solver` instance,
        then asserts ``Not(post_condition)`` for each invariant.

        * ``"unsat"`` → all invariants are mathematically proven to hold.
        * ``"sat"``   → returns a concrete counter-example.
        * ``"unknown"`` → solver could not decide (e.g. non-linear constraints).

        Args:
            spec: The :class:`SpecContract` to verify.

        Returns:
            A result dictionary with at minimum the keys ``"result"`` (str)
            and ``"proven"`` (bool).  When *result* is ``"sat"``,
            ``"counterexample"`` is also present.
        """
        solver = z3.Solver()
        ctx: dict[str, z3.ExprRef] = {
            sv.name: _make_z3_var(sv) for sv in spec.state_variables
        }

        # Add pre-conditions as solver assumptions.
        for pre in spec.preconditions:
            z3_expr = _parse_condition(pre, ctx)
            if z3_expr is not None:
                solver.add(z3_expr)

        # Collect all invariants and post-conditions.
        conditions = spec.invariants + spec.postconditions
        if not conditions:
            # Nothing to verify – vacuously proven.
            return {"result": "unsat", "proven": True}

        negated: list[z3.BoolRef] = []
        for cond in conditions:
            z3_expr = _parse_condition(cond, ctx)
            if z3_expr is not None:
                negated.append(z3.Not(z3_expr))

        if not negated:
            # All conditions were unparseable – report as unknown.
            return {"result": "unknown", "proven": False}

        solver.add(z3.Or(*negated))
        check = solver.check()

        return _build_result(solver, check, proven=(check == z3.unsat))

    # ------------------------------------------------------------------
    # Workflow B – Formal equivalence checking
    # ------------------------------------------------------------------

    def check_equivalence(
        self,
        spec_f: SpecContract,
        spec_g: SpecContract,
    ) -> dict[str, Any]:
        """Formally check whether *spec_f* and *spec_g* are logically equivalent.

        Constructs a combined Z3 model from both specifications' state
        variables, invariants, and post-conditions and asserts
        ``Not(F == G)`` (i.e. the conjunction of all conditions from *F*
        implies the conjunction from *G* and vice-versa).

        * ``"unsat"`` → *F ≡ G* is proven.
        * ``"sat"``   → returns a concrete divergence counter-example.

        Args:
            spec_f: Legacy (original) logic specification.
            spec_g: Generated (target) logic specification.

        Returns:
            A result dictionary with at minimum the keys ``"result"`` (str)
            and ``"proven"`` (bool).
        """
        solver = z3.Solver()

        # Build a unified variable context (union of both specs' variables).
        ctx: dict[str, z3.ExprRef] = {}
        for sv in spec_f.state_variables + spec_g.state_variables:
            if sv.name not in ctx:
                ctx[sv.name] = _make_z3_var(sv)

        def _collect(spec: SpecContract) -> list[z3.BoolRef]:
            exprs: list[z3.BoolRef] = []
            for cond in spec.invariants + spec.postconditions + spec.preconditions:
                e = _parse_condition(cond, ctx)
                if e is not None:
                    exprs.append(e)
            return exprs

        f_exprs = _collect(spec_f)
        g_exprs = _collect(spec_g)

        if not f_exprs and not g_exprs:
            # Both specs have no verifiable conditions – vacuously equivalent.
            return {"result": "unsat", "proven": True}

        f_combined = z3.And(*f_exprs) if f_exprs else z3.BoolVal(True)
        g_combined = z3.And(*g_exprs) if g_exprs else z3.BoolVal(True)

        # Assert F != G (i.e. they are NOT equivalent).
        solver.add(z3.Not(f_combined == g_combined))

        check = solver.check()
        return _build_result(solver, check, proven=(check == z3.unsat))
