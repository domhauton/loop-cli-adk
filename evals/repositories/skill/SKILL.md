---
name: loop-feedback
description: Run this project's configured native checks with compact results and retained logs. Use while changing or debugging code in this project.
---

# Native feedback

Use `python3 .loop/feedback.py focused` for component feedback while iterating.
When ready, `python3 .loop/feedback.py focused suite` runs both configured checks
in one invocation and stops at the first failure. Already-passing focused checks
need not be repeated before running `suite` alone.

The commands are configured in `.loop/feedback.json`. Read it or run `list` when
you need to inspect their scope; discovery is not a prerequisite to execution.

The helper prints a JSON result and returns non-zero on failure, timeout or output
limit. Successful logs stay out of context. Failures include an excerpt and a local
log path; read that log when the excerpt is insufficient. Existing tests remain
the source of assertions. Fix production code rather than weakening checks.

A configured suite may cover only part of a larger repository. Honour the task's
scope and repository guidance; a passing component suite is not evidence that
browser, database, release or production checks passed.
