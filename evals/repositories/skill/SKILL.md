---
name: loop-feedback
description: Run this project's configured native checks with compact results and retained logs. Use while changing or debugging code in this project.
---

# Native feedback

`.loop/feedback.json` records this project's native test commands. Run
`python3 .loop/feedback.py list` to discover them, or read that small file.
`python3 .loop/feedback.py focused` runs the relevant component checks;
`python3 .loop/feedback.py suite` runs the configured broader native suite.

The helper prints a JSON result and returns non-zero on failure, timeout or output
limit. Successful logs stay out of context. Failures include an excerpt and a local
log path; read that log when the excerpt is insufficient. Existing tests remain
the source of assertions. Fix production code rather than weakening checks.

A configured suite may cover only part of a larger repository. Honour the task's
scope and repository guidance; a passing component suite is not evidence that
browser, database, release or production checks passed.
