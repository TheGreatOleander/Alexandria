# PURPOSE.md
## Why Alexandria Exists

Most software systems treat state as primary. They store what *is*,
and discard what *was*. When something goes wrong, the past is gone.
When two systems disagree, there is no ground truth to appeal to.
When a value appears in the system, there is often no way to know why.

Alexandria inverts this.

**History is primary. State is derived.**

Alexandria does not store state. It stores events — immutable records
of what happened, when, and under what authority. State is reconstructed
by replaying those events from the beginning. If you delete the state
and replay the ledger, you get identical state back. Always. Without exception.

This has three consequences that matter:

### 1. Every value is explainable

Because state is derived from events through a chain of relations and
inferences, every value in the system has a complete provenance record.
You can ask "why does `revenue` equal 100?" and get a full derivation
chain back to the originating events. Nothing is implicit. Nothing is magic.

### 2. Disagreement is resolvable

When two branches of a system diverge, Alexandria can analyze the
divergence, identify the exact conflicts, and apply a deterministic
policy to resolve them — or report clearly that resolution is impossible
without operator intervention. Forks are preserved and visible, not
silently collapsed.

### 3. The system cannot lie about the past

The ledger is append-only. Events carry cryptographic hashes that are
verified on load. A corrupted ledger is detected immediately. There is
no mechanism to rewrite history — not accidentally, not deliberately.

---

## What Kind of System Needs This

Alexandria is appropriate when:

- **Auditability is non-negotiable.** Financial systems, medical records,
  legal documents — anywhere that "why does this value exist?" must have
  a complete, verifiable answer.

- **Deterministic replay is required.** Anywhere that two independent
  observers must be able to reconstruct identical state from the same
  event history.

- **Domain authority matters.** Anywhere that different parts of a system
  have different write authorities, and cross-domain conflicts must be
  resolved by explicit policy rather than implicit precedence.

- **Constraints are first-class.** Anywhere that the relationships between
  values are as important as the values themselves — and violations must
  halt progression, not be silently ignored.

---

## What Alexandria Is Not For

Alexandria is not appropriate when:

- You need speculative or branching computation
- You need non-deterministic or probabilistic behavior
- You need a general-purpose database or cache
- You need the system to make decisions autonomously

The absence of these capabilities is intentional.
Alexandria is strong precisely because of what it refuses to do.

---

*"The power of the system is not in what it contains,*
*but in what it refuses to become."*

— MANIFESTO.md
