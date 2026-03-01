"""
Alexandria — Trust Domains

A Trust Domain is a contextual boundary, not a hierarchy.
Domains isolate write authority — a domain can only write keys it owns.

Domains do not override one another. Events are always domain-labelled.
Cross-domain reconciliation is observational, not hierarchical.

Per SPEC §7: forks are preserved, not collapsed.

Usage:

    finance = TrustDomain("finance", owns={"balance", "revenue", "costs"})
    ops     = TrustDomain("ops",     owns={"status", "region"})

    k = TemporalKernel(domains={"finance": finance, "ops": ops})
    k.apply(Event({"balance": 1000.0}, domain="finance"))  # ok
    k.apply(Event({"balance": 500.0},  domain="ops"))       # DomainViolation
"""

from __future__ import annotations

from typing import Optional, Set

from alexandria.exceptions import DomainViolation


class TrustDomain:
    """
    A named authority boundary.

    If `owns` is provided, only keys in that set may be written
    by events carrying this domain. An empty or None `owns` set
    means the domain is unrestricted.
    """

    def __init__(self, name: str, owns: Optional[Set[str]] = None):
        self.name = name
        self.owns: Set[str] = owns or set()

    def assert_write(self, key: str):
        """
        Raise DomainViolation if this domain is not authorised to write `key`.
        No-op if the domain has no declared ownership set.
        """
        if self.owns and key not in self.owns:
            raise DomainViolation(
                f"Domain '{self.name}' cannot write key '{key}'. "
                f"Owned keys: {sorted(self.owns)}"
            )

    def owns_key(self, key: str) -> bool:
        """Return True if this domain owns the given key (or is unrestricted)."""
        return not self.owns or key in self.owns

    def __repr__(self) -> str:
        return f"TrustDomain(name={self.name!r}, owns={sorted(self.owns)})"
