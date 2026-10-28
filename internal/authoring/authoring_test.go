package authoring

import (
	"bytes"
	"context"
	"fmt"
	"net/http"
	"net/http/httptest"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strings"
	"testing"
	"time"

	"github.com/domhauton/loop-cli-adk/pkg/cli"
	"github.com/domhauton/loop-cli-adk/pkg/project"
)

func TestBuiltCLIEqualsLocalRunner(t *testing.T) {
	if testing.Short() {
		t.Skip("compiles and executes a native project binary")
	}
	root, err := filepath.Abs("../..")
	if err != nil {
		t.Fatal(err)
	}
	manifest, err := os.ReadFile(filepath.Join(root, "examples/demo/project.json"))
	if err != nil {
		t.Fatal(err)
	}
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/users" || r.URL.Query().Get("name") != "Ada & Grace" || r.Header.Get("Authorization") != "Bearer fixture-token" {
			t.Errorf("wrong request path/query or credential")
		}
		fmt.Fprint(w, `{"users":[{"id":"1","name":"Ada & Grace"}]}`)
	}))
	defer server.Close()
	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Minute)
	defer cancel()
	name := "democtl"
	if runtime.GOOS == "windows" {
		name += ".exe"
	}
	output := filepath.Join(t.TempDir(), "path with spaces", name)
	// Reproduce Windows Git checkouts on every platform, including a spaced SDK path.
	sdkRoot := filepath.Join(t.TempDir(), "sdk checkout")
	for _, dir := range []string{"pkg", "internal"} {
		if err := os.CopyFS(filepath.Join(sdkRoot, dir), os.DirFS(filepath.Join(root, dir))); err != nil {
			t.Fatal(err)
		}
	}
	module, err := os.ReadFile(filepath.Join(root, "go.mod"))
	if err != nil {
		t.Fatal(err)
	}
	module = bytes.ReplaceAll(bytes.ReplaceAll(module, []byte("\r\n"), []byte("\n")), []byte("\n"), []byte("\r\n"))
	if err := os.WriteFile(filepath.Join(sdkRoot, "go.mod"), module, 0600); err != nil {
		t.Fatal(err)
	}
	if err := Build(ctx, manifest, BuildOptions{Output: output, SDKDir: sdkRoot}); err != nil {
		t.Fatal(err)
	}
	env := map[string]string{"DEMO_API_URL": server.URL, "DEMO_API_TOKEN": "fixture-token"}
	p, err := project.New(manifest, func(k string) string { return env[k] })
	if err != nil {
		t.Fatal(err)
	}
	for _, args := range [][]string{{"describe"}, {"users", "list", "--input", `{"name":"Ada & Grace"}`}, {"users", "list", "--input", `{"extra":"x"}`}, {"missing"}} {
		var localOut, localErr, binaryOut, binaryErr bytes.Buffer
		localStatus := cli.Run(ctx, p, args, &localOut, &localErr)
		cmd := exec.CommandContext(ctx, output, args...)
		cmd.Env = replaceEnv(os.Environ(), env)
		cmd.Stdout = &binaryOut
		cmd.Stderr = &binaryErr
		binaryStatus := 0
		if err := cmd.Run(); err != nil {
			if exit, ok := err.(*exec.ExitError); ok {
				binaryStatus = exit.ExitCode()
			} else {
				t.Fatal(err)
			}
		}
		if localStatus != binaryStatus || localOut.String() != binaryOut.String() || localErr.String() != binaryErr.String() {
			t.Fatalf("args=%v local=%d,%q,%q binary=%d,%q,%q", args, localStatus, &localOut, &localErr, binaryStatus, &binaryOut, &binaryErr)
		}
	}
	// Build staging must not leak files into the output directory.
	files, err := os.ReadDir(filepath.Dir(output))
	if err != nil {
		t.Fatal(err)
	}
	if len(files) != 1 {
		t.Fatalf("unexpected build leftovers: %v", files)
	}
}

func TestBuildRequiresExplicitSDK(t *testing.T) {
	data, err := os.ReadFile("../../examples/demo/project.json")
	if err != nil {
		t.Fatal(err)
	}
	if err := Build(context.Background(), data, BuildOptions{Output: "unused"}); err == nil || !strings.Contains(err.Error(), "exactly one") {
		t.Fatalf("expected explicit SDK source error, got %v", err)
	}
}
