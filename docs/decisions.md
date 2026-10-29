# Design decisions

These decisions capture the design discussion on 28 October 2026. An accepted
direction is not a claim that every capability has been implemented.

| Decision | Reason | Status |
| --- | --- | --- |
| Shared Go runtime plus thin project CLIs | Small project-owned source and native distribution | Implemented first slice |
| Local manifest runner and named standalone executable use the same facade | Avoid divergent behaviour | Implemented |
| Declarative JSON manifest, separate from runtime objects | No language toolchain for ordinary local execution | Implemented; YAML not required for v1 |
| Small config for ordinary API calls, ordinary code for exceptional workflows | Avoid a workflow language inside config | Config implemented; custom handler API pending |
| CLI plus API-building skills, no server SDK initially | Work with the project's existing backend | Development/release skills scaffolded |
| Agent development and verification is the first workflow | Prove prepare/exercise/inspect/clean-up incrementally | Inspect step implemented |
| One Go module, isolated packages and explicit registration | Compiler checks and small local development context | Implemented |
| Frontend and backend protocol boundaries are distinct | Independent development of CLI/MCP and HTTP/gRPC | CLI/HTTP implemented |
| Semantic versioning and pinned SDK/template inputs | Repeatable builds and deliberate upgrades | SDK pin/checksums and template version scaffolded |
| Linux, macOS and Windows, each amd64 and arm64 | Consumers need no Go/Node runtime | Release/CI configuration included |
| GitHub Actions and GoReleaser for release automation | Reuse existing release machinery | Loop and generated project workflows included |
| Discover and reuse suitable organisation publishing infrastructure | Avoid unnecessary repos and technical questions | Guided by generated release skill; provider tooling pending |
| Offer templated multi-project publishing repos when needed | Automate the setup once authorised | Pending |
| Progressive-disclosure agent guidance | Keep component tasks locally understandable | Module guidance and generated project skills implemented |

## Scaffold decisions

`loop init` accepts a project name, destination and optional SDK version. It renders
locally without credentials, network access or a Go toolchain. Names are portable
across the supported operating systems. Existing files and symlink parents cause a
conflict before any generated files are written. Unrelated files are preserved.

The bootstrap SDK pin is the immutable public Go revision of `2b0eb32`, which passed
all six native targets. This avoids a fictional release tag or a dependency on a
moving branch. `go.sum` is included for the default pin; custom pins resolve their
checksums with `go mod tidy`. `.loop/scaffold.json` records template and SDK versions.
No automatic template migration is implied.

The generated `/health` operation is an example, exercised by an offline fixture.
Agents adapt it and its test to the real admin API. The generated GitHub release
workflow is executable by default but can be retargeted to discovered organisation
infrastructure. Creating a scaffold does not authorise publishing or provisioning.

## Alternatives considered

Generated standalone source provides source autonomy but produces larger trees and
regeneration work. A universal runner alone reduces publishing work but does not
deliver the named project CLIs we want. We chose shared execution with both modes.

TypeScript provides convenient typed configuration and JS extensions. Go better
fits the chosen native distribution model and a mostly declarative HTTP client.
The target project's backend is not required to use Go.

Separate processes or Go modules can provide independent deployment/versioning.
They add compatibility and release coordination which we do not need to prove
independent component development. Start with enforced package boundaries.

## First-slice defaults and limits

- Schema version 1, strict known fields, GET only, string query inputs only.
- Base URL and optional bearer token come from named environment variables.
- Base URL paths are prefixes: `/admin/v1` plus `/users` becomes `/admin/v1/users`.
- Discovery/help never need API credentials. Required token absence fails locally.
- One request per invocation. No retries, redirects, writes, pagination or telemetry.
- 1 MiB manifest/input limit, 4 MiB response limit, 30-second HTTP timeout.
- Complete JSON on stdout. Structured errors on stderr. Exit 2 for input/config
  mistakes, 1 for execution/build/output failures, 0 for success.
- HTTP error bodies and diagnostic causes are not printed, to avoid leaking secrets.
- No full JSON Schema engine or dynamic code/plugin loading in this slice.

## Release constraints

Cross-compilation is not runtime verification. CI executes the native tests and
installation smoke checks on the supported OS/architecture matrix. Local macOS
testing only proves the local target until CI runs.

Package-manager setup and signing credentials are publisher-owned. Public catalogue
acceptance can be asynchronous. Apple signing/notarisation can require paid
membership. The kit should support those channels without requiring paid tooling
for basic archive distribution. Never bypass OS security checks in an installer.

Do not automatically overwrite user-edited templates during an upgrade. Record
versions and review regenerated differences first. Build migrations only when real
compatibility needs appear.

## Evaluation-driven test support

Template version 2 pins the six-target-tested `59d6475` SDK, which includes
`pkg/clitest`. Generated contract cases replace repeated HTTP/output boilerplate;
discovery and native-executable checks remain separate. A focused testing skill
explains this helper without replacing the backend's business tests.

The first three-pair skill ablation did not establish a cost saving. Skill effects
and CLI amortisation are different experiments. The amortisation baseline must
allow whatever testing approach the model naturally chooses, including existing
tests and reusable scripts; never force it to rewrite scripts. Count CLI setup and
maintenance, preserve workspace artefacts between tasks in both arms, and grade
the same outcomes. Paid CI evals are opt-in; deterministic grader checks run in
the ordinary six-target matrix.

## Starting small

Template version 3 adds an explicit `manifest` init mode. The agent runner pilot
created a full project merely to learn the manifest shape, then deleted its Go and
release files. Manifest mode replaces that unnecessary setup with three files:
the definition, an inspection skill and scaffold metadata. The installed Loop owns
execution; no SDK version is recorded because no project Go dependency exists.
The default `project` mode continues to generate a distributable named CLI.

A full CLI is not assumed to repay its setup cost for a small API. The lifecycle
evaluation lets agents retain their own verification scripts, measures cumulative
setup/maintenance cost, and records observed client use. Keep that natural baseline
strong rather than forcing repeated script generation to manufacture a win.

## Verification interface remains experimental

The user requested measured prototypes of native-test composition and declarative
API checks before selecting a boundary. Both live under `evals/prototypes`, share
one Loop invocation adapter, and are excluded from production packages/scaffolds.
Three four-task sequences per approach passed, as did the natural-tooling baseline.
Declarative checks reduced median output tokens by about 23% but increased total
input-plus-output tokens by about 14%; the native helper reduced output by about
6% but increased total by about 24%. Neither repaid setup within these tasks.

This is a distinction between reducing generated code and reducing whole-agent
work, not evidence against reuse in general. Do not promote either prototype or
advertise token savings on this evidence. Keep native tests supported, evaluate
broader workflows, and preserve the unconstrained baseline. See
`evals/results/verification-prototypes-v1.json` for complete usage and limitations.

Template version 4 documents the exact per-input declaration shape in both
project-development and manifest-only guidance. A measured trial guessed a JSON
Schema-style object and needed a repair. A short generic example supplies the
missing contract; it does not introduce another manifest language or prescribe
an application's API. Both generated examples are validated by `loop check`.

## Native feedback remains opt-in experimental work

The modular harness has been validated against Loop's Go tests, Landing's Node
suite and PorscheConnect's Home Assistant tests at pinned revisions. Eighteen
model repair trials passed. The prepared skill reduced median total tokens on the
PorscheConnect defect, but increased them on the Go and Node defects; uncached
input did not move consistently with total input. This does not establish a
universal cost saving or justify making another runtime dependency mandatory.

The next measured revision batches configured native checks and removes an
unnecessary discovery prerequisite. It records actual helper use and protects the
prepared configuration from edits. Those are experimental changes, not a decision
to ship a native-process protocol or a verification language in the CLI runtime.

A fresh comparison of the batched native feedback prototype passed all 18 repairs
and confirmed helper use in all nine prepared-workflow runs. Median total tokens
fell for Loop and PorscheConnect but remained higher for Landing. Uncached input
improved only on PorscheConnect. These results support continuing an optional
native-check workflow experiment; they do not justify mandatory adoption or a
universal cost claim. Preserve native assertions and keep process execution apart
from admin-API operations. Configuration and installation costs still need explicit
measurement before claiming a pay-off period.

A configuration-inclusive follow-up found no reliable immediate adoption saving.
All production repairs passed native tests, but one authored PorscheConnect
focused command incorrectly inherited the aggregate coverage gate and remained
red. The independent pass/fail/pass grader rejects that configuration. Keep
command discovery explicit and preserve whole-suite quality gates; a successful
repair alone does not prove the reusable feedback setup is usable. See
`evals/results/native-adoption-v1.json`. Longitudinal native-workflow pay-off remains
unmeasured; do not extrapolate it by subtracting unrelated experiment medians.

A retained-workspace follow-up measured three distinct native repairs per sequence,
with command setup charged to the first task. PorscheConnect passed all six
sequences and used about 16% fewer median total tokens across three tasks; median
uncached input and output also fell. Loop and Landing each had an explicit model
capacity failure with unknown cost, so their cumulative comparisons are invalid.
The evidence now supports an optional native-feedback workflow for this tested
Home Assistant component, including configuration. It still does not justify a
universal saving, a mandatory runtime feature, or API-CLI pay-off claims. Preserve
the failed attempts and keep broader coverage and installation cost explicit.

The template-version-4 manifest example has now been checked on the held-out
`add_audit_events` CLI-development task. All six revision-comparison trials passed
with immutable SDK sources and identical runtime/helper code. Median total tokens
fell about 49%, output about 23%, but uncached input increased. Keep the short
contract example: it improves the measured authoring loop without adding a new
runtime or verification language. Do not translate the total-token result into
credit or monetary savings, or generalise it beyond the measured task.

## Deliver guidance before adding another executor

A three-agent review challenged the remaining adoption gap and the bundled effects
in native-feedback results. The next slice ships optional, one-file native-testing
guidance through `loop init --mode testing`. It preserves native assertions and
uses existing authoring safety; it adds no runtime or command catalogue. Generated
skills cover component selection and the distinction between focused feedback and
aggregate quality gates, based on observed setup failures.

Compare natural tooling, installed guidance, and the same guidance plus the
experimental wrapper before deciding whether to port that wrapper. Count actual
installation and switch components between tasks. Keep common repair correctness
separate from the wrapper's additional promise that named checks remain reusable.
Do not require unused command-configuration files in the direct-native arms.
