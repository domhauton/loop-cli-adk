package main

import (
	"bytes"
	"context"
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestAuthoringCommandArguments(t *testing.T) {
	data, err := os.ReadFile("../../examples/demo/project.json")
	if err != nil {
		t.Fatal(err)
	}
	path := filepath.Join(t.TempDir(), "project with spaces.json")
	if err := os.WriteFile(path, data, 0600); err != nil {
		t.Fatal(err)
	}
	for _, tc := range []struct {
		name   string
		args   []string
		status int
	}{
		{"check", []string{"check", "--manifest", path}, 0},
		{"describe", []string{"run", "--manifest", path, "--", "describe"}, 0},
		{"extra argument", []string{"check", "--manifest", path, "extra"}, 2},
		{"missing file", []string{"check", "--manifest", filepath.Join(t.TempDir(), "missing")}, 2},
		{"bad flag", []string{"run", "--typo"}, 2},
	} {
		t.Run(tc.name, func(t *testing.T) {
			var out, errout bytes.Buffer
			status := execute(context.Background(), tc.args, &out, &errout)
			if status != tc.status {
				t.Fatalf("status=%d stdout=%s stderr=%s", status, &out, &errout)
			}
			if status == 0 && (!json.Valid(out.Bytes()) || errout.Len() != 0) {
				t.Fatalf("expected JSON result only: %q %q", &out, &errout)
			}
			if status != 0 && (out.Len() != 0 || !json.Valid(errout.Bytes())) {
				t.Fatalf("expected JSON error only: %q %q", &out, &errout)
			}
		})
	}
}

func TestInitCommand(t *testing.T) {
	dir := filepath.Join(t.TempDir(), "cli project")
	var out, errout bytes.Buffer
	status := execute(context.Background(), []string{"init", "--name", "reefctl", "--dir", dir}, &out, &errout)
	if status != 0 || errout.Len() != 0 {
		t.Fatalf("status=%d stderr=%s", status, &errout)
	}
	var result struct {
		Directory string   `json:"directory"`
		Files     []string `json:"files"`
	}
	if err := json.Unmarshal(out.Bytes(), &result); err != nil {
		t.Fatal(err)
	}
	if result.Directory != dir || len(result.Files) == 0 {
		t.Fatalf("unexpected result: %s", &out)
	}
	out.Reset()
	errout.Reset()
	status = execute(context.Background(), []string{"init", "--name", "reefctl", "--dir", dir}, &out, &errout)
	if status != 2 || out.Len() != 0 || !json.Valid(errout.Bytes()) {
		t.Fatalf("repeat init: status=%d stdout=%s stderr=%s", status, &out, &errout)
	}
}

func TestAuthoringHelpNeedsNoManifest(t *testing.T) {
	for _, command := range []string{"check", "run", "build"} {
		t.Run(command, func(t *testing.T) {
			var out, diagnostic bytes.Buffer
			status := execute(t.Context(), []string{command, "--manifest", filepath.Join(t.TempDir(), "missing"), "--help"}, &out, &diagnostic)
			if status != 0 || diagnostic.Len() != 0 || !strings.Contains(out.String(), "loop "+command) {
				t.Fatalf("status=%d stdout=%s stderr=%s", status, &out, &diagnostic)
			}
		})
	}
}

func TestManifestInitCommand(t *testing.T) {
	dir := t.TempDir()
	var out, diagnostic bytes.Buffer
	status := execute(t.Context(), []string{"init", "--mode", "manifest", "--name", "energy", "--dir", dir}, &out, &diagnostic)
	if status != 0 || diagnostic.Len() != 0 {
		t.Fatalf("status=%d stderr=%s", status, &diagnostic)
	}
	var result struct {
		Mode  string   `json:"mode"`
		Files []string `json:"files"`
	}
	if err := json.Unmarshal(out.Bytes(), &result); err != nil {
		t.Fatal(err)
	}
	if result.Mode != "manifest" || len(result.Files) != 3 {
		t.Fatalf("unexpected result: %s", &out)
	}
}
