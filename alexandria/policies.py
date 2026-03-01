"""
Alexandria — Conflict Resolution Policies

Policies determine how to resolve conflicts between two values for the
same key when reconciling divergent branches.

A policy returns the winning value, ConflictPolicy.UNRESOLVED (sentinel)
if it cannot decide, or raises ConflictUnresolvable if resolution is
impossible.

Available policies:

    LastWriteWins         — higher timestamp wins
    DomainAuthorityWins   — designated domain's value wins per key
    ConservativeWins      — picks the safer value (derives direction from invariants)
    MergeFunction         — custom callable merge
    OperatorPrompt        — interactive callback for unresolvable conflicts
    PolicyChain           — compose policies with fallback semantics

Usage:

    policy = PolicyChain(
        DomainAuthorityWins({"balance": "finance"}),
        LastWriteWins(),
    )
    k = TemporalKernel(policy=policy)
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING

from alexandria.exceptions import ConflictUnresolvable

if TYPE_CHECKING:
    from alexandria.invariants import (
        Invariant, ValueMustBePositive, ValueNeverDecreases, RelationInvariant,
    )
    from alexandria.relations import BoundedRelation


class ConflictPolicy(ABC):
    """
    Base class for conflict resolution policies.

    resolve() returns:
      - the resolved value        → conflict settled
      - ConflictPolicy.UNRESOLVED → this policy cannot decide; try the next
      - raises ConflictUnresolvable → irreconcilable; stop
    """
    UNRESOLVED = object()

    @abstractmethod
    def resolve(
        self,
        key: str,
        value_a: Any,
        value_b: Any,
        context: Optional[Dict] = None,
    ) -> Any:
        """Returns resolved value, UNRESOLVED sentinel, or raises."""

    def describe(self) -> str:
        return self.__class__.__name__


class LastWriteWins(ConflictPolicy):
    """
    The event with the higher timestamp wins.
    context must include 'ts_a' and 'ts_b'.
    Returns UNRESOLVED if timestamps are equal.
    """

    def resolve(self, key, value_a, value_b, context=None):
        ctx = context or {}
        ts_a = ctx.get("ts_a", 0)
        ts_b = ctx.get("ts_b", 0)
        if ts_a == ts_b:
            return self.UNRESOLVED
        return value_a if ts_a > ts_b else value_b

    def describe(self):
        return "LastWriteWins"


class DomainAuthorityWins(ConflictPolicy):
    """
    A designated authoritative domain's value wins for specific keys.

    authority_map: {key: domain_name} or {key: [domain_names in priority order]}

    Example:
        DomainAuthorityWins({"balance": "finance", "status": ["ops", "admin"]})
    """

    def __init__(self, authority_map: Dict[str, Any]):
        self.authority_map = authority_map

    def resolve(self, key, value_a, value_b, context=None):
        ctx = context or {}
        authority = self.authority_map.get(key)
        if not authority:
            return self.UNRESOLVED
        domain_a = ctx.get("domain_a")
        domain_b = ctx.get("domain_b")
        if isinstance(authority, str):
            if domain_a == authority:
                return value_a
            if domain_b == authority:
                return value_b
        elif isinstance(authority, (list, tuple)):
            for auth in authority:
                if domain_a == auth:
                    return value_a
                if domain_b == auth:
                    return value_b
        return self.UNRESOLVED

    def describe(self):
        return f"DomainAuthorityWins({self.authority_map})"


class ConservativeWins(ConflictPolicy):
    """
    For numeric keys: keep the value that satisfies more invariants,
    or is closer to the safe boundary implied by them.

    Direction can be specified explicitly via key_directions, or derived
    automatically from declared invariants:

      - ValueMustBePositive / ValueNeverDecreases → 'max' (higher is safer)
      - BoundedRelation with hi_val only          → 'min' (lower is safer)
      - No signal                                 → smaller absolute magnitude

    Explicit key_directions always override derived directions.
    """

    def __init__(
        self,
        key_directions: Optional[Dict[str, str]] = None,
        invariants: Optional[List[Any]] = None,
    ):
        self.key_directions = key_directions or {}
        self._invariants = invariants or []
        self._derived: Dict[str, str] = {}
        self._build_derived()

    def _build_derived(self):
        from alexandria.invariants import (
            ValueMustBePositive, ValueNeverDecreases, RelationInvariant,
        )
        from alexandria.relations import BoundedRelation

        for inv in self._invariants:
            if isinstance(inv, ValueMustBePositive):
                self._derived.setdefault(inv.key, "max")
            elif isinstance(inv, ValueNeverDecreases):
                self._derived.setdefault(inv.key, "max")
            elif isinstance(inv, RelationInvariant):
                rel = inv.relation
                if isinstance(rel, BoundedRelation):
                    if rel.hi_val is not None and rel.lo_val is None:
                        self._derived.setdefault(rel.key, "min")
                    elif rel.lo_val is not None and rel.hi_val is None:
                        self._derived.setdefault(rel.key, "max")

    def _direction(self, key: str) -> Optional[str]:
        return self.key_directions.get(key) or self._derived.get(key)

    def resolve(self, key, value_a, value_b, context=None):
        if not (isinstance(value_a, (int, float)) and
                isinstance(value_b, (int, float))):
            return self.UNRESOLVED
        direction = self._direction(key)
        if direction == "max":
            return max(value_a, value_b)
        elif direction == "min":
            return min(value_a, value_b)
        else:
            # No signal: pick smaller absolute magnitude (more central/conservative)
            return value_a if abs(value_a) <= abs(value_b) else value_b

    def describe(self):
        return (f"ConservativeWins(explicit={self.key_directions}, "
                f"derived={self._derived})")


class MergeFunction(ConflictPolicy):
    """
    Custom merge: merged = fn(key, value_a, value_b, context).
    Returns UNRESOLVED if fn returns None.
    """

    def __init__(self, fn: Callable, description: str = ""):
        self.fn = fn
        self._description = description

    def resolve(self, key, value_a, value_b, context=None):
        result = self.fn(key, value_a, value_b, context or {})
        return self.UNRESOLVED if result is None else result

    def describe(self):
        return self._description or "MergeFunction"


class OperatorPrompt(ConflictPolicy):
    """
    Calls a user-supplied callback when no other policy can resolve.
    callback(key, value_a, value_b, context) → resolved_value | None
    If callback returns None, raises ConflictUnresolvable.
    """

    def __init__(self, callback: Callable):
        self.callback = callback

    def resolve(self, key, value_a, value_b, context=None):
        result = self.callback(key, value_a, value_b, context or {})
        if result is None:
            raise ConflictUnresolvable(
                f"Operator could not resolve conflict for '{key}': "
                f"{value_a!r} vs {value_b!r}"
            )
        return result

    def describe(self):
        return "OperatorPrompt"


class PolicyChain(ConflictPolicy):
    """
    Compose multiple policies with fallback semantics.
    Tries each policy in order; uses first non-UNRESOLVED result.
    Raises ConflictUnresolvable if all policies return UNRESOLVED.

    Example:
        PolicyChain(
            DomainAuthorityWins({"balance": "finance"}),
            LastWriteWins(),
            OperatorPrompt(my_callback),
        )
    """

    def __init__(self, *policies: ConflictPolicy):
        self.policies = list(policies)

    def resolve(self, key, value_a, value_b, context=None):
        for policy in self.policies:
            result = policy.resolve(key, value_a, value_b, context)
            if result is not self.UNRESOLVED:
                return result
        raise ConflictUnresolvable(
            f"No policy could resolve conflict for '{key}': "
            f"{value_a!r} vs {value_b!r}"
        )

    def describe(self):
        return f"PolicyChain([{', '.join(p.describe() for p in self.policies)}])"
