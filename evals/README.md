# Evaluating the feedback loop

There are two independent questions: does the CLI preserve the project's actual
API behaviour, and does its development skill help an agent finish correct work
for fewer tokens? Passing the first does not answer the second.

## Energy integration

```sh
python3 evals/energy/run.py --automations /path/to/automations
```

Requires Python 3.12+, Git and Go. The script archives a pinned commit from an
existing authorised checkout, adds a test overlay in a temporary directory and
builds a native CLI from `examples/energy/project.json`. It never edits that
checkout, starts Energy's scheduler, connects to Home Assistant or reads production
endpoint configuration. Synthetic SOC values exercise the actual status and
dashboard handlers. Tests cover API prefixes, bearer auth, credential-free
discovery, invalid input and absence of service calls. Handler auth is supplied by
a fixture wrapper; this does not validate production ingress authentication.

The default source revision is recorded in `energy/run.py`; `--revision` deliberately
selects another committed revision. Uncommitted work is excluded. Energy is private,
so ordinary public CI does not clone it or require access credentials. No source or
real telemetry is embedded in this repository. Go may download source dependencies.

`model_tokens: null` means this deterministic integration makes no model calls;
it is not a measurement of the tokens spent building Loop.

## Agent trials

These commands make real model calls using the locally authenticated Codex CLI and
consume allowance. They are deliberately absent from normal CI.

```sh
python3 evals/agent.py --condition baseline --output evals/results/local/baseline-1
python3 evals/agent.py --condition skill --output evals/results/local/skill-1
```

Both conditions start from the same generated project, shared runtime, prompt and
short project guidance. The skill condition additionally gets the current generated
development skill. This comparison isolates the skill's incremental benefit within
Loop; it does not compare Loop against a CLI written from scratch. A temporary Go
module replacement uses the SDK under evaluation. Model runs ignore user config,
use the workspace-write sandbox with networking enabled for local HTTP fixtures,
no approval prompts and a five-minute timeout. Network access is not restricted
to loopback by the harness; the task instructions restrict use to local fixtures.
The task forbids external services and changes outside the workspace. This is not
a hostile-code sandbox or proof that every model followed those instructions.
Trials select `gpt-6.1-sol` with low reasoning by default (`--model` overrides the
model), and warm a workspace-local Go build cache before measurement. Earlier
setup pilots used the CLI default and are explicitly excluded from comparisons.

The task adds a billing operation and its tests. An independent grader builds the
result and checks path, encoded query, base prefix, auth, JSON result, local input
rejection and safe upstream errors. Candidate tests must pass before mutations
count: changing the path, query mapping or required flag must make them fail.
This assesses whether the agent's tests would catch future integration mistakes.
Hidden grading checks remain in this repository, outside the candidate workspace.

Transcripts and generated artefacts remain in the requested output directory,
ignored by Git under `evals/results/local`. Review them before sharing. Persist only
sanitised aggregate results in the repository. Timeout/failed runs count as failures;
missing token accounting is unknown, never zero. Do not quietly drop bad trials.

## Metrics and decisions

`usage.py` reads actual `turn.completed.usage` events. Input tokens include cached
input; cached input is a subset, not an extra charge. Output includes reasoning
where reported. The report keeps these fields separate and does not invent dollar
cost or convert subscription percentages into tokens. Incomplete/failed streams
are labelled. Command failures are feedback iterations, not necessarily defects.
The source is [Codex non-interactive mode](https://learn.chatgpt.com/docs/non-interactive-mode).

Before claiming a benefit, run at least three paired trials, alternate order, keep
the same model/toolchain and report every trial. Report task pass rate first, then
input/cached/output tokens, elapsed time and failed commands. A cheaper failure is
not an improvement. Small pilots identify defects; they do not prove generality.
Do not tune the skill against grading-only details or repeatedly rerun until it wins.

Next evaluation cases should cover repairing an API mapping, adding a new project,
and updating the SDK. Measure setup and migration cost as well as steady-state
maintenance. Amortisation is setup tokens divided by the measured per-task saving;
if the saving is absent or uncertain, report no demonstrated break-even. The current
repository's historical creation cost has not been measured by this harness.

## Initial evidence

`results/development-v1.json` records three paired Sol trials, in the order baseline,
skill, skill, baseline, baseline, skill. Both conditions passed 3/3 tasks and all
mutation checks. The skill reduced median total input (201,373 to 153,301), but
increased median uncached input (10,849 to 14,761) and output (2,311 to 2,650).
It has not demonstrated a cost reduction. Cache behaviour and a small sample limit
interpretation; one task does not establish transfer to other development work.
`results/setup-pilots.json` retains the earlier setup failures and exclusions.

Use `python3 evals/report.py path/to/result.json ...` to aggregate compatible runs.
It refuses differing models, prompts, harnesses or source revisions, keeps failures
in the totals and marks unknown usage. Existing reports describe their recorded
revision, not whatever happens to be checked out today.

## CI during development

Every ordinary CI run executes the deterministic evaluation tests on all six native
targets. The separate `Agent development evals` workflow is manually dispatched
with complete baseline/candidate commit SHAs and an API model available to the
publisher's OpenAI project. It runs three tasks per revision, using the same prompt
and grader from the workflow revision. The candidate SHA defaults to the workflow
commit. Both arms get their generated project and guidance, so this compares kit
revisions rather than skill presence alone.

Configure the repository's `OPENAI_API_KEY` secret before dispatching. No key is
currently configured in this repository; paid CI execution is not yet verified.
The workflow uses a commit-pinned official Codex action, CLI 0.165.0 and low effort.
The action's proxy keeps the raw key out of the model process. No model key is
passed to the grading job, which builds and tests downloaded candidate artefacts
on a fresh runner. Only trusted maintainers can dispatch this workflow.

Actual usage comes from JSON events in the completed action job's log, not from
the model's self-reported answer. The comparison requires all six tasks to pass
and complete usage to be present, then checks the configured total-token ratio
(default 1.10). Input includes cached input once; uncached input and output are
also reported. Missing jobs, unknown usage and failed tasks cannot pass by appearing
cheap. The result is a small-sample regression signal, not a dollar-cost guarantee.
CI logs and candidate artefacts may contain generated source; retention for
candidate artefacts is seven days. No Energy source or production data is uploaded.

This workflow currently measures command-development tasks. It does not yet answer
CLI-versus-natural-workflow amortisation. That experiment must permit existing
tests, shell commands, temporary scripts and reusable helpers in the baseline,
preserve both workspaces across tasks, and count CLI setup and maintenance.

## CLI pay-off versus natural testing

```sh
python3 evals/lifecycle.py --condition natural --output evals/results/local/natural-1
python3 evals/lifecycle.py --condition loop --output evals/results/local/loop-1
python3 evals/lifecycle_report.py evals/results/local/natural-1/result.json evals/results/local/loop-1/result.json
```

This separate experiment preserves each workspace across four fresh agent sessions:
initial state verification, authentication checks, a breaking route change and
another state check. The baseline can choose any testing approach, retain scripts,
reuse tests or create helpers. The Loop arm additionally scaffolds and builds a
CLI in the first stage, then chooses how to use it. Installation of the Loop kit
is assumed; per-project setup is measured. Neither arm is forced to rewrite work.

Both leave a repeatable verification command. Independent replay requires it to
pass the normal local API and fail wrong-state and authentication-bypass variants.
The fixture is a synthetic Energy-style read API; the separate pinned Energy
integration tests actual handlers. This corpus measures API integration checking,
not all backend implementation or all possible CLI workflows.

`results/lifecycle-v1.json` records three paired sequences (24 successful stages).
The baseline naturally retained a Python verifier. Median cumulative input plus
output was 286,187 tokens for the natural workflow and 460,433 for Loop. No observed
break-even occurred within four tasks. Cached input is included once; uncached input
and output are reported separately. No future pay-off or monetary cost is inferred.
This is evidence against assuming that reuse alone makes a CLI cheaper: a capable
agent can also reuse a script. More complex workflows need their own evaluations.

One observed gap was a separate HTTP client in the Loop verifier to inspect a 401.
The runtime now exposes safe HTTP status details for machine consumers. That change
must be evaluated rather than assumed to improve the full workflow.

## Engineering cost accounting

`session_usage.py SESSION.jsonl --since TIMESTAMP` extracts only cumulative usage
counters from one explicitly selected Codex session. It rejects resets and missing
boundaries and never returns conversation text. `results/engineering-checkpoint.json`
records a parent-session checkpoint, including design, coding, research and eval
work. Its scope excludes architecture subagents and separate model trials. Cached
input and reasoning are already included in their respective totals. This is not
an estimate of dollars or tokens attributable solely to writing source code.

The lifecycle harness also accepts `--loop-mode runner` to measure the existing
manifest runner without a standalone build, and `--sdk PATH` to select the kit
checkout independently of the harness. New runs rotate the grading token and
mutate each required state field separately. Observed requests report the Loop
client marker; a tool-availability condition does not prove that an agent kept
using the tool. The first lightweight pilot eventually replaced its Loop call
with direct HTTP, so its later timings must not be presented as a Loop-use win.

## Verification boundary prototypes

`prototypes/loop_verify.py` supplies two experimental interfaces over the same
Loop invocation code: a native Python helper and a declarative check file. Neither
is a supported runtime API or a decision to require Python in shipped projects.
Both have identical JSON-subset and safe HTTP-error assertion semantics. Real
fixture mutation tests independently check these before model trials.

Use `lifecycle.py --condition loop --loop-mode runner --verification-mode native`
or `--verification-mode declarative`, plus `--output`. The model receives the
same helper and reference, adapts its own manifest/checks and may maintain them
across tasks. It must not modify supplied helper code. The natural baseline remains
unrestricted. Helper installation is assumed; prototype engineering cost is not
included in per-project setup cost. Compare a fresh natural arm from the same
harness revision; earlier reports are not interchangeable.

`results/manifest-runner-v2.json` preserves two diagnostic pairs before these
prototypes. Both Loop arms passed but eventually switched to direct HTTP. Their
later task cost cannot be attributed to continued use of Loop. The arms ran
concurrently, so elapsed times are descriptive rather than an isolated speed test.

### Prototype results

`results/verification-prototypes-v1.json` records three sequences per approach,
four stages each. All 36 stages passed independent grading. Both prototype arms
retained the unmodified shared helper and every replay request went through Loop.
They were explicitly instructed to retain their assigned interface; this does not
measure spontaneous adoption. The natural arm remained unrestricted.

| Median cumulative metric | Natural tooling | Native helper | Declarative checks |
| --- | ---: | ---: | ---: |
| Input + output tokens | 306,142 | 378,654 | 349,867 |
| Uncached input tokens | 33,052 | 42,272 | 38,802 |
| Output tokens | 2,466 | 2,329 | 1,899 |
| Shell commands | 14 | 21 | 19 |

Medians are computed separately, so component medians need not sum to the median
total. Reusable assertions reduced output tokens, especially declarative checks,
but extra discovery/integration turns outweighed that reduction in total tokens.
Neither approach demonstrated cumulative break-even within the four tasks. Total
tokens are not monetary cost; cached input remains separately reported. Concurrent
arms also limit interpretation of elapsed time and caching differences.

Keep both interfaces experimental. The result does not justify a new production
verification language, nor does one small read API establish that reusable tools
are generally inefficient. A next corpus should cover larger existing workflows
and maintenance that exercises shared capabilities before choosing a default.
