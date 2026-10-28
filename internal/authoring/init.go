package authoring

import (
	"bytes"
	"embed"
	"encoding/json"
	"errors"
	"fmt"
	"go/format"
	"io/fs"
	"os"
	"path"
	"path/filepath"
	"regexp"
	"sort"
	"strings"
	"text/template"

	"github.com/domhauton/loop-cli-adk/internal/definition"
)

// DefaultSDKVersion is an immutable, published Go module revision. Until the first
// release tag exists, this pins the six-platform-tested runtime from 28 October 2026.
const DefaultSDKVersion = "v0.0.0-20261028225343-2b0eb32ab06c"

// TemplateVersion identifies the scaffold recipe without implying automatic upgrades.
const TemplateVersion = 4

//go:embed templates/*
var scaffoldTemplates embed.FS

// ModeProject scaffolds a standalone CLI, tests, skills and release workflows.
const ModeProject = "project"

// ModeManifest scaffolds a manifest and inspection skill for an installed Loop.
const ModeManifest = "manifest"

// InitOptions selects a local destination, mode, name and optional SDK version.
// Initialisation does not invoke Go, inspect credentials or access the network.
type InitOptions struct {
	Mode       string
	Directory  string
	Name       string
	SDKVersion string
}

// InitResult lists the created files relative to Directory, in stable order.
type InitResult struct {
	Mode            string   `json:"mode"`
	Directory       string   `json:"directory"`
	Name            string   `json:"name"`
	SDKVersion      string   `json:"sdk_version,omitempty"`
	TemplateVersion int      `json:"template_version"`
	Files           []string `json:"files"`
}

type scaffoldData struct{ Name, SDKVersion, BaseURLEnv, TokenEnv string }

// Init writes a complete project scaffold after validating every destination.
// Existing files, including identical files from a previous run, are never replaced.
func Init(opts InitOptions) (InitResult, error) {
	var result InitResult
	if opts.Mode == "" {
		opts.Mode = ModeProject
	}
	switch opts.Mode {
	case ModeProject:
		if opts.SDKVersion == "" {
			opts.SDKVersion = DefaultSDKVersion
		}
	case ModeManifest:
		if opts.SDKVersion != "" {
			return result, fmt.Errorf("manifest mode uses the installed Loop and cannot select an SDK version")
		}
	default:
		return result, fmt.Errorf("mode must be project or manifest")
	}
	files, err := renderScaffold(opts)
	if err != nil {
		return result, err
	}
	if opts.Directory == "" {
		opts.Directory = "."
	}
	directory, err := filepath.Abs(opts.Directory)
	if err != nil {
		return result, fmt.Errorf("resolve destination: %w", err)
	}
	if info, err := os.Lstat(directory); err == nil && (info.Mode()&os.ModeSymlink != 0 || !info.IsDir()) {
		return result, fmt.Errorf("destination must be a directory, not a file or symlink")
	} else if err != nil && !errors.Is(err, fs.ErrNotExist) {
		return result, fmt.Errorf("inspect destination: %w", err)
	}
	if err := os.MkdirAll(directory, 0755); err != nil {
		return result, fmt.Errorf("create destination: %w", err)
	}
	root, err := os.OpenRoot(directory)
	if err != nil {
		return result, fmt.Errorf("open destination: %w", err)
	}
	defer root.Close()
	names := make([]string, 0, len(files))
	for name := range files {
		names = append(names, name)
	}
	sort.Strings(names)
	// Validate all paths first, so a late README/workflow conflict leaves files untouched.
	for _, name := range names {
		if _, err := root.Lstat(name); err == nil {
			return result, fmt.Errorf("refusing to overwrite %s", name)
		} else if !errors.Is(err, fs.ErrNotExist) {
			return result, fmt.Errorf("inspect %s: %w", name, err)
		}
		for parent := path.Dir(name); parent != "."; parent = path.Dir(parent) {
			info, err := root.Lstat(parent)
			if errors.Is(err, fs.ErrNotExist) {
				continue
			}
			if err != nil {
				return result, fmt.Errorf("inspect %s: %w", parent, err)
			}
			if info.Mode()&os.ModeSymlink != 0 || !info.IsDir() {
				return result, fmt.Errorf("parent %s must be a directory, not a file or symlink", parent)
			}
		}
	}
	created := make([]string, 0, len(names))
	complete := false
	defer func() {
		if !complete {
			for _, name := range created {
				_ = root.Remove(name)
			}
		}
	}()
	for _, name := range names {
		if err := root.MkdirAll(path.Dir(name), 0755); err != nil {
			return result, fmt.Errorf("create parent for %s: %w", name, err)
		}
		file, err := root.OpenFile(name, os.O_WRONLY|os.O_CREATE|os.O_EXCL, 0644)
		if err != nil {
			return result, fmt.Errorf("create %s: %w", name, err)
		}
		created = append(created, name)
		_, writeErr := file.Write(files[name])
		closeErr := file.Close()
		if err := errors.Join(writeErr, closeErr); err != nil {
			return result, fmt.Errorf("write %s: %w", name, err)
		}
	}
	complete = true
	return InitResult{Mode: opts.Mode, Directory: directory, Name: opts.Name, SDKVersion: opts.SDKVersion, TemplateVersion: TemplateVersion, Files: names}, nil
}

func renderScaffold(opts InitOptions) (map[string][]byte, error) {
	if len(opts.Name) > 48 || !regexp.MustCompile(`^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$`).MatchString(opts.Name) {
		return nil, fmt.Errorf("name must be 1-48 lowercase letters or digits with single internal hyphens, starting with a letter")
	}
	if regexp.MustCompile(`^(con|prn|aux|nul|com[1-9]|lpt[1-9])$`).MatchString(opts.Name) {
		return nil, fmt.Errorf("name %q is reserved on Windows", opts.Name)
	}
	if opts.Mode == ModeProject && !regexp.MustCompile(`^v0\.[0-9]+\.[0-9]+(?:-[0-9A-Za-z.-]+)?$`).MatchString(opts.SDKVersion) {
		return nil, fmt.Errorf("sdk-version must be an explicit v0 semantic version, not a branch or latest")
	}
	prefix := strings.ToUpper(strings.ReplaceAll(opts.Name, "-", "_"))
	data := scaffoldData{Name: opts.Name, SDKVersion: opts.SDKVersion, BaseURLEnv: prefix + "_API_URL", TokenEnv: prefix + "_API_TOKEN"}
	m := definition.Manifest{SchemaVersion: 1, Name: opts.Name, Description: "Inspect the " + opts.Name + " project", API: definition.API{BaseURLEnv: data.BaseURLEnv, TokenEnv: data.TokenEnv}, Commands: []definition.Command{{Name: "status get", Description: "Read the API health endpoint", HTTP: definition.HTTP{Method: "GET", Path: "/health"}}}}
	manifest, err := json.MarshalIndent(m, "", "  ")
	if err != nil {
		return nil, fmt.Errorf("encode manifest: %w", err)
	}
	if _, err := definition.Parse(manifest); err != nil {
		return nil, fmt.Errorf("validate generated manifest: %w", err)
	}
	metadata, err := json.MarshalIndent(struct {
		Mode            string `json:"mode"`
		TemplateVersion int    `json:"template_version"`
		SDKVersion      string `json:"sdk_version,omitempty"`
	}{opts.Mode, TemplateVersion, opts.SDKVersion}, "", "  ")
	if err != nil {
		return nil, fmt.Errorf("encode scaffold metadata: %w", err)
	}
	files := map[string][]byte{"project.json": append(manifest, '\n'), ".loop/scaffold.json": append(metadata, '\n')}
	if opts.SDKVersion == DefaultSDKVersion {
		// Verified against the public Go checksum database for the bootstrap revision.
		// Other pins resolve their own checksums with go mod tidy before committing.
		files["go.sum"] = []byte(modulePath + " " + DefaultSDKVersion + " h1:nqHx9l9j+iahNbrV7LB2xIwQqwrUMcfpnqvcdeaR3iM=\n" + modulePath + " " + DefaultSDKVersion + "/go.mod h1:u7e1313Ner7uIpYl6LoGo2Rn3JV1PtFKekpq7kSFGl8=\n")
	}
	templates := map[string]string{
		"go.mod": "go.mod.tmpl", "main_test.go": "main_test.go.tmpl",
		"contracts_test.go": "contracts_test.go.tmpl",
		"README.md":         "README.md.tmpl", "AGENTS.md": "AGENTS.md.tmpl", ".gitignore": "gitignore.tmpl",
		".goreleaser.yaml": "goreleaser.yml.tmpl", ".github/workflows/ci.yml": "ci.yml.tmpl", ".github/workflows/release.yml": "release.yml.tmpl",
		".agents/skills/" + opts.Name + "-develop/SKILL.md": "develop-skill.md.tmpl",
		".agents/skills/" + opts.Name + "-release/SKILL.md": "release-skill.md.tmpl",
		".agents/skills/" + opts.Name + "-test/SKILL.md":    "test-skill.md.tmpl",
	}
	if opts.Mode == ModeManifest {
		templates = map[string]string{".agents/skills/" + opts.Name + "-inspect/SKILL.md": "manifest-skill.md.tmpl"}
	} else {
		files["main.go"] = []byte(projectMain)
	}
	for destination, source := range templates {
		content, err := scaffoldTemplates.ReadFile("templates/" + source)
		if err != nil {
			return nil, fmt.Errorf("read template %s: %w", source, err)
		}
		// Separate delimiters preserve GitHub Actions and GoReleaser expressions verbatim.
		t, err := template.New(source).Delims("[[", "]]").Option("missingkey=error").Parse(string(content))
		if err != nil {
			return nil, fmt.Errorf("parse template %s: %w", source, err)
		}
		var output bytes.Buffer
		if err := t.Execute(&output, data); err != nil {
			return nil, fmt.Errorf("render template %s: %w", source, err)
		}
		files[destination] = output.Bytes()
	}
	for name, content := range files {
		if strings.HasSuffix(name, ".go") {
			formatted, err := format.Source(content)
			if err != nil {
				return nil, fmt.Errorf("format generated %s: %w", name, err)
			}
			files[name] = formatted
		}
	}
	return files, nil
}
