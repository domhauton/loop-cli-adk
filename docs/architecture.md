# Loop architecture

Loop turns a small project definition into a CLI that agents can discover, run
and test. The first implementation supports JSON manifests and unary HTTP GET
operations. The same execution path powers local use and embedded project CLIs.

## Boundaries

| Module | Owns | Allowed project dependencies |
| --- | --- | --- |
| `pkg/operation` | Discoverable descriptors, handler signature, public errors | None |
| `internal/definition` | Persisted manifest and structural validation | None |
| `internal/execution` | Registry, input validation, dispatch, cancellation | operation |
| `internal/httpapi` | URL/query encoding, auth, HTTP lifecycle, response bounds | operation |
| `pkg/project` | Composition facade, definition-to-runtime translation | definition, execution, httpapi, operation |
| `pkg/cli` | Arguments, discovery, help, output and exit codes | project, operation |
| `pkg/clitest` | Optional offline contract-test fixtures | cli, project |
| `internal/authoring` | Scaffolding/templates, bounded file loading and standalone builds | definition |
| `cmd/loop` | Authoring command entry point and process lifecycle | authoring, cli, project, operation |

Production imports are checked in `internal/architecture/dependencies_test.go`.
Integration tests may cross boundaries. The standard library is the only current
dependency. These are packages in one Go module, not separate release units.

Definitions contain no live clients, functions or credential values. Project
construction translates them to descriptors and HTTP handlers. It does not contact
the API or read credentials. The handler resolves environment references when
invoked. The executor validates input first. The frontend prints one complete JSON
result to stdout, or one structured error to stderr with a non-zero exit code.

## Local and embedded execution

`loop run` loads a manifest and calls `project.New` followed by `cli.Run`.
`loop build` writes a temporary Go entry point which embeds that same manifest and
calls the same functions. It compiles a native executable and removes temporary
sources. Build outputs contain the runtime, not the authoring tooling.

Building requires Go. Running an installed Loop or project executable does not.
Development builds select an SDK checkout explicitly. Released builds select a
pinned SDK semantic version. There is no implicit download of a moving branch.
No SDK release tag exists yet. The scaffold pins an immutable Go pseudo-version
which resolves through the public module service. Local SDK checkouts remain an
explicit development option.

## Scaffolding

`loop init --name NAME --dir DIRECTORY` renders a complete project inside the
authoring module. The process entry point only parses flags and serialises results.
No runtime package imports the templates or scaffolder. The generated main and the
temporary build main share the same entry-point source.

Scaffolding uses embedded, versioned templates, validates the manifest before writing,
preflights all destination files, rejects symlink parents and creates files exclusively
within an `os.Root`. Existing content is preserved. Repeating init reports a conflict
instead of reconciling or migrating files. On a write failure, newly created files
are removed where possible, but empty directories may remain.

The generated project includes local development/release skills and a six-target CI
workflow. Tagged releases use GoReleaser only after that CI succeeds. The default
SDK pin includes known module checksums. Custom pins resolve checksums using normal
Go tooling. Init never invokes Go, accesses credentials, contacts a registry or
creates external infrastructure. A release skill handles infrastructure discovery
and intent, using the agent's available tools. There is no automatic provider
provisioner in this version.

Template tests run a generated project against the current SDK through a temporary
Go workspace, without committing local `replace` directives. Native CI separately
builds/tests the default published SDK pin, detecting template/runtime incompatibility.

## Extension boundaries

Backend protocols and agent frontends are different extension points. A future
gRPC adapter owns its connections, method encoding and credentials. A future MCP
frontend owns discovery/invocation presentation and calls the project facade.
Neither should import the other.

HTTP pagination and retries belong in the HTTP adapter or its decorators. There
is no universal page token, automatic page draining or generic write retry.
Server-side dry-run, transactions and idempotency require actual API support.

The current handler contract is one JSON object containing string inputs, and
one JSON result. More input types can be added deliberately. Streaming requires
an explicit contract decision. We do not claim the current contract supports all
future protocols unchanged.

Custom compiled Go handlers are an intended extension, but project-level custom
registration is not exposed in this slice. Runtime plugin loading, subprocess
plugins and separate component modules are deferred until a real use case needs
their lifecycle and compatibility costs.

## Authoring and distribution

Authoring and distribution never enter the runtime dependency graph. Skills guide
intent, exploration and API creation in the project's existing backend language.
Deterministic tooling validates definitions, builds artefacts and prepares concrete
configuration changes. Skills should use progressive disclosure and derive command
references from the same definitions used for execution.

Distribution should discover organisation taps, buckets, registry configuration
(including Artifactory) and existing CI conventions before asking the user about
infrastructure. Prefer existing destinations that support the artefact and intended
audience. Inspect credential availability without displaying values. Read access or
credential presence does not imply permission to publish.

When infrastructure is missing, offer a templated, multi-project publishing
repository and create it once accepted. Homebrew/Scoop and shared catalogues such
as WinGet need distinct recipes. Use existing release tools instead of building a
general publishing platform. Keep provisioned changes reviewable and rerunnable.

## Independent agent development

Each module's local guidance names its purpose, public boundary, side effects,
dependencies and verification command. Work should need that document, the shared
contract and the module's fixtures. Boundary changes require an explicit rationale.

Acceptance examples:

- An ordinary API command changes its project definition and fixtures.
- HTTP pagination changes HTTP code and conformance tests.
- A new backend adds its own adapter, binding schema and composition registration.
- A new frontend adds presentation code and calls the existing facade.
- Artifactory discovery changes authoring/distribution code only.
- Windows installation changes release tooling and Windows installation tests.

Do not build empty packages or interfaces for those future components. Introduce
them with the first working implementation and a dependency budget.

## Evaluation boundary

`evals/` owns opt-in model experiments, token accounting and integration against a
pinned external project snapshot. It is development tooling, never imported by the
Go runtime or generated project. Python's standard library handles experiment
orchestration; installed project CLIs still need neither Python nor Go.

The Energy overlay executes actual handlers in a disposable checkout with synthetic
state. The agent grader inspects compiled artefacts and mutates command mappings to
check test sensitivity. Model transcripts are private local artefacts; committed
reports contain aggregate evidence and explicit limitations. No model calls or
private-project checkout is required by ordinary CI. See `evals/README.md`.

`pkg/clitest` is optional Go test support depending only on `pkg/cli` and
`pkg/project`. Its local HTTP fixture validates independently specified requests,
pass-through JSON, structured errors and absence of requests for invalid input.
Runtime packages and executable entry points cannot import it. This keeps reusable
test mechanics out of each project's handwritten tests without adding a test DSL.

Public errors may include optional string-valued `details` supplied by the owning
adapter. The HTTP adapter sets `http_status` for non-2xx responses. The CLI forwards
these values without understanding HTTP; a future protocol can expose its own
safe keys. Existing error codes, messages and exit codes are unchanged. Causes,
credentials, URLs and response bodies remain excluded. Consumers should tolerate
additional details rather than parsing human-readable messages for protocol data.

## Native feedback experiments

`evals/repositories` exercises existing project test frameworks without adding a
server API or entering the runtime graph. `profiles.py` owns each repository's
pinned source, prerequisites, test commands and regression fixture. The shared
`native_command.py` owns bounded subprocess execution and logs. The experimental
`feedback.py` frontend selects configured commands and emits compact results;
assertions stay in native tests. `agent.py` owns isolated model trials and
independent grading, while `report.py` checks provenance and accounts for usage.

This separation lets a new repository adapter supply its native workflow without
changing the executor or understanding another repository's stack. The experiment
requires the host project's normal tools plus Python for orchestration. It does
not change the installed Loop/project executable's Go-free, Python-free runtime
contract. `loop init` does not currently install this experimental frontend.

Batched feedback commands validate the whole selection before execution and stop
on the first failed check. Skipped checks are explicit; a partial batch cannot
report success. Full bounded logs stay local, with compact results and labelled
failure excerpts. Independent grading runs original native tests regardless of
the helper's claimed outcome and checks that tests/configuration remain unchanged.

## Native-testing skill delivery

`loop init --mode testing --name NAME --dir DIRECTORY` uses the authoring module's
existing validation and exclusive-create path to install one project-named native
testing skill. It creates no API definition, SDK dependency, runner, workflow or
root guidance file. It does not load an existing manifest. The host's native test
framework owns assertions and execution; installed skill use needs no Loop runtime.
The installed Loop binary can scaffold the skill without Go, Python or networking.
No new production dependency is introduced. Experimental process wrappers remain
in `evals/` until their benefit over the same guidance alone is measured.
