# Alexandria Temporal Kernel

> *"Alexandria does not answer questions. It preserves the conditions under which answers can be trusted."*

Alexandria is a deterministic, auditable temporal kernel. It is a **canonicalization field** — a system that preserves a singular historical sequence, enforces invariant-bound state transitions, and guarantees that all state is derivative of history.

It is not a database. It is not an event bus. It is not a simulation engine. It is a system that **remembers** — and from memory alone, can reconstruct truth.

---

## The Core Idea

Most systems treat state as primary. Alexandria treats **history** as primary. State is just what you get when you replay history to the present moment.

This means:

- State is never stored directly — it is always derived
- Any value in the system can be traced back to the exact event that caused it
- Replaying the ledger from the beginning always produces identical state
- Nothing is hidden. Nothing is implicit.

This is the Mendeleev Principle applied to software: **define the lattice first, then fill it with evidence.**

---

## Installation

```bash
pip install alexandria-temporal-kernel
```

Requires Python 3.9+.

---

## Quickstart

```python
from alexandria import TemporalKernel, Event, Lattice
from alexandria.relations import SumRelation, RatioRelation
from alexandria.invariants import ValueMustBePositive

# Define the shape of what could exist
lattice = (
    Lattice()
    .define("fin", "costs",   {int, float})
    .define("fin", "profit",  {int, float})
    .define("fin", "revenue", {int, float})
    .define("fin", "margin",  {int, float})
    .relate(SumRelation(["costs", "profit"], "revenue"))
    .relate(RatioRelation("profit", "revenue", "margin"))
)

# Create the kernel
k = TemporalKernel(
    lattice=lattice,
    invariants=[ValueMustBePositive("revenue")]
)

# Apply events — the kernel infers the rest
k.apply(Event({"costs": 60.0, "profit": 40.0}, domain="fin"))

print(k.state["revenue"])  # 100.0  — inferred
print(k.state["margin"])   # 0.4    — inferred

# Audit any value back to its origin
print(k.explain("revenue"))
# 'revenue' = 100.0 — inferred via [revenue = sum(['costs', 'profit'])] from ['profit', 'costs']

# Full derivation chain
for line in k.explain_chain("margin"):
    print(line)
# 'margin' = 0.4 — inferred via [margin = profit / revenue] from ['profit', 'revenue']
#   ← 'profit' = 40.0 — set by event abc12345
#   ← 'revenue' = 100.0 — inferred via [revenue = sum(...)] from ['profit', 'costs']
#       ← 'costs' = 60.0 — set by event abc12345
```

---

## Architecture

Alexandria is structured around five core abstractions:

### Event
An immutable record with a unique ID, timestamp, domain label, payload, and cryptographic hash. Once created, an event cannot be altered. The hash is verified on load — a corrupted ledger is detected immediately.

### Ledger
An append-only ordered sequence of events. The ledger is the source of truth. State is not.

### Lattice
The coordinate grid — the shape of what *could* exist. You define positions and relations before filling them. The lattice is the periodic table; events are the elements discovered to fill it.

### Relations
Typed edges between lattice positions. The field equations of the system. When some positions are known, relations infer the rest.

| Type | Description |
|------|-------------|
| `SumRelation` | `total = sum(parts)` — bidirectional |
| `RatioRelation` | `ratio = a / b` — bidirectional |
| `EqualityRelation` | `a = b` — bidirectional |
| `BoundedRelation` | `lo ≤ value ≤ hi` |
| `FunctionRelation` | `output = f(*inputs)` |
| `EnumRelation` | value must be in allowed set |
| `CategoricalImplicationRelation` | if A = x, then B = y |
| `NegationRelation` | `a = ¬b` |
| `ExactlyOneRelation` | exactly one boolean key is True |
| `ConditionalRelation` | apply inner relation if predicate holds |
| `TemporalRelation` | constrain change between timesteps |

### Invariants
Conservation laws. They halt progression on violation. They do not decide correctness — they enforce admissibility.

```python
from alexandria.invariants import (
    KeyMustExist,
    ValueMustBePositive,
    ValueNeverDecreases,
    DomainSumConserved,
    RelationInvariant,
)
```

---

## Constraint Propagation

The solver is a two-phase engine:

**Phase 1 — Arc consistency:** Iterative forward-chaining. Each pass applies all relations. Restarts on any new inference. Terminates at fixed point. Handles exact algebraic inference.

**Phase 2 — Energy minimization:** After arc-consistency, computes residual energy `E = Σ(residual²)` and runs gradient descent over free numeric variables to find the lowest-energy fixed point.

This means the system finds not just *a* consistent state, but the one of *minimum tension*.

---

## Trust Domains

Domains are orthogonal authority axes, not a hierarchy. A domain can only write keys it owns. Events carry a domain label. Cross-domain conflicts are resolved by explicit policy, never by implicit precedence.

```python
from alexandria import TrustDomain

finance = TrustDomain("finance", owns={"balance", "revenue", "costs"})
ops     = TrustDomain("ops",     owns={"status", "region"})

k = TemporalKernel(domains={"finance": finance, "ops": ops})
k.apply(Event({"balance": 1000.0}, domain="finance"))  # ok
k.apply(Event({"balance": 500.0},  domain="ops"))       # DomainViolation
```

---

## Conflict Resolution

When reconciling divergent branches, policies resolve conflicts deterministically:

```python
from alexandria.policies import PolicyChain, DomainAuthorityWins, LastWriteWins

policy = PolicyChain(
    DomainAuthorityWins({"balance": "finance"}),
    LastWriteWins(),
)

k = TemporalKernel(policy=policy)
report = k.reconcile(other_kernel)

if report.successful:
    k.apply(Event(report.merged, domain="reconciler"))
```

Available policies: `LastWriteWins`, `DomainAuthorityWins`, `ConservativeWins`, `MergeFunction`, `OperatorPrompt`, `PolicyChain`.

`ConservativeWins` is particularly powerful — it derives the safe direction (min/max) automatically from your declared invariants, so you don't have to specify it manually.

---

## Named Inference Rules

Rules give relations an identity. Every inferred value traces back to a named proposition, not just an anonymous equation.

```python
from alexandria.rules import RuleSet
from alexandria.relations import SumRelation, RatioRelation

ruleset = (
    RuleSet("financial")
    .rule("revenue",  SumRelation(["costs", "profit"], "revenue"),
          "Revenue equals costs plus profit")
    .rule("margin",   RatioRelation("profit", "revenue", "margin"),
          "Margin is profit over revenue")
)

ruleset.attach_to(lattice)
```

---

## Temporal Constraints

Constrain how values change between events — automatically, without boilerplate:

```python
from alexandria.relations import TemporalRelation
from alexandria.invariants import RelationInvariant

# Price may not move more than 10 per event
k = TemporalKernel(invariants=[
    RelationInvariant(TemporalRelation("price", max_delta=10.0))
])

k.apply(Event({"price": 100.0}))
k.apply(Event({"price": 108.0}))  # ok — delta = 8
k.apply(Event({"price": 200.0}))  # InvariantViolation — delta = 92
```

The kernel automatically injects `_prev_price` before each check — no caller boilerplate required.

---

## Schema Inference

Alexandria can observe a stream of events and propose the lattice structure from evidence:

```python
# What positions should the lattice have?
for proposal in k.infer_schema(min_occurrence=3):
    print(proposal.describe())

# What relations hold empirically in the data?
for proposal in k.infer_relations(min_cooccurrence=5, min_confidence=0.9):
    print(proposal.describe())
    print(proposal.constructor)  # copy-paste ready Python
```

Relations are only proposed if they hold on ≥ `min_confidence` fraction of co-observations — not just because keys co-occur.

---

## Temporal Queries

Query state at any point in history in O(log n):

```python
k.apply(Event({"price": 100.0}))
t1 = k.ledger[-1].ts
k.apply(Event({"price": 120.0}))

k.at(t1)["price"]   # 100.0 — state as it was then
k.state["price"]    # 120.0 — current state
```

---

## Persistence

```python
from alexandria.persistence import LedgerStore, GitLedger

# Simple JSON file
store = LedgerStore()
store.save(kernel, "ledger.json")
store.restore(kernel2, "ledger.json")

# Git as canonical substrate
gl = GitLedger("/path/to/repo").init()
gl.append(event)                              # each event is a commit
gl.append_equilibrium(kernel, "end-of-day")  # tagged snapshot
print(gl.log())                               # the git log IS the audit trail
```

---

## CLI

```bash
alexandria                      # version + doctrine banner
alexandria replay ledger.json   # replay and report state
alexandria report ledger.json   # full equilibrium report (JSON)
alexandria verify ledger.json   # verify all event hashes
alexandria schema ledger.json   # infer schema and relation proposals
```

---

## Equilibrium Report

A full human-legible snapshot of the system at any moment:

```python
report = k.equilibrium_report()
# Includes: state, provenance, provenance_chains, event_history,
#           tension, occupancy, solver_energy, domains_seen,
#           underdetermined_keys, dependency_cycles
```

Every value in the report has a provenance chain that walks back to the originating events.

---

## Design Principles

These are not preferences. They are the constitutional doctrine of the system.

1. **Linear Time is Doctrine.** History is singular. There are no alternate timelines.
2. **Holes Are First-Class.** The lattice exists independent of occupancy. Absence is meaningful.
3. **Invariants Are Conservation Laws.** The system enforces admissibility, not correctness.
4. **Domains Are Axes.** Orthogonal authority dimensions. No implicit cross-domain mutation.
5. **State Is Derived.** Replay is canonical reconstruction. State is never primary.

See `DOCTRINE.md`, `SPEC.md`, and `MANIFESTO.md` for the full constitutional record.

---

## What Alexandria Is Not

Explicitly out of scope, by design:

- Temporal branching or speculative replay
- Heuristic auto-correction
- Autonomous state mutation
- Implicit authority inference
- Non-deterministic replay

The absence of these capabilities is not a gap. It is a boundary.

---

## License

PolyForm