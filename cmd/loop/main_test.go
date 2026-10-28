package main

import (
	"bytes"
	"context"
	"encoding/json"
	"os"
	"path/filepath"
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
