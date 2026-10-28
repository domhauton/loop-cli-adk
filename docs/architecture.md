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
| `internal/authoring` | Bounded file loading and standalone builds | definition |
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
No SDK release exists yet, so the working path today is `--sdk-dir`.

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
