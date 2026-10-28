# Shared contract

Descriptors, validated string-input handlers and safe public errors. No other project imports. Changing this API affects all adapters and frontends, so explain compatibility.

Use real fixtures and temporary directories. Read the shared contract in
`pkg/operation` and the import budget in `internal/architecture`.

Verify with `go test ./pkg/project ./internal/execution` and `go test ./internal/architecture`.
