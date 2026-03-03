# SPIRAL_GENERATOR_INTEGRATION_SPEC.md

## Purpose

Define Spiral Code Flow as a generator within Alexandria.

---

## Architecture

Spiral → emits proposal events → Alexandria validates → ledger append

Spiral never mutates authoritative state.

---

## Spiral Responsibilities

- Emit deterministic proposal events
- Declare domain per event
- Respect mutation_scope
- Accept validation outcomes

---

## Kernel Responsibilities

- Enforce invariants
- Enforce domain constraints
- Validate generator trust level
- Record provenance

---

## Principle

Spiral improves.
Alexandria decides.