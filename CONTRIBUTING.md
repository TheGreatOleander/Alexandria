# Contributing to Alexandria

Thank you for your interest. Alexandria is a carefully bounded system —
contributions are welcome, but the philosophical foundation is not negotiable.

Before you write a single line of code, read:

- [`DOCTRINE.md`](DOCTRINE.md) — the constitutional principles
- [`SPEC.md`](docs/SPEC.md) — the governing law
- [`NON_GOALS.md`](NON_GOALS.md) — what Alexandria explicitly refuses to become

If your contribution conflicts with any of those documents, it will not be merged —
not because of taste, but because the system's integrity depends on those boundaries.

---

## What Good Contributions Look Like

**Additions that are welcome:**
- New `Relation` subclasses that express algebraic or logical constraints
- New `Invariant` subclasses that enforce admissibility conditions
- New `ConflictPolicy` subclasses for deterministic reconciliation
- Performance improvements to the solver or temporal index
- Improvements to provenance legibility
- Documentation, examples, and test coverage
- Bug fixes that preserve existing behavior

**Additions that require philosophical justification:**
- Any change to the `apply()` / `replay()` pipeline
- Any change to how provenance is recorded
- Any new concept that doesn't map to an existing abstraction

**Additions that will not be accepted:**
- Branching or speculative replay
- Non-deterministic behavior of any kind
- Implicit state mutation
- Features that hide uncertainty or rewrite history
- Anything that makes the system decide rather than record

---

## Process

1. **Open an issue first.** Describe what you want to add and why it is
   consistent with the doctrine. This saves everyone time.

2. **Fork and branch.** Work on a feature branch, not `main`.

3. **Write tests.** All new behavior must be covered. The test suite is
   in `tests/test_kernel.py`. Follow the existing pattern — test the
   invariant, not just the happy path.

4. **Check replay determinism.** If your change touches state, verify
   that `replay()` produces an identical `snapshot_hash()` before and after.

5. **Update the changelog.** Add an entry under a new version heading
   in `CHANGELOG.md`.

6. **Open a pull request.** Reference the issue. Explain how the change
   preserves the five constitutional principles from `DOCTRINE.md`.

---

## Running the Tests

```bash
pip install -e ".[dev]"
pytest tests/
```

---

## Code Style

- Python 3.9+ compatible
- Type hints on all public methods
- Docstrings on all public classes and functions
- No external dependencies beyond the standard library

---

## Questions

Open an issue or email: **TheGreatOleander@gmail.com**

---

*Alexandria is a canonicalization system, not a feature platform.
The strength of the system is its structural integrity, not its breadth.*
