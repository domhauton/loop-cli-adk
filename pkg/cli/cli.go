// Package cli renders a project through a non-interactive command-line frontend.
package cli

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"strings"

	"github.com/domhauton/loop-cli-adk/pkg/operation"
	"github.com/domhauton/loop-cli-adk/pkg/project"
)

// Run executes CLI arguments. Results go to stdout and structured errors to stderr.
// Discovery and help never require configured API credentials.
func Run(ctx context.Context, p *project.Project, args []string, stdout, stderr io.Writer) int {
	if len(args) == 0 || (len(args) == 1 && (args[0] == "--help" || args[0] == "help")) {
		fmt.Fprintf(stdout, "%s - %s\n\nCommands:\n", p.Name(), p.Description())
		for _, d := range p.Describe() {
			fmt.Fprintf(stdout, "  %s  %s\n", d.Name, d.Description)
		}
		fmt.Fprintln(stdout, "\nUse describe [command] for JSON discovery. Invoke with --input '{...}'.")
		return 0
	}
	if args[0] == "describe" {
		var value any = p.Describe()
		if len(args) > 1 {
			name := strings.Join(args[1:], " ")
			found := false
			for _, d := range p.Describe() {
				if d.Name == name {
					value = d
					found = true
					break
				}
			}
			if !found {
				return WriteError(stderr, operation.NewError("unknown_command", "unknown command: "+name, nil))
			}
		}
		if err := json.NewEncoder(stdout).Encode(value); err != nil {
			return WriteError(stderr, operation.NewError("output", "cannot write command description", err))
		}
		return 0
	}
	input := "{}"
	words := args
	for i, arg := range args {
		if strings.HasPrefix(arg, "--") {
			if arg != "--input" || i+2 != len(args) {
				return WriteError(stderr, operation.NewError("usage", "expected command words followed by --input JSON", nil))
			}
			input = args[i+1]
			words = args[:i]
			break
		}
	}
	result, err := p.Execute(ctx, strings.Join(words, " "), json.RawMessage(input))
	if err != nil {
		return WriteError(stderr, err)
	}
	var compact bytes.Buffer
	if err := json.Compact(&compact, result); err != nil {
		return WriteError(stderr, operation.NewError("invalid_response", "operation returned invalid JSON", err))
	}
	compact.WriteByte('\n')
	if _, err := stdout.Write(compact.Bytes()); err != nil {
		return WriteError(stderr, operation.NewError("output", "cannot write operation result", err))
	}
	return 0
}

// WriteError emits the public error contract and returns a process exit code.
func WriteError(w io.Writer, err error) int {
	public := operation.NewError("internal", "unexpected internal error", nil)
	var known *operation.Error
	if errors.As(err, &known) {
		public = known
	}
	_ = json.NewEncoder(w).Encode(errorEnvelope{Error: publicError{
		Code: public.Code, Message: public.Message, Details: public.Details,
	}})

	switch public.Code {
	case "invalid_manifest", "configuration", "invalid_input", "unknown_command", "usage":
		return 2
	}
	return 1
}

type publicError struct {
	Code    string            `json:"code"`
	Message string            `json:"message"`
	Details map[string]string `json:"details,omitempty"`
}

type errorEnvelope struct {
	Error publicError `json:"error"`
}
