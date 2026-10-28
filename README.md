# Loop CLI ADK

Build agent-facing project CLIs from small admin-API definitions.

The first slice is implemented: validate a JSON manifest, discover commands, call
an HTTP API, and build a standalone project executable using the same runtime.
Publishing discovery, project scaffolding, custom handlers and additional protocols
are planned. See [architecture](docs/architecture.md) and [decisions](docs/decisions.md).

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

`loop build --sdk-dir /path/to/loop-cli-adk` is the development path. Once an SDK
release exists, use `--sdk-version v0.x.y` instead. For cross-compilation add
`--goos linux --goarch arm64`, for example. Build needs Go, execution does not.

## Development

Read [AGENTS.md](AGENTS.md), then the guidance in the module you are changing.

```sh
go vet ./...
go test ./...
go test -race ./...
```

Tests run a real HTTP fixture and build a real project executable in a temporary
directory. They compare local and embedded discovery, success and error behaviour.
Dependency tests enforce module boundaries. Use `go test -short ./...` for a quicker
iteration without compiling the project executable.

## Licence

[Apache License 2.0](LICENSE).
