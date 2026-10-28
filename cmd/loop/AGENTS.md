# Process entry point

Wire authoring commands and the project CLI. Own signal handling and process exit. Do not put API semantics here. Always defer cleanup before returning an exit status.

Use real fixtures and temporary directories. Read the shared contract in
`pkg/operation` and the import budget in `internal/architecture`.

Verify with `go test ./cmd/loop ./internal/authoring` and `go test ./internal/architecture`.
