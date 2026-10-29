# Next session: Loop CLI ADK

Prepared 29 October 2026. This is a handoff, not an instruction to restart paid work
without checking the user's allowance and resumed intent.

## Start here

Use this checkout explicitly:

`/Users/domhauton/Documents/github.com/domhauton/loop-cli-adk`

Branch: `main`. Work through `9640029f84d2788cb24874dc9e4bd648bb235b55` is committed
and pushed; the tree was clean when this note was prepared. The app's current
working directory may instead be the stale detached evaluation checkout:

`/Users/domhauton/.codex/worktrees/eval-helper-sdk/loop-cli-adk` at `8cce793`.

Do not develop there accidentally. The app regarded that checkout as primary and
refused archival; leave it alone. Temporary guidance-comparison worktrees were
removed. No model trials or subagents remain running.

Read root `AGENTS.md`, `docs/architecture.md`, `docs/decisions.md`, then the nearest
module guidance. The user's engineering guide is:
https://github.com/domhauton/agent-guide/blob/main/skills/dom-code/SKILL.md

The goal is **paused** because account usage reached **99% used / 1% remaining**.
The user first stopped at 10% remaining, then explicitly extended to 1%. Do not
consume reset credits or silently restart model experiments. Check current limits
and the user's resumed scope. This handoff request did not resume the goal or
schedule an automatic run tomorrow.

## What the user wants

A Go CLI developer kit that makes agent-facing project CLIs inexpensive to create,
test, maintain and distribute on Linux/macOS/Windows, amd64/arm64. Prefer small
manifests, reusable mechanics and skills over generated boilerplate. Keep modules
independently understandable; the project itself is developed with AI.

Discover existing organisation publishing repos and local registry configuration
before asking nontechnical users to invent infrastructure. Reuse suitable existing
infrastructure; offer templated publishing repos when absent. Credential presence
is not permission to publish. Provisioning remains unimplemented.

Measure actual agent feedback-loop/token efficiency. The natural baseline is
whatever the model chooses, including existing tests and retained scripts; never
force script regeneration. Include setup and maintenance, retain failed attempts,
and keep cached input, uncached input and output separate. No token-to-credit or
money conversion is established. Consult a quorum of agents when new ideas are
needed; give concise briefs rather than copying the whole conversation.

## Current delivered behaviour

- Manifest-defined HTTP GET commands with string inputs, discovery, safe structured
  errors, bounded JSON, lazy environment credentials and standalone builds.
- `loop init` defaults to a project CLI with shared `pkg/clitest` fixtures, skills,
  tests, six-target native CI and a release workflow.
- `--mode manifest` creates only a manifest, inspection skill and metadata.
- **New:** `loop init --mode testing --name myproject --dir .` creates exactly
  `.agents/skills/myproject-native-test/SKILL.md`. No API manifest, SDK, Python
  runner, command configuration, root guidance or workflow is introduced. Existing
  files are preserved and conflicts/symlink parents rejected. Installed skill use
  needs only the host project's native test tools. Template version is now 5.
- No public binary release is published yet. Build with Go as described in README.
  Packaging/provisioning, additional protocols and custom handlers remain future
  work. Do not confuse tested release machinery with a published release.
- The compact Python native runner and declarative verification alternatives are
  still experimental under `evals/`; they are not installed by testing mode.

The latest native runner fix kills child processes on interruption as well as
on timeout. Go runtime boundaries did not change for testing mode: authoring owns
templates, and runtime packages import neither authoring nor evals.

## Verification status to recheck

- `go vet ./...` and `go test ./...` passed; generated testing skill passed the
  skill-creator validator. The Python suite passed **46 tests** before the final
  standalone component-switch script was added; that script was then exercised
  successfully against the real pinned test suite.
- Feature commit `2e25c0c` passed all six native targets and race:
  https://github.com/domhauton/loop-cli-adk/actions/runs/40797984132
- Installation-eval commit `780a27b` CI was still running at handoff:
  https://github.com/domhauton/loop-cli-adk/actions/runs/40798480945
- Component-switch commit `9640029` CI was still running at handoff:
  https://github.com/domhauton/loop-cli-adk/actions/runs/40798803599
- Check live CI, including the handoff commit, before claiming latest main is green.
  Cross-compilation alone is not execution evidence.

Ordinary CI has deterministic tests only. Manual model-eval CI exists, but no
`OPENAI_API_KEY` repo secret was available and paid action execution remains
unverified. Local model experiments used the authenticated Codex CLI. Never copy
subscription credentials into CI.

## Evidence worth reading

Start with the evidence index in `evals/README.md`, then only the relevant report.

- `manifest-example-heldout-v1.json`: six audit-events CLI-development trials passed.
  Generic manifest guidance reduced median total tokens 222,180 → 114,129 and output
  2,153 → 1,667, but uncached input increased 10,571 → 15,615. Runtime and shared
  helper were identical across revisions. This supports precise examples, not a
  monetary or allowance saving.
- `native-maintenance-v1.json`: three retained-workspace repairs per sequence.
  PorscheConnect passed all six sequences; median cumulative total tokens fell
  571,083 → 478,050 (~16%), including command configuration. Uncached input and
  output also fell. Loop and Landing each suffered a model-capacity failure with
  unknown usage, so their cumulative comparisons are invalid. Do not discard or
  replace those failures to manufacture a win.
- `native-adoption-v1.json`: one Porsche configuration inherited whole-project
  coverage requirements for focused tests and stayed unusable despite a correct
  repair. Pass/fail/pass grading caught it. This motivated coverage-scope guidance.
- `verification-prototypes-v1.json`: native API assertions and declarative checks
  did not repay setup over four tasks versus retained natural scripts. This is
  distinct from the native-test wrapper comparison.
- `energy-integration-v2.json`: deterministic actual Energy handlers, synthetic
  state, no live services. No model-token claim.
- `native-skill-installation-v1.json`: delivered testing-mode binary installed into
  pinned Loop, Landing and PorscheConnect snapshots with empty PATH, preserving
  original content, links and permissions. Repeat installation safely failed.
- `component-switch-preflight-v1.json`: the old Porsche sensor check passes while
  a configuration-flow regression exists; the relevant config tests detect it.
  Both components' mutation/restoration cycles and full native suites passed.

Reports live in `evals/results/`. Raw transcripts and external source stay local
under `/tmp/loop-*`; they are not committed. Some may disappear after reboot.
`engineering-checkpoint.json` records parent-session counters, including repeated
cached context. It excludes separate model trials and all subagents/quorums; it is
not the complete monetary creation cost. The goal counter uses another basis.

## Exact next experiment — not yet implemented or run

The latest quorum preferred **testing guidance alone before porting a new executor**.
One member favoured a Go runner immediately; two favoured isolating the guidance
benefit first. Current 16% evidence bundles guidance, discovery and compression.

Build a cold-adoption comparison with three arms and three sequences per arm:

1. Natural tooling, retaining whatever helpers the model chooses.
2. Actual `loop init --mode testing` installation, then native commands directly.
3. The same installed skill plus the current compact Python wrapper.

Use two tasks in each retained workspace, with a fresh model session per task:
first the existing Porsche timestamp repair; then the configuration-flow cleanup
regression defined in `evals/repositories/switch.py:cases`. Count actual skill
installation and wrapper installation/configuration in the first measured task.
Do not pre-copy the skill and call installation free. Dependency preparation can
remain outside timing if clearly disclosed and identical across arms.

Do not name the exact production file in the task prompt; describe the behaviour
so the agent must discover the component. Preserve original tests/configuration.
Keep two separate outcomes:

- Common repair correctness: identical independent relevant focused/full native
  tests for every arm.
- Delivered workflow validity: the wrapper promises reusable named checks, so
  rerun its configured commands against repaired, regressed and restored code.

Do not require unused `feedback.json` or receipt files from natural/direct arms.
Audit their observed commands descriptively and mark ambiguous selection unverified;
do not replay arbitrary shell commands or infer chosen-check sensitivity from the
independent grader. A broken wrapper setup may invalidate an adoption win even
when the production repair passes. A Go port should earn its cost versus the
installed guidance, not merely versus an unguided baseline.

Useful existing code: `repositories/agent.py` has `invoke_agent`, `digest_files`
and configured-check grading; `lifecycle.py` retains workspaces; `lifecycle_report.py`
verifies transcript hashes/usage and rejects incomplete crossover claims. **Do not
reuse lifecycle unchanged for component switching:** its protected-file selection
assumes all stages modify the same file. Recompute protection per stage so prior
repairs and all other original files stay intact. Freeze prompts, grader, skill,
model and source hashes before comparisons. Never pool different harness revisions.

## External snapshots and commands

Use git archives, never edit/deploy these live checkouts:

- Loop host snapshot: `375fa17407392287841ed16a5c62d3ea8634a00b`.
- Landing: `/Users/domhauton/Documents/github.com/domhauton/landing`, pinned
  `ef410d16b48d6e758bfa83d38531cc31caed52e9`. Other chats/user work modified this
  checkout concurrently. Native frontend setup needs `npm ci` and `npm run build`
  for WASM before the Node suite. Full browser/database/deployment gates are outside
  these profiles. Do not rewrite the user's editorial prose.
- PorscheConnect: `/Users/domhauton/Documents/github.com/CJNE/ha-porscheconnect`,
  pinned `45009be1cba72fe2510990b368ee14aa74149a42`, the user's PR #422 head.
  Prepared interpreter: `/Users/domhauton/Documents/github.com/CJNE/ha-porscheconnect/.venv/bin/python`.
  Focused pytest uses `--no-cov`; the full suite retains its 80% coverage gate.
  All account/vehicle operations in these tests are mocked. No PR edits were made.
- Energy: `/Users/domhauton/Documents/github.com/domhauton/automations`, pinned
  `8c3792048d6f4665fc5d35d815fd3e592c8a1bd2`. Actual package is
  `internal/energy/electricity`; root `energy` was a binary, not the service source.
  Do not touch live charging, Home Assistant, schedulers or unrelated local work.

Deterministic validation commands are documented in `evals/repositories/README.md`.
For normal changes run `gofmt`, `go vet ./...`, `go test ./...`, and
`python3 -m unittest discover -s evals -p 'test_*.py'`. Validate changed generated
skills/workflows as required by module guidance. Do not claim the newly delivered
skill alone improves efficiency until the comparison above actually establishes it.
