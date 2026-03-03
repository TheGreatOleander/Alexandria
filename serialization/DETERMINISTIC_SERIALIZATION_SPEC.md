# DETERMINISTIC_SERIALIZATION_SPEC.md

## Objective

Ensure replay produces identical state across all environments.

---

## Requirements

1. Canonical JSON serialization
   - Sorted keys
   - UTF-8 encoding
   - No trailing whitespace
   - Stable array ordering

2. Timestamp Policy
   - UTC only
   - ISO-8601 format
   - No local timezone usage

3. Float Precision Policy
   - Fixed decimal precision
   - Explicit rounding rules
   - No environment-dependent formatting

4. Randomness Policy
   - Seed-locked RNG
   - Seed recorded in event if used

5. Event Ordering
   - Strict ledger index ordering
   - No parallel commit ambiguity

6. Map Iteration
   - Explicit sorting before iteration

---

## Determinism Test

Replay(input_ledger) must produce byte-identical serialized state.

Failure = system halt.