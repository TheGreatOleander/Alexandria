"""
Alexandria Temporal Kernel
Canonicalization Field — v9.0

A deterministic, auditable temporal kernel designed to preserve
truth without coercion. It records what happened, when, and under
what context, and allows anyone to replay and inspect that history.

Quick start:

    from alexandria import TemporalKernel, Event, Lattice
    from alexandria.relations import SumRelation
    from alexandria.invariants import ValueMustBePositive

    lattice = (
        Lattice()
        .define("fin", "costs",   {int, float})
        .define("fin", "profit",  {int, float})
        .define("fin", "revenue", {int, float})
        .relate(SumRelation(["costs", "profit"], "revenue"))
    )

    k = TemporalKernel(lattice=lattice)
    k.apply(Event({"costs": 60.0, "profit": 40.0}, domain="fin"))
    print(k.state["revenue"])  # 100.0
    print(k.explain("revenue"))
"""

from alexandria.kernel import (
    TemporalKernel,
    Event,
    Lattice,
    LatticePosition,
    TrustDomain,
    Occupancy,
    VERSION,
)

from alexandria.relations import (
    Relation,
    SumRelation,
    RatioRelation,
    EqualityRelation,
    BoundedRelation,
    FunctionRelation,
    EnumRelation,
    ExclusionRelation,
    CategoricalImplicationRelation,
    NegationRelation,
    ExactlyOneRelation,
    AllTrueRelation,
    AnyTrueRelation,
    ConditionalRelation,
    TemporalRelation,
)

from alexandria.invariants import (
    Invariant,
    KeyMustExist,
    ValueMustBePositive,
    ValueNeverDecreases,
    DomainSumConserved,
    ImplicationInvariant,
    RelationInvariant,
)

from alexandria.domains import TrustDomain

from alexandria.policies import (
    ConflictPolicy,
    LastWriteWins,
    DomainAuthorityWins,
    ConservativeWins,
    MergeFunction,
    OperatorPrompt,
    PolicyChain,
    ConflictUnresolvable,
)

from alexandria.rules import InferenceRule, RuleSet

from alexandria.persistence import LedgerStore, GitLedger

from alexandria.solver import ConstraintSolver, SolverResult

from alexandria.provenance import ProvenanceLog, ProvenanceRecord

from alexandria.schema import SchemaInference, PositionProposal, RelationProposal

from alexandria.reconciler import ForkReconciler, ReconciliationReport

from alexandria.exceptions import (
    LatticeViolation,
    DomainViolation,
    InvariantViolation,
    SolverContradiction,
    EquilibriumUnreachable,
    LedgerCorruption,
)

__version__ = VERSION
__all__ = [
    # Core
    "TemporalKernel", "Event", "Lattice", "LatticePosition",
    "TrustDomain", "Occupancy", "VERSION",
    # Relations
    "Relation", "SumRelation", "RatioRelation", "EqualityRelation",
    "BoundedRelation", "FunctionRelation", "EnumRelation", "ExclusionRelation",
    "CategoricalImplicationRelation", "NegationRelation", "ExactlyOneRelation",
    "AllTrueRelation", "AnyTrueRelation", "ConditionalRelation", "TemporalRelation",
    # Invariants
    "Invariant", "KeyMustExist", "ValueMustBePositive", "ValueNeverDecreases",
    "DomainSumConserved", "ImplicationInvariant", "RelationInvariant",
    # Policies
    "ConflictPolicy", "LastWriteWins", "DomainAuthorityWins", "ConservativeWins",
    "MergeFunction", "OperatorPrompt", "PolicyChain", "ConflictUnresolvable",
    # Rules
    "InferenceRule", "RuleSet",
    # Persistence
    "LedgerStore", "GitLedger",
    # Solver
    "ConstraintSolver", "SolverResult",
    # Provenance
    "ProvenanceLog", "ProvenanceRecord",
    # Schema
    "SchemaInference", "PositionProposal", "RelationProposal",
    # Reconciler
    "ForkReconciler", "ReconciliationReport",
    # Exceptions
    "LatticeViolation", "DomainViolation", "InvariantViolation",
    "SolverContradiction", "EquilibriumUnreachable", "LedgerCorruption",
]
