# Persisted definitions

Own the JSON DTO and structural validation only. No network, environment or runtime imports. Reject unsupported behaviour before execution. Keep the documented manifest contract in sync.

Use real fixtures and temporary directories. Read the shared contract in
`pkg/operation` and the import budget in `internal/architecture`.

Verify with `go test ./internal/definition` and `go test ./internal/architecture`.
