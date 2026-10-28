# Working on Loop

Loop is a Go library and CLI kit for manifest-defined, agent-facing project CLIs.
Read `docs/architecture.md` and `docs/decisions.md` before changing a boundary.
Read the nearest module `AGENTS.md` when working inside it.

## Engineering

- One composition root, explicit registration, no global registries or `init()` wiring.
- Concrete types by default. Add small interfaces at actual consumer boundaries.
- Separate persisted definitions from runtime objects and credentials.
- Keep HTTP semantics in the HTTP adapter. Frontends depend on the project facade.
- Runtime code must never import authoring, publishing or infrastructure discovery.
- Preserve causes in errors, expose only safe messages through the CLI.
- Bound I/O. Honour cancellation. Never silently truncate a JSON result.
- Use British spelling, idiomatic Go names and comments explaining reasons.
- Document exported types/functions. Keep generated build files disposable.
- Add capabilities only when exercised by a real operation and contract tests.

## Working independently

Keep changes inside the owning module where possible. A new component normally
adds its implementation, tests and explicit composition wiring. Boundary changes
also update the dependency test and architecture document, with the reason.
Use `internal/architecture/dependencies_test.go` to see permitted imports.
Do not weaken that test merely to make a new dependency pass.

## Verification

Run `gofmt` on changed Go files, `go vet ./...`, and `go test ./...`.
Use real temporary directories and HTTP test servers. Add exact malformed-input
regressions and round-trip tests for parsing changes. Avoid sleeps and live-service
tests. `go test -short ./...` skips executable compilation during quick iteration.
Release binaries use `CGO_ENABLED=0`. Cross-compilation is not execution evidence.

## Publishing

Discover existing organisation repositories, workflows and local registry settings
before suggesting new infrastructure. Never print credentials. Existing credentials
show feasibility, not publishing authorisation. Preserve unrelated configuration.
Record unimplemented work explicitly. Do not claim a release or installation works
on a platform until its actual artefacts have been tested there.

Design guidance: https://github.com/domhauton/agent-guide/blob/main/skills/dom-code/SKILL.md
