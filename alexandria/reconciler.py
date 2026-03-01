"""
Alexandria — Fork Reconciler

Analyzes two divergent ledger branches and attempts resolution.

Per SPEC §7: forks are preserved, not collapsed. The reconciler
produces a candidate merge; the operator must apply it as an Event.

With no policy: reports conflicts, proposes merge only if conflict-free.
With policy:    attempts to resolve each conflict deterministically.
Policy chain:   tries policies in order, falls back gracefully.

Usage:

    report = kernel_a.reconcile(kernel_b)
    if report.successful:
        merge_event = Event(report.merged, domain="reconciler")
        kernel_a.apply(merge_event)
    else:
        print(report.failure_reason)
        print(report.conflicts)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from alexandria.exceptions import InvariantViolation, SolverContradiction, ConflictUnresolvable

if TYPE_CHECKING:
    from alexandria.kernel import Event
    from alexandria.solver import ConstraintSolver
    from alexandria.invariants import Invariant
    from alexandria.policies import ConflictPolicy


@dataclass
class ReconciliationReport:
    """Full reconciliation report — what happened and why."""
    branch_a_exclusive: List[str]       # keys only in A
    branch_b_exclusive: List[str]       # keys only in B
    conflicts: Dict[str, Dict]          # key → {value_a, value_b, resolved, policy}
    compatible: Dict[str, Any]          # keys with equal values in both
    merged: Optional[Dict[str, Any]]    # final merged state (None if failed)
    solver_inferred: Dict[str, Any]     # values solver added to merge
    successful: bool
    failure_reason: Optional[str]
    policy_applied: str


class ForkReconciler:
    """
    Analyzes divergent state branches and attempts policy-driven resolution.
    """

    def __init__(
        self,
        solver: Optional["ConstraintSolver"] = None,
        policy: Optional["ConflictPolicy"] = None,
    ):
        self.solver = solver
        self.policy = policy

    def analyze(
        self,
        state_a: Dict,
        state_b: Dict,
        invariants: Optional[List["Invariant"]] = None,
        context_a: Optional[Dict] = None,
        context_b: Optional[Dict] = None,
    ) -> ReconciliationReport:
        from alexandria.policies import ConflictPolicy

        keys_a, keys_b = set(state_a), set(state_b)
        shared = keys_a & keys_b
        raw_conflicts = {
            k: (state_a[k], state_b[k])
            for k in shared if state_a[k] != state_b[k]
        }
        compatible = {k: state_a[k] for k in shared if state_a[k] == state_b[k]}

        merged = dict(compatible)
        merged.update({k: v for k, v in state_a.items() if k not in state_b})
        merged.update({k: v for k, v in state_b.items() if k not in state_a})

        conflict_details: Dict[str, Dict] = {}
        failure_reason = None
        successful = True
        policy_applied = "none"

        for key, (val_a, val_b) in raw_conflicts.items():
            conflict_details[key] = {
                "value_a": val_a, "value_b": val_b,
                "resolved": None, "policy": None,
            }

            if self.policy:
                ctx = {**(context_a or {}), **(context_b or {})}
                ctx["domain_a"] = (context_a or {}).get("domain")
                ctx["domain_b"] = (context_b or {}).get("domain")
                ctx["ts_a"] = (context_a or {}).get("ts", 0)
                ctx["ts_b"] = (context_b or {}).get("ts", 0)

                try:
                    resolved = self.policy.resolve(key, val_a, val_b, ctx)
                    if resolved is ConflictPolicy.UNRESOLVED:
                        successful = False
                        failure_reason = (
                            f"Policy '{self.policy.describe()}' "
                            f"could not resolve '{key}'"
                        )
                        break
                    merged[key] = resolved
                    conflict_details[key]["resolved"] = resolved
                    conflict_details[key]["policy"] = self.policy.describe()
                    policy_applied = self.policy.describe()
                except ConflictUnresolvable as e:
                    successful = False
                    failure_reason = str(e)
                    break
            else:
                successful = False
                failure_reason = (
                    f"Conflict on '{key}': {val_a!r} vs {val_b!r} — no policy"
                )
                break

        solver_inferred: Dict[str, Any] = {}
        if successful and self.solver:
            try:
                result = self.solver.solve(merged)
                solver_inferred = result.inferred
                merged.update(solver_inferred)
                if result.contradictions:
                    successful = False
                    failure_reason = (
                        "Solver contradiction after merge: "
                        + "; ".join(result.contradictions)
                    )
            except SolverContradiction as e:
                successful = False
                failure_reason = str(e)

        if successful and invariants:
            from alexandria.kernel import Event
            dummy = Event({}, domain="reconciler", source="reconciler")
            for inv in invariants:
                try:
                    inv.check(merged, dummy)
                except InvariantViolation as e:
                    successful = False
                    failure_reason = f"Invariant violation in merge: {e}"
                    break

        return ReconciliationReport(
            branch_a_exclusive=list(keys_a - keys_b),
            branch_b_exclusive=list(keys_b - keys_a),
            conflicts=conflict_details,
            compatible=compatible,
            merged=merged if successful else None,
            solver_inferred=solver_inferred,
            successful=successful,
            failure_reason=failure_reason,
            policy_applied=policy_applied,
        )
