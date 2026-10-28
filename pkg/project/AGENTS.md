# Composition facade

Translate definitions into runtime descriptors and explicitly bind handlers. This is the only place joining definition, execution and HTTP packages. Construction and discovery must not read credentials or contact the API.

Use real fixtures and temporary directories. Read the shared contract in
`pkg/operation` and the import budget in `internal/architecture`.

Verify with `go test ./pkg/project` and `go test ./internal/architecture`.
