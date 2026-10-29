# Loop CLI ADK

Build agent-facing project CLIs from small admin-API definitions.

Scaffold a project with config, agent skills, tests and release automation, then
run it locally or build a standalone executable using the same runtime. The current
API bindings support GET commands and string query inputs. Provider provisioning,
custom handlers and additional protocols are planned. See
[architecture](docs/architecture.md) and [decisions](docs/decisions.md).

## Installation

No public release has been published yet. From a checkout, use Go 1.26 or later:

```sh
go build -o bin/loop ./cmd/loop
./bin/loop --help
```

The release workflow produces Linux, macOS and Windows builds for amd64 and arm64.
Consumers of those binaries do not need Go. Installer scripts are in `scripts/`.
Package-manager registration and signed/notarised distribution are follow-up work.

After a release is published, use `bash scripts/install.sh --version v0.x.y` on
Linux/macOS or `./scripts/install.ps1 -Version v0.x.y` on Windows. Omit the version
to select the latest release. Both verify the archive checksum, install into a
user-owned directory and print the PATH location. `--dir` / `-InstallDir` selects
another location. Neither script modifies shell profiles or bypasses OS security.

## Try the vertical slice

Start the local fixture API in one terminal:

```sh
go run ./examples/demo/server
```

In another terminal:

```sh
export DEMO_API_URL=http://127.0.0.1:8080
export DEMO_API_TOKEN=demo-local
go run ./cmd/loop check --manifest examples/demo/project.json
go run ./cmd/loop run --manifest examples/demo/project.json -- describe
go run ./cmd/loop run --manifest examples/demo/project.json -- users list --input '{"name":"Ada"}'
go run ./cmd/loop build --manifest examples/demo/project.json --output bin/democtl --sdk-dir .
./bin/democtl users list --input '{"name":"Ada"}'
```

On PowerShell, set environment variables with `$env:DEMO_API_URL = 'http://127.0.0.1:8080'`
and `$env:DEMO_API_TOKEN = 'demo-local'`. Build to `bin/democtl.exe` and invoke
`.\bin\democtl.exe`. The demo token is a public fixture credential, not a real secret.

The result is `{"users":[{"id":"user-1","name":"Ada"}]}`. Help and `describe`
also work without either environment variable. All commands are non-interactive.

## Scaffold a project CLI

```sh
./bin/loop init --name myproject --dir ./myproject-cli
cd myproject-cli
go test ./...
go run . describe
go build -o bin/myproject .
```

`loop init` needs no Go installation or network access when using the installed
Loop binary. The generated project's Go development and CI commands download its
pinned SDK on first use. The default pin and verified checksums refer to an existing
immutable SDK revision, so a release tag is not required to get started.

The scaffold includes:

- `project.json`: an example `status get` command for GET `/health`.
- `main.go`, `go.mod` and `go.sum`: a thin executable with a pinned runtime.
- `contracts_test.go`: compact HTTP contract cases using the shared fixture helper.
- `main_test.go`: discovery and native executable tests.
- `AGENTS.md` and three `.agents/skills/` skills for development, testing and publishing setup.
- Native CI for all six targets, a tag-triggered release workflow and GoReleaser config.
- README, ignore rules and `.loop/scaffold.json` recording the template/SDK versions.

Adapt the example endpoint and its fixture to the project's actual API. The generated
environment names are derived from the executable name, for example
`MYPROJECT_API_URL` and `MYPROJECT_API_TOKEN`. The release skill guides agents to
discover and reuse organisation infrastructure before proposing new publishing repos.
Scaffolding itself never creates external infrastructure or publishes a release.

Use `--sdk-version v0.x.y` to select another immutable SDK version. For a custom pin,
run `go mod tidy` and commit its resulting `go.sum` before release. Existing files
are never replaced, even on repeated init. Choose a new directory when integrating
with a project that already has its own Go module, README or workflows. The scaffold
is laid out as a dedicated CLI repository root. For a monorepo, an agent must merge
the generated workflows into the repository-root `.github/workflows/` with the
appropriate working directories. Init does not modify the parent repository.

## Project definition

```json
{
  "schema_version": 1,
  "name": "myproject",
  "description": "Inspect my project",
  "api": {"base_url_env": "MYPROJECT_API_URL", "token_env": "MYPROJECT_API_TOKEN"},
  "commands": [{
    "name": "users list",
    "description": "List users",
    "input": {"name": {"type": "string", "required": false}},
    "http": {"method": "GET", "path": "/users", "query": {"name": "name"}}
  }]
}
```

Command names contain lowercase words separated by single spaces. The HTTP query
map maps input names to API query names. Unknown inputs are rejected. Only the
declared string inputs and GET bindings are supported today. API prefixes in the
base URL are preserved. Put credential variable names, never tokens, in manifests.

`loop build --sdk-dir /path/to/loop-cli-adk` is the development path. Alternatively
use `--sdk-version` with a published tag or immutable Go pseudo-version, as recorded
in a generated project's `.loop/scaffold.json`. For cross-compilation add
`--goos linux --goarch arm64`, for example. Build needs Go, execution does not.

## Development

Read [AGENTS.md](AGENTS.md), then the guidance in the module you are changing.

```sh
go vet ./...
go test ./...
go test -race ./...
```

Tests run a real HTTP fixture and build a real project executable in a temporary
directory. They compare local and embedded discovery, success and error behaviour,
exercise scaffold conflicts, and compile/test a complete generated project offline
against the current SDK. Native CI additionally tests a scaffold against its public SDK pin.
Dependency tests enforce module boundaries. Use `go test -short ./...` for a quicker
iteration without compiling the project executable.

## Licence

[Apache License 2.0](LICENSE).

## Evaluate agent development

[Evaluation tooling](evals/README.md) checks a native CLI against Energy's actual
handlers in an offline fixture and runs opt-in agent trials for command development.
It records observed model tokens, task success and whether the agent's tests catch
broken API mappings. Model trials consume allowance and are not part of normal CI.

Generated CLIs use native Go tests and `pkg/clitest` for HTTP contracts. Keep the
application's existing test framework as the source of assertions. The compact
native-test runner and declarative API-check alternatives under `evals/` are
experimental; `loop init` does not install them and runtime packages do not import
them. Python is required only for this developer evaluation tooling.

See the [evidence index](evals/README.md#evidence-index) before choosing a workflow.
Some measured tasks improved, but API-CLI setup pay-off and universal token savings
are not established. Cached input, uncached input and output are reported separately.

Non-2xx HTTP errors expose a machine-readable status, for example
`{"error":{"code":"http_status","message":"API returned HTTP 401","details":{"http_status":"401"}}}`.
The optional details map contains safe string values. Existing error codes and
exit codes are unchanged; consumers need not parse the message to identify 401.

For API checks inside an existing project, start without a standalone build:

```sh
loop init --mode manifest --name myproject --dir .
loop check --manifest project.json
loop run --manifest project.json -- describe
```

Manifest mode creates only `project.json`, an inspection skill and scaffold
metadata. It preserves existing README, agent guidance and language build files.
It uses the installed Loop directly and needs no Go toolchain or SDK dependency.
Choose the default project mode when you need a named CLI with tests and release
workflows. Both modes retain the same refusal to overwrite existing files.

HTTP requests identify the shared client with `User-Agent: loop-cli-adk` for server
diagnostics. This sends no user or machine identifier and collects no analytics.
