# Operation execution

Own registry lookup and input validation. Only import pkg/operation. Never inspect HTTP status codes, URLs or publishing settings. Descriptors returned to callers must not mutate the registry.

Use real fixtures and temporary directories. Read the shared contract in
`pkg/operation` and the import budget in `internal/architecture`.

Verify with `go test ./internal/execution ./pkg/project` and `go test ./internal/architecture`.
