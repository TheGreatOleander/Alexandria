"""
Alexandria Temporal Kernel — v9.0
Canonicalization Field / Self-Completing Knowledge Structure

The core engine. All other modules (relations, invariants, policies, etc.)
import from here for the types they need, and this module imports from them
for its own use.

Architecture:
  Event            — immutable record with cryptographic hash
  Lattice          — coordinate grid (shape of what could exist)
  TemporalIndex    — O(log n) state queries at any point in time
  TemporalKernel   — the canonicalization engine
"""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

VERSION = "9.0"

from alexandria.exceptions import (
    LatticeViolation, DomainViolation, InvariantViolation,
    SolverContradiction, EquilibriumUnreachable, LedgerCorruption,
)
from alexandria.relations import Relation, TemporalRelation
from alexandria.invariants import Invariant, RelationInvariant
from alexandria.domains import TrustDomain
from alexandria.solver import ConstraintSolver, SolverResult
from alexandria.provenance import ProvenanceLog
from alexandria.schema import SchemaInference, PositionProposal, RelationProposal
from alexandria.reconciler import ForkReconciler, ReconciliationReport
from alexandria.policies import ConflictPolicy


# ===========================================================================
# Occupancy
# ===========================================================================

class Occupancy(Enum):
    FILLED    = "filled"
    EMPTY     = "empty"
    REQUIRED  = "required"
    IMPLIED   = "implied"
    INFERRED  = "inferred"
    FORBIDDEN = "forbidden"


# ===========================================================================
# Event
# ===========================================================================

class Event:
    def __init__(
        self,
        payload: Dict[str, Any],
        domain: str = "default",
        source: str = "external",
    ):
        self.id = str(uuid.uuid4())
        self.ts = time.time_ns()
        self.domain = domain
        self.payload = payload
        self.source = source
        self.hash = self._compute_hash()

    def _compute_hash(self) -> str:
        raw = json.dumps(
            {
                "id": self.id, "ts": self.ts,
                "domain": self.domain, "payload": self.payload,
            },
            sort_keys=True,
        ).encode()
        return hashlib.sha256(raw).hexdigest()

    def to_dict(self) -> Dict:
        return {
            "id": self.id, "ts": self.ts, "domain": self.domain,
            "payload": self.payload, "source": self.source, "hash": self.hash,
        }

    @classmethod
    def from_dict(cls, d: Dict) -> "Event":
        e = object.__new__(cls)
        e.id, e.ts, e.domain = d["id"], d["ts"], d["domain"]
        e.payload = d["payload"]
        e.source = d.get("source", "external")
        e.hash = d["hash"]
        expected = hashlib.sha256(
            json.dumps(
                {
                    "id": e.id, "ts": e.ts,
                    "domain": e.domain, "payload": e.payload,
                },
                sort_keys=True,
            ).encode()
        ).hexdigest()
        if expected != e.hash:
            raise LedgerCorruption(
                f"Event {e.id} hash mismatch — ledger corrupted"
            )
        return e


# ===========================================================================
# Lattice
# ===========================================================================

@dataclass
class LatticePosition:
    domain: str
    key: str
    allowed_types: Optional[Set[type]] = None
    required: bool = False
    implied_by: List[Tuple[str, str]] = field(default_factory=list)
    default_factory: Optional[Callable] = None
    description: str = ""

    @property
    def coord(self) -> str:
        return f"{self.domain}:{self.key}"

    def validate_value(self, value: Any):
        if self.allowed_types and not isinstance(value, tuple(self.allowed_types)):
            raise LatticeViolation(
                f"{self.coord} expects {self.allowed_types}, "
                f"got {type(value).__name__}"
            )


class Lattice:
    def __init__(self):
        self._positions: Dict[str, LatticePosition] = {}
        self._relations: List[Relation] = []
        self._solver: Optional[ConstraintSolver] = None

    def define(
        self,
        domain: str,
        key: str,
        allowed_types: Optional[Set[type]] = None,
        required: bool = False,
        implied_by: Optional[List[Tuple[str, str]]] = None,
        default_factory: Optional[Callable] = None,
        description: str = "",
    ) -> "Lattice":
        pos = LatticePosition(
            domain=domain, key=key, allowed_types=allowed_types,
            required=required, implied_by=implied_by or [],
            default_factory=default_factory, description=description,
        )
        self._positions[pos.coord] = pos
        return self

    def relate(self, relation: Relation) -> "Lattice":
        self._relations.append(relation)
        self._solver = ConstraintSolver(self._relations)
        return self

    def validate(self, domain: str, key: str, value: Any):
        coord = f"{domain}:{key}"
        if coord not in self._positions:
            raise LatticeViolation(
                f"Position {coord} not defined in lattice."
            )
        self._positions[coord].validate_value(value)

    def position(self, domain: str, key: str) -> Optional[LatticePosition]:
        return self._positions.get(f"{domain}:{key}")

    def all_positions(self) -> List[LatticePosition]:
        return list(self._positions.values())

    def solver(self) -> Optional[ConstraintSolver]:
        return self._solver

    def occupancy_map(self, state: Dict[str, Any]) -> Dict[str, Occupancy]:
        inferable = (
            self._solver.inferred_keys(state) if self._solver else set()
        )
        result = {}
        for coord, pos in self._positions.items():
            if pos.key in state:
                result[coord] = Occupancy.FILLED
            elif pos.key in inferable:
                result[coord] = Occupancy.INFERRED
            elif pos.required:
                result[coord] = Occupancy.REQUIRED
            else:
                implied = any(k in state for _, k in pos.implied_by)
                result[coord] = Occupancy.IMPLIED if implied else Occupancy.EMPTY
        return result

    def gaps(self, state: Dict[str, Any]) -> List[LatticePosition]:
        occ = self.occupancy_map(state)
        return [
            self._positions[c] for c, s in occ.items()
            if s in (Occupancy.REQUIRED, Occupancy.IMPLIED, Occupancy.INFERRED)
        ]

    def mendeleev_predict(self, state: Dict[str, Any]) -> List[Dict]:
        occ = self.occupancy_map(state)
        solver_result = None
        if self._solver:
            try:
                solver_result = self._solver.solve(state)
            except SolverContradiction:
                pass

        predictions = []
        for coord, status in occ.items():
            if status == Occupancy.FILLED:
                continue
            pos = self._positions[coord]
            entry = {
                "coord": coord, "domain": pos.domain, "key": pos.key,
                "status": status.value,
                "reason": {
                    Occupancy.REQUIRED: "conservation_law",
                    Occupancy.IMPLIED:  "structural_implication",
                    Occupancy.INFERRED: "solver_inference",
                }.get(status, "unknown"),
                "default": None, "inferred_value": None,
            }
            if status == Occupancy.INFERRED and solver_result:
                entry["inferred_value"] = solver_result.inferred.get(pos.key)
                entry["default"] = entry["inferred_value"]
            elif pos.default_factory:
                entry["default"] = pos.default_factory()
            predictions.append(entry)
        return predictions


# ===========================================================================
# Temporal Index
# ===========================================================================

class TemporalIndex:
    """O(log n) state queries at any point in time."""

    def __init__(self):
        self._snapshots: List[Tuple[int, Dict[str, Any]]] = []

    def record(self, ts: int, state: Dict[str, Any]):
        self._snapshots.append((ts, dict(state)))

    def at(self, ts: int) -> Optional[Dict[str, Any]]:
        if not self._snapshots:
            return None
        lo, hi, result = 0, len(self._snapshots) - 1, None
        while lo <= hi:
            mid = (lo + hi) // 2
            if self._snapshots[mid][0] <= ts:
                result = self._snapshots[mid][1]
                lo = mid + 1
            else:
                hi = mid - 1
        return result

    def between(self, t_start: int, t_end: int) -> List[Tuple[int, Dict]]:
        return [
            (ts, s) for ts, s in self._snapshots
            if t_start <= ts <= t_end
        ]

    def first(self) -> Optional[Dict]:
        return self._snapshots[0][1] if self._snapshots else None

    def latest(self) -> Optional[Dict]:
        return self._snapshots[-1][1] if self._snapshots else None

    def rebuild(self, ledger: List[Event]):
        self._snapshots = []
        state: Dict = {}
        for event in sorted(ledger, key=lambda e: e.ts):
            state = {**state, **event.payload}
            self.record(event.ts, state)


# ===========================================================================
# Constraint Propagator
# ===========================================================================

@dataclass
class PropagationResult:
    tension: float
    filled: List[str]
    remaining_gaps: List[Dict]
    at_equilibrium: bool
    inferred_this_step: Dict[str, Any]
    violations: List[str]


class ConstraintPropagator:
    def __init__(self, lattice: Lattice, invariants: List[Invariant]):
        self.lattice = lattice
        self.invariants = invariants

    def analyze(
        self,
        state: Dict,
        provenance: Optional[ProvenanceLog] = None,
    ) -> PropagationResult:
        solver = self.lattice.solver()
        inferred, violations = {}, []
        if solver:
            try:
                result = solver.solve(state, provenance)
                inferred = result.inferred
                violations = result.contradictions
            except SolverContradiction as e:
                violations = [str(e)]

        extended = {**state, **inferred}
        gaps = self.lattice.mendeleev_predict(extended)
        auto_fillable = [g for g in gaps if g["default"] is not None]
        needs_external = [g for g in gaps if g["default"] is None]
        tension = sum(
            2.0 if g["reason"] == "conservation_law" else 1.0
            for g in needs_external
        )

        return PropagationResult(
            tension=tension,
            filled=[g["coord"] for g in auto_fillable],
            remaining_gaps=needs_external,
            at_equilibrium=tension == 0.0 and not auto_fillable,
            inferred_this_step=inferred,
            violations=violations,
        )

    def candidate_events(self, state: Dict) -> List[Event]:
        solver = self.lattice.solver()
        inferred = {}
        if solver:
            try:
                inferred = solver.solve(state).inferred
            except SolverContradiction:
                pass
        extended = {**state, **inferred}
        return [
            Event(
                {g["key"]: g["default"]},
                domain=g["domain"],
                source="propagator",
            )
            for g in self.lattice.mendeleev_predict(extended)
            if g["default"] is not None
        ]

    def tension_gradient(self, state: Dict) -> Dict[str, float]:
        weights = {
            Occupancy.REQUIRED: 2.0, Occupancy.IMPLIED: 1.0,
            Occupancy.INFERRED: 0.5, Occupancy.FILLED: 0.0,
            Occupancy.EMPTY: 0.0,    Occupancy.FORBIDDEN: 0.0,
        }
        return {
            c: weights.get(s, 0.0)
            for c, s in self.lattice.occupancy_map(state).items()
        }


# ===========================================================================
# Temporal Kernel
# ===========================================================================

class TemporalKernel:
    """
    The core canonicalization engine.

    apply()                — ingest event through full pipeline
    replay()               — reconstruct from first principles
    propagate()            — Floquet analysis
    drive_to_equilibrium() — auto-fill inferable/default gaps
    at(ts)                 — state at time T (temporal query)
    explain(key)           — provenance for any value
    explain_chain(key)     — full derivation chain back to events
    reconcile(other)       — fork divergence analysis
    infer_schema()         — propose lattice from observed events
    infer_relations()      — propose relations from observed data
    equilibrium_report()   — full human-legible system report
    """

    def __init__(
        self,
        lattice: Optional[Lattice] = None,
        domains: Optional[Dict[str, TrustDomain]] = None,
        invariants: Optional[List[Invariant]] = None,
        policy: Optional[ConflictPolicy] = None,
    ):
        self.lattice = lattice
        self.domains = domains or {}
        self.invariants = invariants or []
        self.policy = policy
        self.state: Dict[str, Any] = {}
        self.ledger: List[Event] = []
        self.provenance = ProvenanceLog()
        self._temporal = TemporalIndex()
        self._schema = SchemaInference()
        self._propagator = (
            ConstraintPropagator(lattice, self.invariants) if lattice else None
        )
        self._reconciler = ForkReconciler(
            solver=lattice.solver() if lattice else None,
            policy=policy,
        )
        self._temporal_watched_keys: Set[str] = self._collect_temporal_keys()

    def _collect_temporal_keys(self) -> Set[str]:
        watched: Set[str] = set()
        sources: List[Relation] = []
        if self.lattice:
            sources.extend(self.lattice._relations)
        for inv in self.invariants:
            if isinstance(inv, RelationInvariant) and isinstance(
                inv.relation, TemporalRelation
            ):
                sources.append(inv.relation)
        for rel in sources:
            if isinstance(rel, TemporalRelation):
                watched.add(rel.key)
        return watched

    def apply(self, event: Event) -> "TemporalKernel":
        # 1. Domain write authority
        if event.domain in self.domains:
            for key in event.payload:
                self.domains[event.domain].assert_write(key)

        # 2. Lattice position validation (skip internal _prev_ keys)
        if self.lattice:
            for key, value in event.payload.items():
                if not key.startswith("_prev_"):
                    self.lattice.validate(event.domain, key, value)

        # 3. Candidate state + automatic _prev_ injection
        candidate = {**self.state, **event.payload}
        for key in self._temporal_watched_keys:
            if key in event.payload and key in self.state:
                prev_key = f"_prev_{key}"
                if prev_key not in event.payload:
                    candidate[prev_key] = self.state[key]

        # 4. Constraint propagation
        if self.lattice and self.lattice.solver():
            try:
                sr = self.lattice.solver().solve(candidate, self.provenance)
                if sr.contradictions:
                    raise SolverContradiction("; ".join(sr.contradictions))
                candidate.update(sr.inferred)
            except SolverContradiction:
                raise

        # 5. Invariants
        for inv in self.invariants:
            inv.check(candidate, event)

        # 6. Commit
        self.ledger.append(event)
        self.state = candidate

        # 7. Provenance, temporal index, schema inference
        for key, value in event.payload.items():
            self.provenance.record_event(key, value, event)
        self._temporal.record(event.ts, self.state)
        self._schema.observe(event)

        return self

    def replay(self) -> "TemporalKernel":
        saved = list(self.ledger)
        self.state = {}
        self.ledger = []
        self.provenance.clear()
        self._temporal = TemporalIndex()
        self._schema = SchemaInference()
        for inv in self.invariants:
            if hasattr(inv, '_last'):
                inv._last = None
        for event in sorted(saved, key=lambda e: e.ts):
            self.apply(event)
        return self

    def propagate(self) -> PropagationResult:
        if not self._propagator:
            raise RuntimeError(
                "No lattice — propagation requires a lattice"
            )
        return self._propagator.analyze(self.state, self.provenance)

    def candidate_events(self) -> List[Event]:
        return (
            self._propagator.candidate_events(self.state)
            if self._propagator else []
        )

    def drive_to_equilibrium(self, max_steps: int = 100) -> List[Event]:
        applied = []
        for _ in range(max_steps):
            candidates = self.candidate_events()
            if not candidates:
                break
            for event in candidates:
                self.apply(event)
                applied.append(event)
            if self.propagate().at_equilibrium:
                break
        return applied

    def at(self, ts: int) -> Optional[Dict[str, Any]]:
        return self._temporal.at(ts)

    def between(self, t_start: int, t_end: int) -> List[Tuple[int, Dict]]:
        return self._temporal.between(t_start, t_end)

    def explain(self, key: str) -> str:
        return self.provenance.explain(key)

    def explain_chain(self, key: str) -> List[str]:
        return self.provenance.explain_chain(key)

    def explain_all(self) -> Dict[str, str]:
        return self.provenance.explain_all()

    def reconcile(
        self,
        other: "TemporalKernel",
        context_a: Optional[Dict] = None,
        context_b: Optional[Dict] = None,
    ) -> ReconciliationReport:
        return self._reconciler.analyze(
            self.state, other.state, self.invariants, context_a, context_b
        )

    def infer_schema(self, min_occurrence: int = 2) -> List[PositionProposal]:
        return self._schema.proposals(min_occurrence)

    def infer_relations(
        self,
        min_cooccurrence: int = 3,
        min_confidence: float = 0.8,
    ) -> List[RelationProposal]:
        return self._schema.relation_proposals(min_cooccurrence, min_confidence)

    def snapshot_hash(self) -> str:
        return hashlib.sha256(
            json.dumps(self.state, sort_keys=True).encode()
        ).hexdigest()

    def equilibrium_report(self) -> Dict:
        report: Dict[str, Any] = {
            "version": VERSION,
            "snapshot_hash": self.snapshot_hash(),
            "event_count": len(self.ledger),
            "state_keys": list(self.state.keys()),
            "state": dict(self.state),
            "provenance": self.explain_all(),
            "provenance_chains": {
                key: self.explain_chain(key)
                for key in self.state
                if not key.startswith("_prev_")
            },
        }

        if self.ledger:
            report["event_history"] = [
                {
                    "id": e.id[:8],
                    "domain": e.domain,
                    "source": e.source,
                    "keys": list(e.payload.keys()),
                }
                for e in self.ledger
            ]
            report["time_span_ns"] = self.ledger[-1].ts - self.ledger[0].ts
            report["domains_seen"] = sorted({e.domain for e in self.ledger})

        if self._propagator:
            result = self.propagate()
            report.update({
                "tension": result.tension,
                "at_equilibrium": result.at_equilibrium,
                "occupancy": {
                    k: v.value
                    for k, v in self.lattice.occupancy_map(self.state).items()
                },
                "tension_gradient": self._propagator.tension_gradient(self.state),
                "gaps": result.remaining_gaps,
                "inferred_this_step": result.inferred_this_step,
                "violations": result.violations,
            })

        if self.lattice and self.lattice.solver():
            try:
                sr = self.lattice.solver().solve(self.state, minimize=False)
                report["solver_energy"] = sr.energy
                report["solver_steps"] = sr.steps
                report["minimization_steps"] = sr.minimization_steps
                if sr.underdetermined:
                    report["underdetermined_keys"] = sr.underdetermined
                if sr.cycles:
                    report["dependency_cycles"] = sr.cycles
            except Exception:
                pass

        return report
