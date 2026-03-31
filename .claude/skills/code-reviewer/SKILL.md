---
name: code-reviewer
description: Review code changes for bugs, security issues, performance problems, and style. Use this skill when the user asks for a code review, wants feedback on their changes, says "review this", "check my code", or asks about code quality. Also trigger when reviewing PRs or diffs.
---

# Code Reviewer

Review code for correctness, security, performance, and maintainability.

## Review Process

1. Read the changed files or diff
2. Check for:
   - Logic errors and edge cases
   - Security vulnerabilities (injection, XSS, auth issues)
   - Performance problems (N+1 queries, unnecessary allocations, blocking calls)
   - Error handling gaps
   - Naming clarity and code readability
3. Provide actionable feedback with specific line references

## Output Format

For each issue found:
- **File:Line** - severity (bug/security/perf/style)
- What the problem is
- Suggested fix

End with a summary: total issues by severity, overall assessment, and whether the code is safe to merge.

## Guidelines

- Focus on real problems, not nitpicks
- If the code is good, say so briefly
- Prioritize bugs and security over style
- Suggest fixes, don't just point out problems
- Consider the broader context of how the code fits into the project
