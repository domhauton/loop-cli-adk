# HTTP adapter

Own request encoding, credentials, HTTP lifecycle and bounded response reads. Only import pkg/operation. No retries/redirects in this slice. Preserve cancellation and never include tokens or response bodies in public errors.

Use real fixtures and temporary directories. Read the shared contract in
`pkg/operation` and the import budget in `internal/architecture`.

Verify with `go test ./internal/httpapi ./pkg/project` and `go test ./internal/architecture`.
