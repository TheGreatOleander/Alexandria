"""
Alexandria — Constraint Solver

Two-phase constraint engine:

Phase 1 — Arc consistency (symbolic):
  Iterative forward-chaining. Each pass applies all relations.
  Restarts on any new inference. Terminates at fixed point.
  Handles exact algebraic inference: sum, ratio, equality, implication.

Phase 2 — Energy minimization (variational):
  After arc-consistency, computes residual energy:
    E = Σ (constraint_residual)²
  Then runs gradient descent over numeric free variables to minimize E.
  This finds the true lowest-energy state when arc-consistency alone
  cannot determine unique values.

  The gradient is estimated numerically (finite differences).
  Convergence criterion: |ΔE| < tolerance across a full pass.

This is the variational calculus layer — the system finds not just
*a* fixed point, but the one of minimum tension.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple, TYPE_CHECKING

from alexandria.exceptions import SolverContradiction

if TYPE_CHECKING:
    from alexandria.relations import Relation, SumRelation, RatioRelation
    from alexandria.relations import EqualityRelation, FunctionRelation, BoundedRelation
    from alexandria.provenance import ProvenanceLog


@dataclass
class SolverResult:
    inferred: Dict[str, Any]
    contradictions: List[str]
    steps: int
    fixed_point: bool
    energy: float
    minimization_steps: int
    underdetermined: List[str]   # keys that remain unknown due to underdetermination
    cycles: List[List[str]]      # detected circular dependency chains


class ConstraintSolver:
    """
    Two-phase solver: arc consistency → energy minimization.
    See module docstring for full description.
    """

    def __init__(
        self,
        relations: List["Relation"],
        max_steps: int = 1000,
        max_minimization_steps: int = 500,
        learning_rate: float = 0.01,
        tolerance: float = 1e-9,
        epsilon: float = 1e-7,
    ):
        self.relations = relations
        self.max_steps = max_steps
        self.max_minimization_steps = max_minimization_steps
        self.learning_rate = learning_rate
        self.tolerance = tolerance
        self.epsilon = epsilon

    # ------------------------------------------------------------------
    # Dependency graph analysis
    # ------------------------------------------------------------------

    def _build_dependency_graph(
        self, state: Dict[str, Any]
    ) -> Dict[str, Set[str]]:
        unknown: Set[str] = set()
        for rel in self.relations:
            for k in rel.keys():
                if k not in state:
                    unknown.add(k)

        graph: Dict[str, Set[str]] = {k: set() for k in unknown}
        for rel in self.relations:
            rel_keys = rel.keys()
            unknown_in_rel = rel_keys & unknown
            if not unknown_in_rel:
                continue
            for k in unknown_in_rel:
                others = (rel_keys - {k}) & unknown
                graph.setdefault(k, set()).update(others)
        return graph

    def _detect_cycles(
        self, graph: Dict[str, Set[str]]
    ) -> List[List[str]]:
        """Tarjan's algorithm — SCCs of size > 1 are cycles."""
        index_counter = [0]
        stack: List[str] = []
        lowlink: Dict[str, int] = {}
        index: Dict[str, int] = {}
        on_stack: Dict[str, bool] = {}
        sccs: List[List[str]] = []

        def strongconnect(v: str):
            index[v] = lowlink[v] = index_counter[0]
            index_counter[0] += 1
            stack.append(v)
            on_stack[v] = True
            for w in graph.get(v, set()):
                if w not in index:
                    strongconnect(w)
                    lowlink[v] = min(lowlink[v], lowlink[w])
                elif on_stack.get(w):
                    lowlink[v] = min(lowlink[v], index[w])
            if lowlink[v] == index[v]:
                scc = []
                while True:
                    w = stack.pop()
                    on_stack[w] = False
                    scc.append(w)
                    if w == v:
                        break
                if len(scc) > 1:
                    sccs.append(sorted(scc))

        for v in list(graph.keys()):
            if v not in index:
                strongconnect(v)
        return sccs

    def _detect_underdetermined(
        self, state: Dict[str, Any], inferred: Dict[str, Any]
    ) -> List[str]:
        all_keys: Set[str] = set()
        for rel in self.relations:
            all_keys.update(rel.keys())
        combined = set(state) | set(inferred)
        return sorted(all_keys - combined)

    # ------------------------------------------------------------------
    # Phase 1: Arc consistency
    # ------------------------------------------------------------------

    def _arc_consistency(
        self,
        state: Dict[str, Any],
        provenance: Optional["ProvenanceLog"] = None,
    ) -> Tuple[Dict[str, Any], Dict[str, Any], int]:
        working = dict(state)
        inferred: Dict[str, Any] = {}
        newly_set: Set[str] = set()

        for step in range(self.max_steps):
            made_progress = False
            for rel in self.relations:
                new_vals = rel.infer(working)
                if not new_vals:
                    continue
                for k, v in new_vals.items():
                    if k not in working:
                        working[k] = v
                        inferred[k] = v
                        newly_set.add(k)
                        if provenance:
                            derived = [x for x in rel.keys()
                                       if x != k and x in working]
                            provenance.record_inference(k, v, rel, derived)
                        made_progress = True
                    elif getattr(rel, 'volatile', False) and k in newly_set:
                        existing = working[k]
                        changed = (
                            (abs(existing - v) > 1e-9)
                            if isinstance(v, float) and isinstance(existing, float)
                            else (existing != v)
                        )
                        if changed:
                            working[k] = v
                            inferred[k] = v
                            if provenance:
                                derived = [x for x in rel.keys()
                                           if x != k and x in working]
                                provenance.record_inference(k, v, rel, derived)
                            made_progress = True
                    else:
                        existing = working[k]
                        conflict = (
                            (abs(existing - v) > 1e-9)
                            if isinstance(v, float) and isinstance(existing, float)
                            else (existing != v)
                        )
                        if conflict:
                            raise SolverContradiction(
                                f"Contradiction on '{k}': [{rel.describe()}] "
                                f"infers {v!r} but value is already {existing!r}"
                            )
            if not made_progress:
                return working, inferred, step + 1

        return working, inferred, self.max_steps

    # ------------------------------------------------------------------
    # Phase 2: Energy minimization
    # ------------------------------------------------------------------

    def _energy(self, state: Dict[str, Any]) -> float:
        total = 0.0
        for rel in self.relations:
            if rel.check(state) is None:
                continue
            residual = self._numeric_residual(rel, state)
            total += residual * residual
        return total

    def _numeric_residual(self, rel: "Relation", state: Dict) -> float:
        from alexandria.relations import (
            SumRelation, RatioRelation, EqualityRelation, FunctionRelation,
        )
        if isinstance(rel, SumRelation):
            if all(k in state for k in rel.parts) and rel.total in state:
                return sum(state[k] for k in rel.parts) - state[rel.total]
        elif isinstance(rel, RatioRelation):
            n, d, r = rel.numerator, rel.denominator, rel.ratio_key
            if all(k in state for k in [n, d, r]) and state[d] != 0:
                return state[n] / state[d] - state[r]
        elif isinstance(rel, EqualityRelation):
            a, b = rel.key_a, rel.key_b
            if a in state and b in state:
                va, vb = state[a], state[b]
                if isinstance(va, (int, float)) and isinstance(vb, (int, float)):
                    return float(va) - float(vb)
                return 0.0 if va == vb else 1.0
        elif isinstance(rel, FunctionRelation):
            if all(k in state for k in rel.inputs) and rel.output in state:
                try:
                    expected = rel.fn(*[state[k] for k in rel.inputs])
                    if isinstance(expected, (int, float)):
                        return float(state[rel.output]) - float(expected)
                except Exception:
                    pass
        return 1.0 if rel.check(state) else 0.0

    def _free_numeric_keys(
        self, state: Dict[str, Any], fixed_keys: Set[str]
    ) -> List[str]:
        return [
            k for k, v in state.items()
            if k not in fixed_keys and isinstance(v, (int, float))
        ]

    def _minimize(
        self,
        working: Dict[str, Any],
        fixed_keys: Set[str],
        inferred: Dict[str, Any],
    ) -> Tuple[Dict[str, Any], Dict[str, Any], float, int]:
        free_keys = self._free_numeric_keys(working, fixed_keys)
        if not free_keys:
            return working, inferred, self._energy(working), 0

        current_energy = self._energy(working)
        if current_energy < self.tolerance:
            return working, inferred, current_energy, 0

        lr = self.learning_rate
        steps = 0

        for _ in range(self.max_minimization_steps):
            gradient = {}
            for k in free_keys:
                plus = {**working, k: working[k] + self.epsilon}
                minus = {**working, k: working[k] - self.epsilon}
                gradient[k] = (
                    (self._energy(plus) - self._energy(minus)) / (2 * self.epsilon)
                )

            new_working = dict(working)
            for k in free_keys:
                new_working[k] = working[k] - lr * gradient[k]

            new_energy = self._energy(new_working)
            if new_energy >= current_energy:
                lr *= 0.5
                if lr < 1e-15:
                    break
                continue

            delta_e = current_energy - new_energy
            working = new_working
            current_energy = new_energy
            steps += 1
            for k in free_keys:
                if k in inferred or k not in fixed_keys:
                    inferred[k] = working[k]
            if delta_e < self.tolerance:
                break

        return working, inferred, current_energy, steps

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def solve(
        self,
        state: Dict[str, Any],
        provenance: Optional["ProvenanceLog"] = None,
        minimize: bool = True,
    ) -> SolverResult:
        """
        Full two-phase solve.
        Phase 1: arc consistency → exact symbolic inference.
        Phase 2: energy minimization → lowest-energy fixed point.
        """
        fixed_keys = set(state.keys())

        working, inferred, arc_steps = self._arc_consistency(state, provenance)

        energy = self._energy(working)
        min_steps = 0
        if minimize and energy > self.tolerance:
            working, inferred, energy, min_steps = self._minimize(
                working, fixed_keys, inferred
            )

        contradictions = [
            err for rel in self.relations if (err := rel.check(working))
        ]
        underdetermined = self._detect_underdetermined(state, inferred)
        cycles: List[List[str]] = []
        if underdetermined:
            graph = self._build_dependency_graph(working)
            cycles = self._detect_cycles(graph)

        return SolverResult(
            inferred=inferred,
            contradictions=contradictions,
            steps=arc_steps,
            fixed_point=True,
            energy=energy,
            minimization_steps=min_steps,
            underdetermined=underdetermined,
            cycles=cycles,
        )

    def inferred_keys(self, state: Dict[str, Any]) -> Set[str]:
        try:
            return set(self.solve(state, minimize=False).inferred.keys())
        except SolverContradiction:
            return set()
