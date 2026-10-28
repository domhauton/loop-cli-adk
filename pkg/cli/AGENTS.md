# CLI frontend

Own argument parsing and rendering. Depend only on pkg/project and pkg/operation. No HTTP or file-system logic. Results go to stdout, safe structured errors to stderr. Keep invocation non-interactive.

Use real fixtures and temporary directories. Read the shared contract in
`pkg/operation` and the import budget in `internal/architecture`.

Verify with `go test ./pkg/project ./internal/authoring` and `go test ./internal/architecture`.
