# Authoring

Own manifest file loading and disposable project builds. Only production dependency is internal/definition. Never enter the project runtime graph. Go subprocesses receive argument arrays, not shell strings. Remove temporary sources and preserve existing output on failure.

`init.go` owns scaffold validation and file creation. `templates/` contains the
generated project, skills and workflows. Keep the shared entry point used by init
and build in `projectMain`. Use separate template delimiters so GitHub Actions and
GoReleaser expressions survive rendering. Do not write credentials or local SDK
paths into a scaffold. Default SDK pins and checksums must resolve publicly.
Preflight every destination and create files exclusively, never overwrite existing
content or follow a symlink parent. Initialisation has no network/subprocess work.

Run the generated project tests when changing a template. CI also scaffolds and
tests the published SDK pin on all six native targets. Validate generated skills
and workflow/GoReleaser syntax when those templates change.

Use real fixtures and temporary directories. Read the shared contract in
`pkg/operation` and the import budget in `internal/architecture`.

Verify with `go test ./internal/authoring` and `go test ./internal/architecture`.

`project` mode is the default standalone scaffold. `manifest` mode emits only the
manifest, inspection skill and metadata; it must not write a Go module, README,
root AGENTS file or workflows into an existing host project. It cannot select an
SDK version because it uses the installed runner. Keep both modes on the same
preflight/exclusive-create path and bump the template version for recipe changes.

`testing` mode installs only a project-named native-testing skill. It has no SDK
version, API manifest or scaffold metadata file, so it can coexist with existing
project definitions. It shares exclusive creation and symlink checks with the other
modes; no host configuration or test commands are inferred or executed during init.
