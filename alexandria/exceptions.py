"""
Alexandria — Exceptions

All custom exceptions raised by the kernel.
Import from here or from the top-level `alexandria` package.
"""


class LatticeViolation(Exception):
    """Raised when a value violates a lattice position constraint."""


class DomainViolation(Exception):
    """Raised when a domain attempts to write a key it does not own."""


class InvariantViolation(Exception):
    """Raised when an invariant (conservation law) is broken."""


class SolverContradiction(Exception):
    """Raised when constraint propagation produces an irreconcilable conflict."""


class EquilibriumUnreachable(Exception):
    """Raised when the system cannot reach equilibrium within the step limit."""


class LedgerCorruption(Exception):
    """Raised when a ledger event fails its cryptographic hash check."""


class ConflictUnresolvable(Exception):
    """Raised when no policy in a chain can resolve a reconciliation conflict."""
