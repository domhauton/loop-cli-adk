# Native repository feedback

This harness validates the feedback cycle against existing repositories and their
native tests. Repository profiles own pinned revisions, prerequisites, commands
and one meaningful behavioural mutation. The shared runner owns snapshots,
time/output limits, restoration and reporting. It does not add an HTTP server,
replace native test frameworks or deploy anything.

```sh
python3 evals/repositories/run.py --profile loop-definition --source . --output /tmp/loop-self-eval
python3 evals/repositories/run.py --profile landing-counters --source /path/to/landing --output /tmp/landing-eval
python3 evals/repositories/run.py --profile porsche-timestamp --source /path/to/ha-porscheconnect --python /path/to/prepared/venv/bin/python --output /tmp/porsche-eval
```

Each output directory must be new. The source checkout must contain the pinned
commit; uncommitted changes are excluded and the checkout is never edited.
Python 3.12+ runs the harness. Go is required for Loop. Landing needs Node/npm and
its pinned Rust/WASM toolchain; the profile runs `npm ci` and `npm run build`.
PorscheConnect uses an interpreter with that commit's `requirements_test.txt`
installed. Existing prepared environments can be reused; the harness does not
modify them. Dependency installation/build time is recorded separately.

The sequence is prerequisite setup, focused baseline, injected regression,
restored focused test and native language suite. A timeout, missing executable,
excessive output or unrelated error cannot count as a caught regression. Raw logs
stay local. Public reports contain outcomes, sizes, durations and exact revisions.
`model_tokens: null` means no model ran; it is not a zero-cost development claim.

Profiles:

- Loop: unknown manifest fields must be rejected; full `go test ./...` afterwards.
- Landing: counters must stop at confirmed totals; build its WASM dependency, then
  run the complete Node suite. This is not the full `make check` gate: browser,
  Go/PostgreSQL integration, Rust tests and deployment validation are separate.
- PorscheConnect: the vehicle timestamp sensor must expose actual report time.
  Focused sensor tests use `--no-cov`; the complete pytest suite retains the
  repository's 80% coverage requirement. Fixtures mock Porsche account operations.

The Porsche profile pins the user's PR head, not the moving upstream branch:
https://github.com/CJNE/ha-porscheconnect/pull/422
No sensor naming, visibility, translations or PR comments are changed by this eval.

These checks establish harness portability and test sensitivity. Measuring whether
agents spend fewer tokens on repairs needs a separate model experiment on these
snapshots, with the same task and independent acceptance criteria in both arms.
