# GENERATOR_TRUST_MODEL.md

## Purpose

Define authority boundaries between event emitters and kernel validation.

---

## Generator Definition

A generator is any entity that emits events into Alexandria.

Examples:
- Humans
- AI models
- Automation systems
- APIs
- Multi-agent frameworks

Generators propose.
Kernel validates.
Ledger records.

---

## Generator Identity Schema

generator_id: string  
trust_level: enum  
allowed_domains: list  
mutation_scope: list  
signature_key: optional public key  

---

## Trust Levels

root   → Human sovereign authority  
high   → Deterministic symbolic engines  
medium → AI model systems  
low    → External unverified sources  

Trust level affects validation strictness, not invariants.

---

## Enforcement Rules

- Generators cannot mutate authoritative state directly.
- Events outside allowed_domains are rejected.
- Events outside mutation_scope are rejected.
- Invalid signatures (if required) are rejected.
- Invariants always override trust level.

---

## Auditability

All events must record:

generator_id  
timestamp (UTC)  
schema_version  

No anonymous generators permitted.