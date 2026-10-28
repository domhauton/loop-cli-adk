# Authoring

Own manifest file loading and disposable project builds. Only production dependency is internal/definition. Never enter the project runtime graph. Go subprocesses receive argument arrays, not shell strings. Remove temporary sources and preserve existing output on failure.

Use real fixtures and temporary directories. Read the shared contract in
`pkg/operation` and the import budget in `internal/architecture`.

Verify with `go test ./internal/authoring` and `go test ./internal/architecture`.
