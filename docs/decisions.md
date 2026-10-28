# Design decisions

These decisions capture the design discussion on 28 October 2026. An accepted
direction is not a claim that every capability has been implemented.

| Decision | Reason | Status |
| --- | --- | --- |
| Shared Go runtime plus thin project CLIs | Small project-owned source and native distribution | Implemented first slice |
| Local manifest runner and named standalone executable use the same facade | Avoid divergent behaviour | Implemented |
| Declarative JSON manifest, separate from runtime objects | No language toolchain for ordinary local execution | Implemented; YAML not required for v1 |
| Small config for ordinary API calls, ordinary code for exceptional workflows | Avoid a workflow language inside config | Config implemented; custom handler API pending |
| CLI plus API-building skills, no server SDK initially | Work with the project's existing backend | Skills pending |
| Agent development and verification is the first workflow | Prove prepare/exercise/inspect/clean-up incrementally | Inspect step implemented |
| One Go module, isolated packages and explicit registration | Compiler checks and small local development context | Implemented |
| Frontend and backend protocol boundaries are distinct | Independent development of CLI/MCP and HTTP/gRPC | CLI/HTTP implemented |
| Semantic versioning and pinned SDK/template inputs | Repeatable builds and deliberate upgrades | Explicit SDK selection implemented |
| Linux, macOS and Windows, each amd64 and arm64 | Consumers need no Go/Node runtime | Release/CI configuration included |
| GitHub Actions and GoReleaser for release automation | Reuse existing release machinery | Loop release configuration included; project templates pending |
| Discover and reuse suitable organisation publishing infrastructure | Avoid unnecessary repos and technical questions | Recorded; discovery pending |
| Offer templated multi-project publishing repos when needed | Automate the setup once authorised | Pending |
| Progressive-disclosure agent guidance | Keep component tasks locally understandable | Module guidance implemented; product skills pending |

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
