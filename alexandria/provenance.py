"""
Alexandria — Provenance

Provenance answers: "Why does this value exist?"

Every value in state has a ProvenanceRecord. Records trace back to either:
  - an Event (the value was set directly)
  - an inference (the value was derived by a relation)
  - a propagator (the value was filled by a default factory)

explain_chain() walks the full derivation graph back to originating events,
giving a complete audit trail for any value in the system.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, TYPE_CHECKING

if TYPE_CHECKING:
    from alexandria.relations import Relation
    from alexandria.kernel import Event


@dataclass
class ProvenanceRecord:
    key: str
    value: Any
    source: str          # "event" | "inferred" | "propagator"
    event_id: Optional[str]
    relation: Optional[str]
    ts: int
    derived_from: List[str]

    def explain(self) -> str:
        if self.source == "event":
            return (f"'{self.key}' = {self.value!r} "
                    f"— set by event {self.event_id}")
        elif self.source == "inferred":
            return (f"'{self.key}' = {self.value!r} "
                    f"— inferred via [{self.relation}] from {self.derived_from}")
        elif self.source == "propagator":
            return (f"'{self.key}' = {self.value!r} "
                    f"— filled by propagator (default)")
        return f"'{self.key}' = {self.value!r} — source: {self.source}"


class ProvenanceLog:
    """
    Append-only log of ProvenanceRecords, keyed by state key.
    The latest record for each key is always the current one.
    """

    def __init__(self):
        self._records: Dict[str, ProvenanceRecord] = {}

    def record_event(self, key: str, value: Any, event: "Event"):
        self._records[key] = ProvenanceRecord(
            key=key, value=value, source="event",
            event_id=event.id, relation=None, ts=event.ts, derived_from=[]
        )

    def record_inference(
        self,
        key: str,
        value: Any,
        relation: "Relation",
        derived_from: List[str],
    ):
        self._records[key] = ProvenanceRecord(
            key=key, value=value, source="inferred",
            event_id=None, relation=relation.describe(),
            ts=time.time_ns(), derived_from=derived_from,
        )

    def record_propagator(self, key: str, value: Any):
        self._records[key] = ProvenanceRecord(
            key=key, value=value, source="propagator",
            event_id=None, relation=None, ts=time.time_ns(), derived_from=[]
        )

    def explain(self, key: str) -> str:
        if key not in self._records:
            return f"'{key}' — no provenance recorded"
        return self._records[key].explain()

    def explain_all(self) -> Dict[str, str]:
        return {k: r.explain() for k, r in self._records.items()}

    def get(self, key: str) -> Optional[ProvenanceRecord]:
        return self._records.get(key)

    def explain_chain(
        self,
        key: str,
        _seen: Optional[Set[str]] = None,
    ) -> List[str]:
        """
        Walk the derivation chain back to originating events.
        Returns explanation strings from the key back to root causes.
        Handles cycles via _seen guard.
        """
        if _seen is None:
            _seen = set()
        if key in _seen:
            return [f"'{key}' — circular derivation detected"]
        _seen = _seen | {key}
        rec = self._records.get(key)
        if rec is None:
            return [f"'{key}' — no provenance recorded"]
        lines = [rec.explain()]
        for parent_key in rec.derived_from:
            parent_lines = self.explain_chain(parent_key, _seen)
            lines.extend(f"  ← {line}" for line in parent_lines)
        return lines

    def clear(self):
        self._records.clear()
