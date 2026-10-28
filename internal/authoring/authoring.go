// Package authoring builds project executables without entering their runtime graph.
package authoring

import (
	"context"
	"fmt"
	"io"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"runtime"
	"strconv"
	"strings"

	"github.com/domhauton/loop-cli-adk/internal/definition"
)

const modulePath = "github.com/domhauton/loop-cli-adk"

// BuildOptions selects the output target and exactly one SDK source.
type BuildOptions struct{ Output, SDKDir, SDKVersion, GOOS, GOARCH string }

// ReadManifest reads at most the manifest limit plus one detection byte.
func ReadManifest(path string) ([]byte, error) {
	f, err := os.Open(path)
	if err != nil {
		return nil, fmt.Errorf("open manifest: %w", err)
	}
	defer f.Close()
	data, err := io.ReadAll(io.LimitReader(f, definition.MaxManifestBytes+1))
	if err != nil {
		return nil, fmt.Errorf("read manifest: %w", err)
	}
	if len(data) > definition.MaxManifestBytes {
		return nil, fmt.Errorf("manifest exceeds %d bytes", definition.MaxManifestBytes)
	}
	return data, nil
}

// Build compiles the same manifest and facade used by the local runner.
// A Go toolchain is required here, never on the consumer's machine.
func Build(ctx context.Context, manifest []byte, opts BuildOptions) error {
	if _, err := definition.Parse(manifest); err != nil {
		return fmt.Errorf("validate manifest: %w", err)
	}
	if opts.Output == "" {
		return fmt.Errorf("output path is required")
	}
	if (opts.SDKDir == "") == (opts.SDKVersion == "") {
		return fmt.Errorf("provide exactly one of sdk-dir or sdk-version")
	}
	if opts.GOOS == "" {
		opts.GOOS = runtime.GOOS
	}
	if opts.GOARCH == "" {
		opts.GOARCH = runtime.GOARCH
	}
	if (opts.GOOS != "linux" && opts.GOOS != "darwin" && opts.GOOS != "windows") || (opts.GOARCH != "amd64" && opts.GOARCH != "arm64") {
		return fmt.Errorf("unsupported target %s/%s", opts.GOOS, opts.GOARCH)
	}
	goMod := "module loop-project-build\n\ngo 1.26.0\n\nrequire " + modulePath + " "
	if opts.SDKDir != "" {
		root, err := filepath.Abs(opts.SDKDir)
		if err != nil {
			return fmt.Errorf("resolve SDK directory: %w", err)
		}
		mod, err := os.ReadFile(filepath.Join(root, "go.mod"))
		if err != nil {
			return fmt.Errorf("read SDK module: %w", err)
		}
		// Git may check out go.mod with CRLF on Windows.
		moduleText := strings.ReplaceAll(string(mod), "\r\n", "\n")
		if !strings.Contains(moduleText, "module "+modulePath+"\n") {
			return fmt.Errorf("sdk-dir is not a Loop SDK checkout")
		}
		goMod += "v0.0.0\n\nreplace " + modulePath + " => " + strconv.Quote(filepath.ToSlash(root)) + "\n"
	} else {
		if !regexp.MustCompile(`^v0\.[0-9]+\.[0-9]+(?:-[0-9A-Za-z.-]+)?$`).MatchString(opts.SDKVersion) {
			return fmt.Errorf("sdk-version must be an explicit v0 semantic version")
		}
		goMod += opts.SDKVersion + "\n"
	}
	dir, err := os.MkdirTemp("", "loop-build-*")
	if err != nil {
		return fmt.Errorf("create build directory: %w", err)
	}
	defer os.RemoveAll(dir)
	for name, data := range map[string][]byte{"go.mod": []byte(goMod), "main.go": []byte(projectMain), "project.json": manifest} {
		if err := os.WriteFile(filepath.Join(dir, name), data, 0600); err != nil {
			return fmt.Errorf("write build input: %w", err)
		}
	}
	cmd := exec.CommandContext(ctx, "go", "build", "-mod=mod", "-trimpath", "-o", filepath.Join(dir, "project.bin"), ".")
	cmd.Dir = dir
	cmd.Env = replaceEnv(os.Environ(), map[string]string{"CGO_ENABLED": "0", "GOOS": opts.GOOS, "GOARCH": opts.GOARCH, "GOWORK": "off"})
	// Do not surface subprocess output that may contain private module URLs or credentials.
	if err := cmd.Run(); err != nil {
		return fmt.Errorf("Go build failed (check the Go toolchain and access to the selected SDK): %w", err)
	}
	output, err := filepath.Abs(opts.Output)
	if err != nil {
		return fmt.Errorf("resolve output path: %w", err)
	}
	if err := os.MkdirAll(filepath.Dir(output), 0755); err != nil {
		return fmt.Errorf("create output directory: %w", err)
	}
	// Stage next to the destination so rename stays on the same filesystem.
	staged, err := os.CreateTemp(filepath.Dir(output), ".loop-build-*")
	if err != nil {
		return fmt.Errorf("stage output: %w", err)
	}
	defer os.Remove(staged.Name())
	source, err := os.Open(filepath.Join(dir, "project.bin"))
	if err != nil {
		staged.Close()
		return fmt.Errorf("open built executable: %w", err)
	}
	_, copyErr := io.Copy(staged, source)
	source.Close()
	closeErr := staged.Close()
	if copyErr != nil {
		return fmt.Errorf("copy executable: %w", copyErr)
	}
	if closeErr != nil {
		return fmt.Errorf("close executable: %w", closeErr)
	}
	if err := os.Chmod(staged.Name(), 0755); err != nil {
		return fmt.Errorf("make output executable: %w", err)
	}
	if err := os.Rename(staged.Name(), output); err != nil {
		return fmt.Errorf("install built executable: %w", err)
	}
	return nil
}

func replaceEnv(env []string, overrides map[string]string) []string {
	out := make([]string, 0, len(env)+len(overrides))
	for _, value := range env {
		key, _, _ := strings.Cut(value, "=")
		if _, ok := overrides[key]; !ok {
			out = append(out, value)
		}
	}
	for key, value := range overrides {
		out = append(out, key+"="+value)
	}
	return out
}

const projectMain = `package main

import (
    "context"
    _ "embed"
    "os"
    "os/signal"

    "github.com/domhauton/loop-cli-adk/pkg/cli"
    "github.com/domhauton/loop-cli-adk/pkg/project"
)

//go:embed project.json
var manifest []byte

func main() { os.Exit(run()) }

func run() int {
    ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt)
    defer stop()
    p, err := project.New(manifest, os.Getenv)
    if err != nil { return cli.WriteError(os.Stderr, err) }
    return cli.Run(ctx, p, os.Args[1:], os.Stdout, os.Stderr)
}
`
