"""
Alexandria — Named Inference Rules and RuleSets

InferenceRule wraps a Relation with a name and description, making
every inferred value traceable to a named proposition rather than an
anonymous equation. This closes the legibility loop.

RuleSet groups rules into a coherent domain theory that can be attached
to a Lattice as a unit.

Usage:

    ruleset = (
        RuleSet("financial")
        .rule("revenue",  SumRelation(["costs", "profit"], "revenue"),
              "Revenue equals costs plus profit")
        .rule("margin",   RatioRelation("profit", "revenue", "margin"),
              "Margin is profit over revenue")
    )

    ruleset.attach_to(lattice)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from alexandria.relations import Relation
    from alexandria.kernel import Lattice


@dataclass
class InferenceRule:
    """
    A named, documented inference rule.

    Rules are relations with identity — they can be cited in provenance.
    Every inferred value traces back to a named proposition,
    not just an anonymous equation.
    """
    name: str
    relation: "Relation"
    description: str
    confidence: float = 1.0  # 0.0–1.0; reserved for probabilistic extensions

    def infer(self, state: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        return self.relation.infer(state)

    def check(self, state: Dict[str, Any]) -> Optional[str]:
        return self.relation.check(state)

    def keys(self):
        return self.relation.keys()

    def describe(self) -> str:
        return f"[{self.name}] {self.description}"


class RuleSet:
    """
    A named collection of InferenceRules forming a coherent domain theory.
    Attach to a Lattice to register all rules as active relations.
    """

    def __init__(self, name: str):
        self.name = name
        self._rules: Dict[str, InferenceRule] = {}

    def add(self, rule: InferenceRule) -> "RuleSet":
        self._rules[rule.name] = rule
        return self

    def rule(
        self,
        name: str,
        relation: "Relation",
        description: str,
        confidence: float = 1.0,
    ) -> "RuleSet":
        """Convenience: create and register a rule in one call."""
        return self.add(InferenceRule(
            name=name,
            relation=relation,
            description=description,
            confidence=confidence,
        ))

    def rules(self) -> List[InferenceRule]:
        return list(self._rules.values())

    def relations(self) -> List["Relation"]:
        return [r.relation for r in self._rules.values()]

    def get(self, name: str) -> Optional[InferenceRule]:
        return self._rules.get(name)

    def attach_to(self, lattice: "Lattice") -> "RuleSet":
        """Register all rules as relations on the given Lattice."""
        for rule in self._rules.values():
            lattice.relate(rule.relation)
        return self

    def __len__(self) -> int:
        return len(self._rules)

    def __repr__(self) -> str:
        return f"RuleSet(name={self.name!r}, rules={list(self._rules.keys())})"
