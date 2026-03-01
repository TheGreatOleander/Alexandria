"""
Alexandria — Invariants

Invariants are conservation laws. They halt progression on violation.
They do not decide correctness — they enforce admissibility.

Register invariants on TemporalKernel at construction time:

    k = TemporalKernel(invariants=[
        KeyMustExist("user_id"),
        ValueMustBePositive("balance"),
        ValueNeverDecreases("sequence"),
    ])
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from alexandria.exceptions import InvariantViolation

if TYPE_CHECKING:
    from alexandria.relations import Relation, BoundedRelation


class Invariant(ABC):
    @abstractmethod
    def check(self, state: Dict, event: Any): ...

    def describe(self) -> str:
        return self.__class__.__name__


class KeyMustExist(Invariant):
    """A key must be present in state after the event is applied."""

    def __init__(self, key: str):
        self.key = key

    def check(self, state, event):
        if self.key not in state:
            raise InvariantViolation(f"'{self.key}' must exist")

    def describe(self):
        return f"KeyMustExist({self.key})"


class ValueMustBePositive(Invariant):
    """A numeric key must be >= 0."""

    def __init__(self, key: str):
        self.key = key

    def check(self, state, event):
        v = state.get(self.key)
        if v is not None and v < 0:
            raise InvariantViolation(
                f"'{self.key}' must be ≥ 0, got {v}"
            )

    def describe(self):
        return f"ValueMustBePositive({self.key})"


class ValueNeverDecreases(Invariant):
    """A numeric key must never decrease between events."""

    def __init__(self, key: str):
        self.key = key
        self._last: Optional[Any] = None

    def check(self, state, event):
        v = state.get(self.key)
        if v is not None and self._last is not None and v < self._last:
            raise InvariantViolation(
                f"'{self.key}' decreased {self._last}→{v}"
            )
        if v is not None:
            self._last = v

    def describe(self):
        return f"ValueNeverDecreases({self.key})"


class DomainSumConserved(Invariant):
    """The sum of a set of keys must remain constant once established."""

    def __init__(self, keys: List[str], total: Optional[float] = None):
        self.keys = keys
        self.total = total

    def check(self, state, event):
        vals = [state[k] for k in self.keys if k in state]
        if len(vals) == len(self.keys):
            s = sum(vals)
            if self.total is None:
                self.total = s
            elif abs(s - self.total) > 1e-9:
                raise InvariantViolation(
                    f"sum({self.keys}) must be {self.total}, got {s}"
                )

    def describe(self):
        return f"DomainSumConserved({self.keys})"


class ImplicationInvariant(Invariant):
    """If if_key is present, then_key must also be present."""

    def __init__(self, if_key: str, then_key: str):
        self.if_key = if_key
        self.then_key = then_key

    def check(self, state, event):
        if self.if_key in state and self.then_key not in state:
            raise InvariantViolation(
                f"'{self.if_key}' requires '{self.then_key}'"
            )

    def describe(self):
        return f"Implies({self.if_key} → {self.then_key})"


class RelationInvariant(Invariant):
    """Wraps any Relation as a hard invariant (conservation law)."""

    def __init__(self, relation: "Relation"):
        self.relation = relation

    def check(self, state, event):
        err = self.relation.check(state)
        if err:
            raise InvariantViolation(err)

    def describe(self):
        return f"RelationInvariant({self.relation.describe()})"
