"""
Alexandria — Schema Inference

Observes events and proposes lattice positions and relations.
The system learns the shape of its own domain from evidence.

Position proposals: frequency analysis + type consistency.

Relation proposals: tests candidate relation types against all
co-observed events. A relation is proposed only if it holds
consistently across observed data — not just because keys co-occur.

Usage:

    k = TemporalKernel()
    for event in my_events:
        k.apply(event)

    # What positions should the lattice have?
    for proposal in k.infer_schema(min_occurrence=3):
        print(proposal.describe())

    # What relations hold in the data?
    for proposal in k.infer_relations(min_cooccurrence=5, min_confidence=0.9):
        print(proposal.describe())
        print(proposal.constructor)  # copy-paste ready Python
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from alexandria.kernel import Event
    from alexandria.relations import Relation


@dataclass
class PositionProposal:
    key: str
    observed_types: Set[str]
    occurrence_count: int
    domains_seen: Set[str]
    example_values: List[Any]
    suggested_required: bool
    confidence: float

    def describe(self) -> str:
        domain = list(self.domains_seen)[0] if self.domains_seen else "unknown"
        types = ", ".join(sorted(self.observed_types))
        return (
            f"lattice.define(domain='{domain}', key='{self.key}', "
            f"required={self.suggested_required})  "
            f"# types={{{types}}}, confidence={self.confidence:.2f}, "
            f"seen={self.occurrence_count}x"
        )


@dataclass
class RelationProposal:
    """
    A relation inferred from observed data, with empirical confidence.
    Confidence = fraction of co-observations where the relation holds.
    """
    relation_type: str
    keys: Tuple
    confidence: float
    observations: int
    description: str
    constructor: str   # copy-paste ready Python expression

    def describe(self) -> str:
        return (
            f"{self.relation_type}({self.description})  "
            f"# confidence={self.confidence:.2f}, n={self.observations}"
        )

    def instantiate(self) -> Optional["Relation"]:
        """Attempt to instantiate the proposed relation."""
        try:
            from alexandria.relations import (
                EqualityRelation, SumRelation, RatioRelation,
            )
            keys = list(self.keys)
            if self.relation_type == "EqualityRelation":
                return EqualityRelation(keys[0], keys[1])
            elif self.relation_type == "SumRelation":
                import re
                m = re.match(
                    r"SumRelation\(\['(.+)', '(.+)'\], '(.+)'\)",
                    self.constructor,
                )
                if m:
                    return SumRelation([m.group(1), m.group(2)], m.group(3))
            elif self.relation_type == "RatioRelation":
                return RatioRelation(keys[0], keys[1], keys[2])
        except Exception:
            pass
        return None


class SchemaInference:
    """
    Observes events and proposes lattice positions and relations.
    """

    def __init__(self):
        self._key_counts: Dict[str, int] = defaultdict(int)
        self._key_types: Dict[str, Set[str]] = defaultdict(set)
        self._key_domains: Dict[str, Set[str]] = defaultdict(set)
        self._key_examples: Dict[str, List] = defaultdict(list)
        self._cooccurrence: Dict[Tuple[str, str], int] = defaultdict(int)
        self._coobservations: Dict[Tuple, List[Dict]] = defaultdict(list)
        self._total_events = 0

    def observe(self, event: "Event"):
        self._total_events += 1
        keys = sorted(event.payload.keys())
        for key, value in event.payload.items():
            self._key_counts[key] += 1
            self._key_types[key].add(type(value).__name__)
            self._key_domains[key].add(event.domain)
            if len(self._key_examples[key]) < 10:
                self._key_examples[key].append(value)
        for i, k1 in enumerate(keys):
            for k2 in keys[i + 1:]:
                pair = (k1, k2)
                self._cooccurrence[pair] += 1
        for i, k1 in enumerate(keys):
            for k2 in keys[i + 1:]:
                for k3 in keys[i + 2:] if i + 2 < len(keys) else []:
                    triple = (k1, k2, k3)
                    if len(self._coobservations[triple]) < 50:
                        self._coobservations[triple].append(dict(event.payload))
            if len(keys) > 1:
                pair = (k1, keys[i + 1]) if i + 1 < len(keys) else None
                if pair and len(self._coobservations[pair]) < 50:
                    self._coobservations[pair].append(dict(event.payload))

    def observe_all(self, ledger: List["Event"]) -> "SchemaInference":
        for e in ledger:
            self.observe(e)
        return self

    def proposals(self, min_occurrence: int = 2) -> List[PositionProposal]:
        result = []
        for key, count in self._key_counts.items():
            if count < min_occurrence:
                continue
            freq = count / max(self._total_events, 1)
            type_consistent = len(self._key_types[key]) == 1
            confidence = freq * (0.9 if type_consistent else 0.5)
            result.append(PositionProposal(
                key=key,
                observed_types=self._key_types[key],
                occurrence_count=count,
                domains_seen=self._key_domains[key],
                example_values=self._key_examples[key],
                suggested_required=freq > 0.8,
                confidence=confidence,
            ))
        return sorted(result, key=lambda p: p.confidence, reverse=True)

    def relation_proposals(
        self,
        min_cooccurrence: int = 3,
        min_confidence: float = 0.8,
    ) -> List[RelationProposal]:
        """
        Test candidate relations against observed co-occurrence data.
        Returns proposals sorted by confidence.
        Only proposes relations that hold on >= min_confidence fraction
        of co-observations where all keys are present.
        """
        proposals: List[RelationProposal] = []
        tol = 1e-6

        def _confidence(observations, check_fn) -> float:
            if not observations:
                return 0.0
            hits = sum(1 for obs in observations if check_fn(obs))
            return hits / len(observations)

        # EqualityRelation
        for (k1, k2), count in self._cooccurrence.items():
            if count < min_cooccurrence:
                continue
            obs = self._coobservations.get((k1, k2), [])
            relevant = [
                o for o in obs if k1 in o and k2 in o
                and isinstance(o[k1], (int, float))
                and isinstance(o[k2], (int, float))
            ]
            if len(relevant) < min_cooccurrence:
                continue
            conf = _confidence(
                relevant,
                lambda o, a=k1, b=k2: abs(o[a] - o[b]) < tol,
            )
            if conf >= min_confidence:
                proposals.append(RelationProposal(
                    relation_type="EqualityRelation",
                    keys=(k1, k2),
                    confidence=conf,
                    observations=len(relevant),
                    description=f"{k1} = {k2}",
                    constructor=f"EqualityRelation('{k1}', '{k2}')",
                ))

        # SumRelation
        for triple, obs in self._coobservations.items():
            if len(triple) != 3 or len(obs) < min_cooccurrence:
                continue
            k1, k2, k3 = triple
            for total, parts in [
                (k1, (k2, k3)), (k2, (k1, k3)), (k3, (k1, k2))
            ]:
                p1, p2 = parts
                relevant = [
                    o for o in obs if all(k in o for k in triple)
                    and all(isinstance(o[k], (int, float)) for k in triple)
                ]
                if len(relevant) < min_cooccurrence:
                    continue
                conf = _confidence(
                    relevant,
                    lambda o, t=total, a=p1, b=p2: abs(o[a] + o[b] - o[t]) < tol,
                )
                if conf >= min_confidence:
                    proposals.append(RelationProposal(
                        relation_type="SumRelation",
                        keys=triple,
                        confidence=conf,
                        observations=len(relevant),
                        description=f"{total} = {p1} + {p2}",
                        constructor=f"SumRelation(['{p1}', '{p2}'], '{total}')",
                    ))

        # RatioRelation
        for triple, obs in self._coobservations.items():
            if len(triple) != 3 or len(obs) < min_cooccurrence:
                continue
            perms = [
                triple,
                (triple[1], triple[0], triple[2]),
                (triple[0], triple[2], triple[1]),
                (triple[2], triple[0], triple[1]),
                (triple[1], triple[2], triple[0]),
                (triple[2], triple[1], triple[0]),
            ]
            for n, d, r in perms:
                relevant = [
                    o for o in obs if all(k in o for k in [n, d, r])
                    and all(isinstance(o[k], (int, float)) for k in [n, d, r])
                    and o[d] != 0
                ]
                if len(relevant) < min_cooccurrence:
                    continue
                conf = _confidence(
                    relevant,
                    lambda o, nn=n, dd=d, rr=r: abs(o[nn] / o[dd] - o[rr]) < tol,
                )
                if conf >= min_confidence:
                    proposals.append(RelationProposal(
                        relation_type="RatioRelation",
                        keys=(n, d, r),
                        confidence=conf,
                        observations=len(relevant),
                        description=f"{r} = {n} / {d}",
                        constructor=f"RatioRelation('{n}', '{d}', '{r}')",
                    ))

        # Deduplicate by constructor, keep highest confidence
        seen: Dict[str, RelationProposal] = {}
        for p in proposals:
            if (p.constructor not in seen or
                    p.confidence > seen[p.constructor].confidence):
                seen[p.constructor] = p
        return sorted(seen.values(), key=lambda p: p.confidence, reverse=True)
