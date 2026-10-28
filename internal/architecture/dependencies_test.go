package architecture

import (
	"encoding/json"
	"io"
	"os/exec"
	"strings"
	"testing"
)

// Every production package has an explicit internal dependency budget.
// Tests may cross boundaries to exercise integration behaviour.
func TestPackageBoundaries(t *testing.T) {
	const root = "github.com/domhauton/loop-cli-adk/"
	allowed := map[string][]string{
		"pkg/operation":         {},
		"internal/definition":   {},
		"internal/execution":    {"pkg/operation"},
		"internal/httpapi":      {"pkg/operation"},
		"pkg/project":           {"internal/definition", "internal/execution", "internal/httpapi", "pkg/operation"},
		"pkg/cli":               {"pkg/project", "pkg/operation"},
		"pkg/clitest":           {"pkg/cli", "pkg/project"},
		"internal/authoring":    {"internal/definition"},
		"cmd/loop":              {"internal/authoring", "pkg/cli", "pkg/project", "pkg/operation"},
		"examples/demo/server":  {},
		"internal/architecture": {},
	}
	cmd := exec.Command("go", "list", "-json", "./...")
	cmd.Dir = "../.."
	output, err := cmd.Output()
	if err != nil {
		t.Fatal(err)
	}
	d := json.NewDecoder(strings.NewReader(string(output)))
	for {
		var p struct {
			ImportPath string
			Imports    []string
		}
		if err := d.Decode(&p); err == io.EOF {
			break
		} else if err != nil {
			t.Fatal(err)
		}
		name := strings.TrimPrefix(p.ImportPath, root)
		budget, ok := allowed[name]
		if !ok {
			t.Errorf("package %s needs an explicit dependency contract", name)
			continue
		}
		for _, dep := range p.Imports {
			if !strings.HasPrefix(dep, root) {
				continue
			}
			dep = strings.TrimPrefix(dep, root)
			valid := false
			for _, a := range budget {
				if dep == a {
					valid = true
				}
			}
			if !valid {
				t.Errorf("forbidden dependency: %s -> %s", name, dep)
			}
		}
	}
}
