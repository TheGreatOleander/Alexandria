# Alexandria Temporal Kernel
## Foundational Specification — v1.0

---

## 1. Purpose

Alexandria is a temporal witnessing kernel.

Its sole purpose is to:
- preserve events over time,
- enable deterministic replay,
- and allow independent observers (human or machine) to inspect how state evolved.

Alexandria does not decide truth.
It preserves the conditions under which truth can be examined.

---

## 2. Core Definition

An Alexandria Kernel is a system that:

1. Accepts events
2. Orders them in time
3. Applies them deterministically
4. Produces reproducible state
5. Allows complete replay from first principles

If any of the above fail, the kernel is invalid.

---

## 3. Fundamental Objects

### 3.1 Event

An Event is an immutable record containing:
- a unique identifier
- a timestamp
- a domain identifier
- a payload
- a cryptographic hash of its contents

Once created, an Event MUST NOT be altered.

---

### 3.2 Ledger

The Ledger is an append-only, ordered collection of Events.

Rules:
- Events may be added
- Events may never be removed or modified
- Ordering is explicit and observable
- Gaps and forks are allowed and visible

A ledger that hides or rewrites history is non-compliant.

---

### 3.3 State

State is the deterministic result of replaying the ledger.

Rules:
- State has no authority outside replay
- State must be fully derivable from events
- No hidden or implicit state is permitted

State is an artifact, not a source of truth.

---

## 4. Determinism

Given:
- the same initial conditions
- the same ordered event ledger

Replay MUST produce:
- identical state
- identical state hash

Non-determinism is a fatal violation.

---

## 5. Replay

Replay is a first-class operation.

Rules:
- Replay must be complete or fail loudly
- Partial replay is invalid
- Silent divergence is forbidden

---

## 6. Invariants

An Invariant is a condition that must always hold true.

Rules:
- Invariants are explicit
- Invariants are inspectable
- Invariant failure halts progression

Alexandria enforces consistency, not correctness.

---

## 7. Trust Domains

A Trust Domain is a contextual boundary, not a hierarchy.

Rules:
- Domains do not override one another
- Events are always domain-labeled
- Cross-domain reconciliation is observational

Forks are preserved, not collapsed.

---

## 8. Non-Goals (Explicit Prohibitions)

Alexandria MUST NOT:
- decide outcomes
- rank humans or agents
- optimize behavior
- predict intent
- persuade
- enforce morality
- hide uncertainty

Any system that does so is not Alexandria.

---

## 9. Human Legibility

All Alexandria systems MUST allow:
- event inspection
- ledger traversal
- replay explanation
- divergence identification

If a human cannot understand why a state exists, the system is incomplete.

---

## 10. Failure Semantics

Failure is acceptable.
Silence is not.

Errors must be explicit.
Recovery must never rewrite history.

---

## 11. Extensibility

Extensions are permitted only if they:
- preserve invariants
- preserve replay
- preserve legibility
- add no hidden state

Power must live outside the kernel.

---

## 12. Closing Principle

Alexandria does not answer questions.
It preserves the conditions under which answers can be trusted.