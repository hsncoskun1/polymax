---
name: architecture-governor
description: Enforce architectural boundaries and prevent scope creep in POLYMAX. Use this skill before implementing any feature, adding a new module, or making structural changes. Triggers on architecture decisions, new module proposals, scope questions, or when a change might violate project boundaries.
---

# Architecture Governor

Prevents unauthorized scope expansion and enforces module boundaries in POLYMAX.

## Before Any Implementation

Ask these questions:
1. Is this change in the approved scope for the current step?
2. Does it respect the launcher + localhost panel architecture?
3. Does it add a new dependency or abstraction? If yes, is it justified?
4. Does the backend remain the single data authority?

If any answer is "no" or uncertain, stop and report to the user before proceeding.

## Boundary Rules

- Backend is the single source of truth for all data
- Frontend displays data from backend; it never computes or stores authoritative state
- New modules require explicit user approval
- No technology additions without stated need
- No speculative abstractions or "future-proofing" code

## Scope Check Process

1. State what you're about to do
2. Identify which approved scope item it falls under
3. If it doesn't fall under any approved item, flag it
4. Wait for user confirmation before proceeding with anything outside scope

## When to Block

- Adding a new external dependency not discussed
- Creating a new service/module not in the plan
- Implementing features beyond the current step
- Adding abstraction layers for hypothetical future needs
