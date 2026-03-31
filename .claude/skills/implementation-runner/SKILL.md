---
name: implementation-runner
description: Execute approved implementation steps in a controlled, minimal way. Use this skill when writing or modifying code for POLYMAX features. Ensures changes are small, intentional, and free of unnecessary complexity. Triggers on any code implementation task, feature building, or file modification.
---

# Implementation Runner

Executes only the approved step, nothing more.

## Before Writing Code

1. Confirm the step is approved by the user
2. Identify exactly which files will change
3. State any assumptions explicitly

## Implementation Rules

- One approved step at a time
- No helper utilities for one-time operations
- No abstraction layers unless reuse is proven (3+ call sites)
- No feature flags or backwards-compat shims
- No speculative error handling for impossible scenarios
- If you're making an assumption, write it down before proceeding

## File Change Discipline

- Edit existing files; don't create new ones unless necessary
- Keep changes minimal and focused
- Don't refactor surrounding code while implementing a feature
- Don't add comments, docstrings, or type annotations to unchanged code

## Output

After each implementation:
- List files changed and what changed in each
- State any assumptions made
- Flag anything that needs user decision
- Hand off to test-and-report skill
