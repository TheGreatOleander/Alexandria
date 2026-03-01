"""
Alexandria — Relations

Typed edges between lattice positions. These are the field equations
of the system. Relations infer unknown values and check consistency
of known ones.

Numeric:
    SumRelation, RatioRelation, EqualityRelation,
    BoundedRelation, FunctionRelation

Categorical / Boolean:
    EnumRelation, ExclusionRelation, CategoricalImplicationRelation,
    NegationRelation, ExactlyOneRelation, AllTrueRelation, AnyTrueRelation

Composite:
    ConditionalRelation, TemporalRelation
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional, Set


class Relation(ABC):
    @abstractmethod
    def infer(self, state: Dict[str, Any]) -> Optional[Dict[str, Any]]: ...

    @abstractmethod
    def check(self, state: Dict[str, Any]) -> Optional[str]: ...

    @abstractmethod
    def keys(self) -> Set[str]: ...

    def describe(self) -> str:
        return self.__class__.__name__


# ---------------------------------------------------------------------------
# Numeric
# ---------------------------------------------------------------------------

class SumRelation(Relation):
    """parts sum to total: total = sum(parts)"""

    def __init__(self, parts: List[str], total: str):
        self.parts = parts
        self.total = total

    def keys(self) -> Set[str]:
        return set(self.parts) | {self.total}

    def infer(self, state: Dict) -> Optional[Dict]:
        known = {k: state[k] for k in self.parts if k in state}
        has_total = self.total in state
        if len(known) == len(self.parts) and not has_total:
            return {self.total: sum(known.values())}
        missing = [k for k in self.parts if k not in state]
        if has_total and len(missing) == 1:
            return {missing[0]: state[self.total] - sum(known.values())}
        return None

    def check(self, state: Dict) -> Optional[str]:
        if all(k in state for k in self.parts) and self.total in state:
            s = sum(state[k] for k in self.parts)
            if abs(s - state[self.total]) > 1e-9:
                return f"SumRelation: sum({self.parts})={s} ≠ {self.total}={state[self.total]}"
        return None

    def describe(self) -> str:
        return f"{self.total} = sum({self.parts})"


class RatioRelation(Relation):
    """a / b = ratio"""

    def __init__(self, numerator: str, denominator: str, ratio_key: str):
        self.numerator = numerator
        self.denominator = denominator
        self.ratio_key = ratio_key

    def keys(self) -> Set[str]:
        return {self.numerator, self.denominator, self.ratio_key}

    def infer(self, state: Dict) -> Optional[Dict]:
        n, d, r = self.numerator, self.denominator, self.ratio_key
        if n in state and d in state and r not in state and state[d] != 0:
            return {r: state[n] / state[d]}
        if r in state and d in state and n not in state:
            return {n: state[r] * state[d]}
        if r in state and n in state and d not in state and state[r] != 0:
            return {d: state[n] / state[r]}
        return None

    def check(self, state: Dict) -> Optional[str]:
        n, d, r = self.numerator, self.denominator, self.ratio_key
        if all(k in state for k in [n, d, r]) and state[d] != 0:
            computed = state[n] / state[d]
            if abs(computed - state[r]) > 1e-9:
                return f"RatioRelation: {n}/{d}={computed} ≠ {r}={state[r]}"
        return None

    def describe(self) -> str:
        return f"{self.ratio_key} = {self.numerator} / {self.denominator}"


class EqualityRelation(Relation):
    """a = b"""

    def __init__(self, key_a: str, key_b: str):
        self.key_a = key_a
        self.key_b = key_b

    def keys(self) -> Set[str]:
        return {self.key_a, self.key_b}

    def infer(self, state: Dict) -> Optional[Dict]:
        a, b = self.key_a, self.key_b
        if a in state and b not in state:
            return {b: state[a]}
        if b in state and a not in state:
            return {a: state[b]}
        return None

    def check(self, state: Dict) -> Optional[str]:
        a, b = self.key_a, self.key_b
        if a in state and b in state and state[a] != state[b]:
            return f"EqualityRelation: {a}={state[a]} ≠ {b}={state[b]}"
        return None

    def describe(self) -> str:
        return f"{self.key_a} = {self.key_b}"


class BoundedRelation(Relation):
    """lo <= value <= hi"""

    def __init__(self, key: str, lo_key: Optional[str] = None,
                 hi_key: Optional[str] = None, lo_val: Optional[float] = None,
                 hi_val: Optional[float] = None):
        self.key = key
        self.lo_key, self.hi_key = lo_key, hi_key
        self.lo_val, self.hi_val = lo_val, hi_val

    def keys(self) -> Set[str]:
        ks = {self.key}
        if self.lo_key:
            ks.add(self.lo_key)
        if self.hi_key:
            ks.add(self.hi_key)
        return ks

    def infer(self, state: Dict) -> Optional[Dict]:
        return None

    def check(self, state: Dict) -> Optional[str]:
        if self.key not in state:
            return None
        v = state[self.key]
        lo = state.get(self.lo_key, self.lo_val) if self.lo_key else self.lo_val
        hi = state.get(self.hi_key, self.hi_val) if self.hi_key else self.hi_val
        if lo is not None and v < lo:
            return f"BoundedRelation: {self.key}={v} < lo={lo}"
        if hi is not None and v > hi:
            return f"BoundedRelation: {self.key}={v} > hi={hi}"
        return None

    def describe(self) -> str:
        return f"{self.lo_key or self.lo_val} ≤ {self.key} ≤ {self.hi_key or self.hi_val}"


class FunctionRelation(Relation):
    """output = f(*inputs)"""

    def __init__(self, inputs: List[str], output: str, fn: Callable,
                 description: str = ""):
        self.inputs = inputs
        self.output = output
        self.fn = fn
        self._description = description

    def keys(self) -> Set[str]:
        return set(self.inputs) | {self.output}

    def infer(self, state: Dict) -> Optional[Dict]:
        if all(k in state for k in self.inputs) and self.output not in state:
            try:
                return {self.output: self.fn(*[state[k] for k in self.inputs])}
            except Exception:
                return None
        return None

    def check(self, state: Dict) -> Optional[str]:
        if all(k in state for k in self.inputs) and self.output in state:
            try:
                expected = self.fn(*[state[k] for k in self.inputs])
                if state[self.output] != expected:
                    return (f"FunctionRelation: {self.output} should be "
                            f"{expected}, got {state[self.output]}")
            except Exception:
                pass
        return None

    def describe(self) -> str:
        return self._description or f"{self.output} = f({self.inputs})"


# ---------------------------------------------------------------------------
# Categorical / Boolean
# ---------------------------------------------------------------------------

class EnumRelation(Relation):
    """Value must be one of an allowed set."""

    def __init__(self, key: str, allowed: Set[Any]):
        self.key = key
        self.allowed = set(allowed)

    def keys(self) -> Set[str]:
        return {self.key}

    def infer(self, state: Dict) -> Optional[Dict]:
        if self.key not in state and len(self.allowed) == 1:
            return {self.key: next(iter(self.allowed))}
        return None

    def check(self, state: Dict) -> Optional[str]:
        if self.key in state and state[self.key] not in self.allowed:
            return f"EnumRelation: '{self.key}'={state[self.key]!r} not in {self.allowed}"
        return None

    def describe(self):
        return f"{self.key} ∈ {self.allowed}"


class ExclusionRelation(Relation):
    """If key A = value_a, then key B must NOT equal value_b."""

    def __init__(self, key_a: str, value_a: Any, key_b: str, forbidden_b: Any):
        self.key_a = key_a
        self.value_a = value_a
        self.key_b = key_b
        self.forbidden_b = forbidden_b

    def keys(self) -> Set[str]:
        return {self.key_a, self.key_b}

    def infer(self, state: Dict) -> Optional[Dict]:
        return None

    def check(self, state: Dict) -> Optional[str]:
        if (state.get(self.key_a) == self.value_a and
                state.get(self.key_b) == self.forbidden_b):
            return (f"ExclusionRelation: {self.key_a}={self.value_a!r} "
                    f"forbids {self.key_b}={self.forbidden_b!r}")
        return None

    def describe(self):
        return (f"if {self.key_a}={self.value_a!r} "
                f"then {self.key_b}≠{self.forbidden_b!r}")


class CategoricalImplicationRelation(Relation):
    """If key A = value_a, then key B must equal value_b."""

    def __init__(self, key_a: str, value_a: Any, key_b: str, value_b: Any):
        self.key_a = key_a
        self.value_a = value_a
        self.key_b = key_b
        self.value_b = value_b

    def keys(self) -> Set[str]:
        return {self.key_a, self.key_b}

    def infer(self, state: Dict) -> Optional[Dict]:
        if state.get(self.key_a) == self.value_a and self.key_b not in state:
            return {self.key_b: self.value_b}
        return None

    def check(self, state: Dict) -> Optional[str]:
        if (state.get(self.key_a) == self.value_a and
                self.key_b in state and state[self.key_b] != self.value_b):
            return (f"CategoricalImplication: {self.key_a}={self.value_a!r} "
                    f"requires {self.key_b}={self.value_b!r}, "
                    f"got {state[self.key_b]!r}")
        return None

    def describe(self):
        return f"if {self.key_a}={self.value_a!r} then {self.key_b}={self.value_b!r}"


class NegationRelation(Relation):
    """A = not B (boolean negation)."""

    def __init__(self, key_a: str, key_b: str):
        self.key_a = key_a
        self.key_b = key_b

    def keys(self) -> Set[str]:
        return {self.key_a, self.key_b}

    def infer(self, state: Dict) -> Optional[Dict]:
        if self.key_a in state and self.key_b not in state:
            return {self.key_b: not state[self.key_a]}
        if self.key_b in state and self.key_a not in state:
            return {self.key_a: not state[self.key_b]}
        return None

    def check(self, state: Dict) -> Optional[str]:
        if self.key_a in state and self.key_b in state:
            if state[self.key_a] != (not state[self.key_b]):
                return (f"NegationRelation: {self.key_a}={state[self.key_a]} "
                        f"should negate {self.key_b}={state[self.key_b]}")
        return None

    def describe(self):
        return f"{self.key_a} = ¬{self.key_b}"


class ExactlyOneRelation(Relation):
    """Exactly one of a set of boolean keys must be True (partition)."""

    def __init__(self, keys: List[str]):
        self._keys = keys

    def keys(self) -> Set[str]:
        return set(self._keys)

    def infer(self, state: Dict) -> Optional[Dict]:
        known = {k: state[k] for k in self._keys if k in state}
        unknown = [k for k in self._keys if k not in state]
        true_count = sum(1 for v in known.values() if v is True)
        false_count = sum(1 for v in known.values() if v is False)
        if len(unknown) == 1:
            if true_count == 1:
                return {unknown[0]: False}
            if true_count == 0 and false_count == len(known):
                return {unknown[0]: True}
        return None

    def check(self, state: Dict) -> Optional[str]:
        if all(k in state for k in self._keys):
            true_count = sum(1 for k in self._keys if state[k] is True)
            if true_count != 1:
                return (f"ExactlyOneRelation: exactly 1 of {self._keys} "
                        f"must be True, got {true_count}")
        return None

    def describe(self):
        return f"ExactlyOne({self._keys})"


class AllTrueRelation(Relation):
    """All boolean keys must be True → output = all(keys)."""

    def __init__(self, keys: List[str], output: str):
        self._input_keys = keys
        self.output = output

    def keys(self) -> Set[str]:
        return set(self._input_keys) | {self.output}

    def infer(self, state: Dict) -> Optional[Dict]:
        if all(k in state for k in self._input_keys) and self.output not in state:
            return {self.output: all(state[k] is True for k in self._input_keys)}
        if self.output in state and state[self.output] is False:
            unknown = [k for k in self._input_keys if k not in state]
            if len(unknown) == 1 and all(
                state.get(k, True) is True
                for k in self._input_keys if k != unknown[0]
            ):
                return {unknown[0]: False}
        return None

    def check(self, state: Dict) -> Optional[str]:
        if all(k in state for k in self._input_keys) and self.output in state:
            expected = all(state[k] is True for k in self._input_keys)
            if state[self.output] != expected:
                return f"AllTrueRelation: {self.output} should be {expected}"
        return None

    def describe(self):
        return f"{self.output} = all({self._input_keys})"


class AnyTrueRelation(Relation):
    """At least one of the boolean keys must be True → output = any(keys)."""

    def __init__(self, keys: List[str], output: str):
        self._input_keys = keys
        self.output = output

    def keys(self) -> Set[str]:
        return set(self._input_keys) | {self.output}

    def infer(self, state: Dict) -> Optional[Dict]:
        if all(k in state for k in self._input_keys) and self.output not in state:
            return {self.output: any(state[k] is True for k in self._input_keys)}
        return None

    def check(self, state: Dict) -> Optional[str]:
        if all(k in state for k in self._input_keys) and self.output in state:
            expected = any(state[k] is True for k in self._input_keys)
            if state[self.output] != expected:
                return f"AnyTrueRelation: {self.output} should be {expected}"
        return None

    def describe(self):
        return f"{self.output} = any({self._input_keys})"


# ---------------------------------------------------------------------------
# Composite
# ---------------------------------------------------------------------------

class ConditionalRelation(Relation):
    """
    If predicate(state) is True, apply inner_relation.
    Marked volatile — predicate is re-evaluated every solver pass.
    """
    volatile = True

    def __init__(self, predicate: Callable[[Dict], bool], inner: Relation,
                 description: str = ""):
        self.predicate = predicate
        self.inner = inner
        self._description = description

    def keys(self) -> Set[str]:
        return self.inner.keys()

    def infer(self, state: Dict) -> Optional[Dict]:
        if self.predicate(state):
            return self.inner.infer(state)
        return None

    def check(self, state: Dict) -> Optional[str]:
        if self.predicate(state):
            return self.inner.check(state)
        return None

    def describe(self):
        return self._description or f"if <predicate> then [{self.inner.describe()}]"


class TemporalRelation(Relation):
    """
    Relates a key's value to its previous value.
    Requires state to carry '_prev_{key}' — injected automatically by
    TemporalKernel when this relation is registered.
    """

    def __init__(self, key: str, max_delta: Optional[float] = None,
                 min_delta: Optional[float] = None):
        self.key = key
        self.max_delta = max_delta
        self.min_delta = min_delta
        self._prev_key = f"_prev_{key}"

    def keys(self) -> Set[str]:
        return {self.key, self._prev_key}

    def infer(self, state: Dict) -> Optional[Dict]:
        return None

    def check(self, state: Dict) -> Optional[str]:
        if self.key in state and self._prev_key in state:
            delta = state[self.key] - state[self._prev_key]
            if self.max_delta is not None and delta > self.max_delta:
                return (f"TemporalRelation: {self.key} increased by {delta} "
                        f"> max_delta={self.max_delta}")
            if self.min_delta is not None and delta < self.min_delta:
                return (f"TemporalRelation: {self.key} changed by {delta} "
                        f"< min_delta={self.min_delta}")
        return None

    def describe(self):
        parts = []
        if self.max_delta is not None:
            parts.append(f"Δ≤{self.max_delta}")
        if self.min_delta is not None:
            parts.append(f"Δ≥{self.min_delta}")
        return f"Temporal({self.key}: {', '.join(parts)})"
