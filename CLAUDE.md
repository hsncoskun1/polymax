# POLYMAX

> **Repo governance rules** — branch naming, commit discipline, document placement,
> source-of-truth map — are authoritative in `docs/governance/`.
> This file covers Claude-specific operational context only.

## Project Rules

- POLYMAX runs locally (launcher + localhost panel architecture)
- Backend is the single data authority; frontend only displays
- Only approved small steps are implemented
- No large-scope additions without explicit user approval
- Every change requires test + report before it's considered complete
- No unnecessary technologies, dependencies, or abstractions
- Large features progress in versioned steps with user approval at each step
- Scope is never self-expanded; if unsure, ask

## Skill Usage Policy

- Use existing installed skills first
- If a new skill seems needed, propose it to the user before adding
- No skill is added without clear justification
- A skill must solve a recurring, concrete problem in this project to be installed
- Installed skills: code-reviewer, browser-use, excalidraw-diagram, frontend-design
- Custom skills: architecture-governor, implementation-runner, test-and-report, git-release-discipline
- Conditional (not installed): request-history — install only if recurring need is confirmed

## Architecture

```
POLYMAX/
├── backend/     # Single source of truth for all data
├── frontend/    # Display only, no authoritative state
├── launcher/    # Application entry point
├── docs/        # Governance, releases, testing contracts
└── test-results/  # Test execution output
```

## Workflow

1. User approves a step
2. architecture-governor checks scope
3. implementation-runner executes the step
4. test-and-report verifies and records results
5. git-release-discipline commits and pushes
