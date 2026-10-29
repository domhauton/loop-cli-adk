package authoring

import (
	"bytes"
	"context"
	"encoding/json"
	"io/fs"
	"os"
	"os/exec"
	"path/filepath"
	"reflect"
	"strings"
	"testing"
	"time"

	"github.com/domhauton/loop-cli-adk/internal/definition"
)

func TestInitCreatesUsableDefinition(t *testing.T) {
	dir := filepath.Join(t.TempDir(), "project with spaces")
	result, err := Init(InitOptions{Directory: dir, Name: "reefctl"})
	if err != nil {
		t.Fatal(err)
	}
	if result.Directory != dir || result.SDKVersion != DefaultSDKVersion || result.TemplateVersion != TemplateVersion {
		t.Fatalf("wrong result: %+v", result)
	}
	data, err := os.ReadFile(filepath.Join(dir, "project.json"))
	if err != nil {
		t.Fatal(err)
	}
	m, err := definition.Parse(data)
	if err != nil {
		t.Fatal(err)
	}
	if m.Name != "reefctl" || m.API.BaseURLEnv != "REEFCTL_API_URL" || m.API.TokenEnv != "REEFCTL_API_TOKEN" {
		t.Fatalf("wrong manifest: %+v", m)
	}
	roundTrip, err := json.Marshal(m)
	if err != nil {
		t.Fatal(err)
	}
	if _, err := definition.Parse(roundTrip); err != nil {
		t.Fatal(err)
	}
	for _, name := range []string{"main.go", "main_test.go", "contracts_test.go", "go.mod", "go.sum", "AGENTS.md", "README.md", ".loop/scaffold.json", ".goreleaser.yaml", ".github/workflows/ci.yml", ".github/workflows/release.yml", ".agents/skills/reefctl-develop/SKILL.md", ".agents/skills/reefctl-test/SKILL.md", ".agents/skills/reefctl-release/SKILL.md"} {
		if _, err := os.Stat(filepath.Join(dir, filepath.FromSlash(name))); err != nil {
			t.Errorf("missing %s: %v", name, err)
		}
	}
	before := snapshot(t, dir)
	if _, err := Init(InitOptions{Directory: dir, Name: "reefctl"}); err == nil {
		t.Fatal("repeat init overwrote project")
	}
	if after := snapshot(t, dir); !reflect.DeepEqual(before, after) {
		t.Fatal("repeat init changed files")
	}
}

func TestInitPreflightsEveryConflict(t *testing.T) {
	for _, conflicting := range []string{"README.md", "project.json", ".github/workflows/release.yml", ".agents/skills/reefctl-release/SKILL.md"} {
		t.Run(conflicting, func(t *testing.T) {
			dir := t.TempDir()
			name := filepath.Join(dir, filepath.FromSlash(conflicting))
			if err := os.MkdirAll(filepath.Dir(name), 0755); err != nil {
				t.Fatal(err)
			}
			if err := os.WriteFile(name, []byte("user-owned\r\n"), 0644); err != nil {
				t.Fatal(err)
			}
			before := snapshot(t, dir)
			if _, err := Init(InitOptions{Directory: dir, Name: "reefctl"}); err == nil {
				t.Fatal("accepted conflict")
			}
			if after := snapshot(t, dir); !reflect.DeepEqual(before, after) {
				t.Fatal("conflict changed files")
			}
		})
	}
}

func TestInitPreservesUnrelatedFiles(t *testing.T) {
	dir := t.TempDir()
	if err := os.WriteFile(filepath.Join(dir, "notes.txt"), []byte("keep me"), 0644); err != nil {
		t.Fatal(err)
	}
	if _, err := Init(InitOptions{Directory: dir, Name: "reefctl"}); err != nil {
		t.Fatal(err)
	}
	data, err := os.ReadFile(filepath.Join(dir, "notes.txt"))
	if err != nil || string(data) != "keep me" {
		t.Fatal("unrelated file changed")
	}
}

func TestInitRejectsUnsafeOptionsBeforeWriting(t *testing.T) {
	for _, name := range []string{"", "../escape", "UPPER", "a/b", "nul", "com1", "name-", "two--hyphens", "a\nrun: bad", strings.Repeat("a", 49)} {
		t.Run(name, func(t *testing.T) {
			dir := filepath.Join(t.TempDir(), "new-project")
			if _, err := Init(InitOptions{Directory: dir, Name: name}); err == nil {
				t.Fatal("accepted invalid name")
			}
			if _, err := os.Stat(dir); !os.IsNotExist(err) {
				t.Fatal("invalid options created destination")
			}
		})
	}
	for _, version := range []string{"latest", "main", "v1.0.0", "v0.1.0\nreplace x => y"} {
		if _, err := Init(InitOptions{Directory: filepath.Join(t.TempDir(), "new"), Name: "reefctl", SDKVersion: version}); err == nil {
			t.Fatalf("accepted version %q", version)
		}
	}
}

func TestInitRejectsSymlinkParent(t *testing.T) {
	dir, outside := t.TempDir(), t.TempDir()
	if err := os.Symlink(outside, filepath.Join(dir, ".agents")); err != nil {
		t.Skipf("symlink creation unavailable: %v", err)
	}
	for _, mode := range []string{ModeProject, ModeManifest, ModeTesting} {
		if _, err := Init(InitOptions{Directory: dir, Name: "reefctl", Mode: mode}); err == nil {
			t.Fatalf("%s mode accepted symlink parent", mode)
		}
	}
	if files := snapshot(t, outside); len(files) != 0 {
		t.Fatalf("wrote outside destination: %v", files)
	}
	if _, err := os.Stat(filepath.Join(dir, "project.json")); !os.IsNotExist(err) {
		t.Fatal("symlink conflict caused partial scaffold")
	}
}

func TestGeneratedProjectBuildsAndTests(t *testing.T) {
	if testing.Short() {
		t.Skip("compiles and tests a complete generated project")
	}
	dir := filepath.Join(t.TempDir(), "generated project")
	if _, err := Init(InitOptions{Directory: dir, Name: "reefctl"}); err != nil {
		t.Fatal(err)
	}
	root, err := filepath.Abs("../..")
	if err != nil {
		t.Fatal(err)
	}
	// A separate workspace exercises the current SDK without modifying the generated
	// go.mod or requiring network access. CI separately checks the published SDK pin.
	ctx, cancel := context.WithTimeout(context.Background(), 3*time.Minute)
	defer cancel()
	// Let Go use '.' and discover go.work from its actual working directory.
	// Absolute temp paths can have different symlink/short-name spellings on macOS
	// and Windows, which prevents Go from recognising an otherwise valid workspace.
	env := replaceEnv(os.Environ(), map[string]string{"GOWORK": "", "GOPROXY": "off", "GOSUMDB": "off"})
	setup := exec.CommandContext(ctx, "go", "work", "init", ".", root)
	setup.Dir, setup.Env = dir, env
	if output, err := setup.CombinedOutput(); err != nil {
		t.Fatalf("initialise test workspace: %v\n%s", err, output)
	}
	cmd := exec.CommandContext(ctx, "go", "test", "-v", "./...")
	cmd.Dir = dir
	cmd.Env = env
	output, err := cmd.CombinedOutput()
	if err != nil {
		t.Fatalf("generated project test failed: %v\n%s", err, output)
	}
	if !bytes.Contains(output, []byte("--- PASS: TestNativeExecutable")) {
		t.Fatalf("generated binary test did not run:\n%s", output)
	}
}

func snapshot(t *testing.T, directory string) map[string]string {
	t.Helper()
	files := map[string]string{}
	err := filepath.WalkDir(directory, func(name string, entry fs.DirEntry, err error) error {
		if err != nil {
			return err
		}
		if entry.IsDir() {
			return nil
		}
		data, err := os.ReadFile(name)
		if err != nil {
			return err
		}
		rel, err := filepath.Rel(directory, name)
		if err != nil {
			return err
		}
		files[rel] = string(data)
		return nil
	})
	if err != nil {
		t.Fatal(err)
	}
	return files
}

func TestManifestModeFitsAnExistingProject(t *testing.T) {
	dir := t.TempDir()
	for _, name := range []string{"README.md", "AGENTS.md", "go.mod"} {
		if err := os.WriteFile(filepath.Join(dir, name), []byte("existing project"), 0644); err != nil {
			t.Fatal(err)
		}
	}
	result, err := Init(InitOptions{Directory: dir, Name: "reefctl", Mode: ModeManifest})
	if err != nil {
		t.Fatal(err)
	}
	if result.Mode != ModeManifest || result.SDKVersion != "" || len(result.Files) != 3 {
		t.Fatalf("unexpected manifest scaffold: %+v", result)
	}
	for _, name := range []string{"README.md", "AGENTS.md", "go.mod"} {
		data, err := os.ReadFile(filepath.Join(dir, name))
		if err != nil || string(data) != "existing project" {
			t.Fatalf("changed %s: %v", name, err)
		}
	}
	data, err := os.ReadFile(filepath.Join(dir, "project.json"))
	if err != nil {
		t.Fatal(err)
	}
	if _, err := definition.Parse(data); err != nil {
		t.Fatal(err)
	}
	metadata, err := os.ReadFile(filepath.Join(dir, ".loop/scaffold.json"))
	if err != nil {
		t.Fatal(err)
	}
	if strings.Contains(string(metadata), "sdk_version") {
		t.Fatalf("manifest mode recorded an unused SDK: %s", metadata)
	}
}

func TestInitRejectsAmbiguousModesBeforeWriting(t *testing.T) {
	for _, opts := range []InitOptions{{Name: "reefctl", Mode: ModeTesting, SDKVersion: DefaultSDKVersion}, {Name: "reefctl", Mode: "unknown"}, {Name: "reefctl", Mode: ModeManifest, SDKVersion: DefaultSDKVersion}} {
		opts.Directory = filepath.Join(t.TempDir(), "new")
		if _, err := Init(opts); err == nil {
			t.Fatalf("accepted %+v", opts)
		}
		if _, err := os.Stat(opts.Directory); !os.IsNotExist(err) {
			t.Fatalf("invalid options touched destination: %v", err)
		}
	}
}

func TestTestingModePreservesExistingProjectWithoutRuntime(t *testing.T) {
	t.Setenv("PATH", "")
	for _, host := range []string{"go.mod", "package.json", "pyproject.toml"} {
		t.Run(host, func(t *testing.T) {
			dir := t.TempDir()
			for _, name := range []string{host, "README.md", "AGENTS.md", "project.json"} {
				if err := os.WriteFile(filepath.Join(dir, name), []byte("existing unrelated content"), 0644); err != nil {
					t.Fatal(err)
				}
			}
			before := snapshot(t, dir)
			result, err := Init(InitOptions{Directory: dir, Name: "reef", Mode: ModeTesting})
			if err != nil {
				t.Fatal(err)
			}
			if result.Mode != ModeTesting || result.SDKVersion != "" || len(result.Files) != 1 || result.Files[0] != ".agents/skills/reef-native-test/SKILL.md" {
				t.Fatalf("unexpected testing scaffold: %+v", result)
			}
			after := snapshot(t, dir)
			if len(after) != len(before)+1 {
				t.Fatalf("testing mode created unrelated files: %v", result.Files)
			}
			for name, content := range before {
				if after[name] != content {
					t.Fatalf("changed host file %s", name)
				}
			}
			if _, err := Init(InitOptions{Directory: dir, Name: "reef", Mode: ModeTesting}); err == nil {
				t.Fatal("repeated installation must preserve the existing skill")
			}
			if !reflect.DeepEqual(after, snapshot(t, dir)) {
				t.Fatal("conflict modified the project")
			}
		})
	}
}
