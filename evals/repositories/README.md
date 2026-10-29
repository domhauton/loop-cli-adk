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

## Measured repair trials

`agent.py` applies the same regression in a disposable snapshot and compares
`--condition natural` with `--condition skill`. Supply the same `--profile`,
`--source`, `--python` and a fresh `--output` as above. It makes real model calls
using the locally authenticated Codex CLI and consumes allowance. The skill arm
gets a prepared `.loop/feedback.json`, the shared bounded command runner and a
short skill. Test assertions remain in the repository's existing framework.

Both arms may repair only the affected production file. Grading reruns the native
checks independently and verifies that original tests/configuration stayed intact.
The helper implementation must remain unchanged. Raw transcripts and repaired
source stay local. Run `report.py RESULT... --output report.json` with three trials
per arm per repository; it refuses duplicate transcript evidence or mixed setups.

`../results/native-repair-v1.json` records 18 successful repairs: three per arm on
each of the three repositories. Trial order was natural/skill, skill/natural,
natural/skill. Separate repository streams ran concurrently.

| Repository | Natural median total tokens | Skill median total tokens |
| --- | ---: | ---: |
| Loop | 133,322 | 141,408 |
| Landing | 92,222 | 96,701 |
| PorscheConnect | 204,448 | 162,814 |

The skill was used in all nine skill trials. PorscheConnect showed about 20% fewer
median total tokens, while Loop and Landing increased by about 6% and 5%. Sums
across runs fell for all three, illustrating the influence of outliers. Uncached
input moves differently: PorscheConnect's median increased from 14,406 to 21,726.
These are token measurements, not monetary savings. Prepared command discovery,
log compression and skill guidance are bundled; their effects are not isolated.

This is one injected defect per repository, repeated three times. It does not
establish broad transfer, installation pay-off, or full production readiness.
The installed helper and dependency preparation are excluded from model timing;
preflight durations and parent engineering usage are recorded separately. Keep
this frontend experimental pending broader evidence.

### Batched feedback revision

`../results/native-repair-v2.json` contains a fresh 18-run comparison. The revised
helper accepts `focused suite` in one invocation, validates the whole selection
first and stops at the first failed check. Guidance makes discovery optional.
Invocation records confirm both checks ran in all nine skill trials; the grader
also verifies the supplied helper configuration is unchanged. All 18 repairs pass.

| Repository | Natural median total tokens | Skill median total tokens |
| --- | ---: | ---: |
| Loop | 145,891 | 122,792 |
| Landing | 91,876 | 96,896 |
| PorscheConnect | 178,327 | 117,197 |

The same-run comparison shows about 16% fewer median total tokens for Loop and
34% fewer for PorscheConnect; Landing is about 5% higher. Median uncached input
increases for Loop (15,609 to 18,540) and Landing (10,231 to 14,302), but decreases
for PorscheConnect (17,933 to 12,504). Monetary savings are not inferred. The old
and new harnesses are not pooled, and the changes bundle guidance and batching,
so this is not an isolated causal estimate for either change.

The result supports an optional prepared native workflow, particularly for verbose
failure output, but installation/configuration pay-off and broader defect coverage
remain unproven. The current frontend still lives only in evaluation tooling.

### Configuration-inclusive adoption experiment

Pass `--discover-checks` to both arms for a separate comparison. The skill arm
receives the reusable runner and schema guidance, but no command configuration.
The agent discovers existing native commands and creates `.loop/feedback.json`
within its measured task. Natural tooling remains unconstrained. Both arms use
the same prepared dependencies and repair task.

The grader preserves original tests and configuration, reruns independent native
checks, and verifies each authored helper command with a pass/fail/pass sequence:
repaired source, the known regression, then restored repaired source. Regression
failures must include the expected native assertion marker. No-op commands and
always-failing commands are rejected by executable grader regressions. Grader
invocations are excluded from the agent's helper-adoption audit.

This measures command configuration plus one repair, not helper installation or
longitudinal maintenance pay-off. Do not pool it with prepared-command trials.

`../results/native-adoption-v1.json` records three fresh trials per arm per repo.
All 18 production repairs passed independent native tests, but one PorscheConnect
skill configuration failed its repaired/restored focused checks. The overall
comparison therefore has 17 passing trials, and PorscheConnect's cost ratio is
invalid rather than a saving.

| Repository | Natural median total tokens | Skill median total tokens | Skill acceptance |
| --- | ---: | ---: | ---: |
| Loop | 124,609 | 127,828 | 3/3 |
| Landing | 92,440 | 94,298 | 3/3 |
| PorscheConnect | 171,181 | 242,863 | 2/3 |

Loop and Landing median totals increased about 3% and 2%, respectively. Landing's
sum decreased about 4%; small samples and different summary statistics must not
be presented as a robust win. Median uncached input was 20,145/21,860 for Loop,
12,280/9,034 for Landing, and 20,351/26,267 for PorscheConnect (natural/skill).
These remain token counts, not monetary costs.

All three Porsche skill agents initially ran focused tests with the project's
whole-suite coverage threshold. Two repaired their command selection; one left
an unusable focused command despite a passing full suite. This explains observed
extra feedback iterations, but is not a causal estimate of their token cost.
Configuration discovery needs to distinguish component feedback from aggregate
quality gates, preserve the full-suite gate, and validate the authored command on
repaired code. The prepared-command comparison excluded precisely this work.

The runner remains experimental. Installation is still excluded, and no retained
workspace maintenance sequence has yet established native-helper break-even.

### Retained-workspace maintenance

`lifecycle.py` accepts the same profile/source/condition/output/interpreter options
as `agent.py`. Each sequence has three distinct defects in the same component.
The skill arm discovers its command configuration in the first task. Both arms
retain repaired source and any new helper scripts or notes between tasks, while
each task starts a fresh model session. Existing tests, dependencies and original
configuration remain protected. Each authored command is revalidated against the
current regression, so a test selection that only covers the first defect cannot
silently pass later tasks.

Use `--preflight-only` to validate all mutations and restored native suites without
model calls. `../results/native-maintenance-preflight-v1.json` records the nine
successful deterministic mutation/restoration cycles. A missing mutation anchor
or failed preflight stops a sequence and remains a failure; the harness never
resets candidate code to force later tasks to work.

For measured trials, run three sequences per arm per repository, alternating order,
then use `python3 -m evals.repositories.lifecycle_report RESULT... --output REPORT`.
The report includes cumulative setup-plus-repair usage by stage. Missing stages,
unknown usage or any failed sequence invalidate cost ratios and crossover claims.
A sustained observed crossover means the cumulative skill median stays below the
natural median through every remaining measured stage; it does not extrapolate
beyond three tasks or prove a general saving.

The generic skill now distinguishes component feedback from whole-project quality
gates and requires both configured commands to pass on repaired code. This change
belongs to the new experiment; the previous adoption report is not retroactively
regraded or pooled with it. Helper installation and dependency preparation remain
outside model timing. These are component repairs, not full application releases.
