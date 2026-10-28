# CLI contract fixtures

Own offline, project-level CLI contract checks. Depend only on the public project
and CLI facades. No runtime package or executable may import this test support
package; generated `_test.go` files may. The dependency test enforces this boundary.

Use independent expected paths and decoded query values. Never derive expected
requests from the manifest under test. Each case gets its own local HTTP server,
fixed synthetic credentials and bounded execution. Never consult os.Getenv.
Keep this a small Go helper, not another configuration or assertion language.

Test checker failures as well as passing examples. Mutated paths, query mappings
and required flags must fail. Missing assertions must not produce vacuous success.
Use `go test -race ./pkg/clitest` and `go test ./internal/architecture`.
