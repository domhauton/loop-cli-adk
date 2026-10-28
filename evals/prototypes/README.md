# Verification boundary experiments

These Python prototypes are evaluation artefacts, not a supported SDK or a decision
to add Python to Loop. Both reuse the installed Loop executable and the same
invocation/error-handling code. They have no direct HTTP client. Do not edit the
supplied helper during a trial; adapt your manifest and verification instead.

## Native tests

Import `Client` from `loop_verify`. `Client("project.json").expect_json(command,
expected)` checks a JSON object subset (nested objects allowed; arrays and scalar
types match exactly). `command` is an argv list such as `["items", "list"]`.
`expect_http_status(command, status, invalid_token=True)` supplies a deliberately
invalid credential and checks the adapter's structured status error. These methods
raise a safe exception on failure. Use them in a normal Python script or test suite;
ordinary code owns control flow and any additional domain assertions.

## Declarative checks

Run `python3 loop_verify.py checks.json`. The file has a `manifest` path and a
non-empty `checks` array. Each check contains `command` (argv array) and either
`json_subset` (expected JSON), or `http_status` (integer) plus `invalid_token: true`.
All checks must pass. This prototype has no expressions, loops, fixtures or writes.

The environment supplies `LOOP_EXECUTABLE`, plus the URL/token variables referenced
by the manifest. Neither interface prints responses, credentials or error bodies.
The model must still create/adapt its project manifest and checks. Installation of
the reusable helper is assumed equally in both experimental arms; its engineering
cost is not included in per-project token counts.
