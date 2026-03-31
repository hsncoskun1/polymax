---
name: git-release-discipline
description: Enforce disciplined git workflow with small commits, mandatory testing before commit, and push verification. Use this skill when committing code, preparing releases, or managing git operations in POLYMAX. Triggers on "commit", "push", "release", or any git workflow step.
---

# Git Release Discipline

Small commits. Test first. Push when possible.

## Commit Rules

1. Tests must pass before committing
2. Each commit covers one logical change
3. Commit messages are concise and descriptive
4. Format: `type(scope): description` (e.g., `feat(launcher): add process manager`)

## Commit Process

1. Verify tests passed (check test-and-report output)
2. Stage only relevant files (no `git add -A`)
3. Write a clear commit message
4. Commit
5. Attempt push

## Push Protocol

1. Try `git push`
2. If it fails:
   - Record the error
   - Report the reason to the user (no remote, auth issue, conflict, etc.)
   - Do not force push
3. Include push status in the report

## Report Format

```
## Git Status
- Commit: [hash] [message]
- Files: [count] changed
- Push: SUCCESS / FAILED (reason)
```

## Never Do

- Commit without passing tests
- Force push
- Skip hooks with --no-verify
- Amend published commits
- Stage sensitive files (.env, credentials)
