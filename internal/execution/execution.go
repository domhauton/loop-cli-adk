// Package execution validates and dispatches unary operations without transport knowledge.
package execution

import (
	"context"
	"encoding/json"
	"fmt"
	"sort"

	"github.com/domhauton/loop-cli-adk/pkg/operation"
)

// MaxInputBytes caps one invocation's JSON input at 1 MiB.
const MaxInputBytes = 1 << 20

// Entry pairs one descriptor with its explicitly registered handler.
type Entry struct {
	Descriptor operation.Descriptor
	Handler    operation.Handler
}

// Executor owns an immutable registry built at construction time.
type Executor struct{ entries map[string]Entry }

// New constructs a registry, rejecting duplicate or incomplete registrations.
func New(entries []Entry) (*Executor, error) {
	e := &Executor{entries: make(map[string]Entry, len(entries))}
	for _, entry := range entries {
		if entry.Descriptor.Name == "" || entry.Handler == nil {
			return nil, fmt.Errorf("incomplete operation registration")
		}
		if _, ok := e.entries[entry.Descriptor.Name]; ok {
			return nil, fmt.Errorf("duplicate operation %q", entry.Descriptor.Name)
		}
		entry.Descriptor = clone(entry.Descriptor)
		e.entries[entry.Descriptor.Name] = entry
	}
	return e, nil
}

func clone(d operation.Descriptor) operation.Descriptor {
	input := make(map[string]operation.Parameter, len(d.Input))
	for k, v := range d.Input {
		input[k] = v
	}
	d.Input = input
	return d
}

// Describe returns detached descriptors in stable command order.
func (e *Executor) Describe() []operation.Descriptor {
	out := make([]operation.Descriptor, 0, len(e.entries))
	for _, entry := range e.entries {
		out = append(out, clone(entry.Descriptor))
	}
	sort.Slice(out, func(i, j int) bool { return out[i].Name < out[j].Name })
	return out
}

// Execute validates input before calling the selected handler.
func (e *Executor) Execute(ctx context.Context, name string, input json.RawMessage) (json.RawMessage, error) {
	entry, ok := e.entries[name]
	if !ok {
		return nil, operation.NewError("unknown_command", "unknown command: "+name, nil)
	}
	if len(input) > MaxInputBytes {
		return nil, operation.NewError("invalid_input", fmt.Sprintf("input size %d exceeds %d bytes", len(input), MaxInputBytes), nil)
	}
	var raw map[string]json.RawMessage
	if err := json.Unmarshal(input, &raw); err != nil || raw == nil {
		return nil, operation.NewError("invalid_input", "input must be a JSON object", err)
	}
	values := make(map[string]string, len(raw))
	for key, value := range raw {
		if _, ok := entry.Descriptor.Input[key]; !ok {
			return nil, operation.NewError("invalid_input", "unknown input field: "+key, nil)
		}
		var s string
		if string(value) == "null" {
			return nil, operation.NewError("invalid_input", "input field must be a string: "+key, nil)
		}
		if err := json.Unmarshal(value, &s); err != nil {
			return nil, operation.NewError("invalid_input", "input field must be a string: "+key, err)
		}
		values[key] = s
	}
	for key, p := range entry.Descriptor.Input {
		if _, ok := values[key]; p.Required && !ok {
			return nil, operation.NewError("invalid_input", "missing required input: "+key, nil)
		}
	}
	if err := ctx.Err(); err != nil {
		return nil, operation.NewError("cancelled", "operation cancelled", err)
	}
	result, err := entry.Handler(ctx, values)
	if err != nil {
		return nil, err
	}
	if len(result) > operation.MaxResultBytes {
		return nil, operation.NewError("response_limit", fmt.Sprintf("operation result exceeds %d bytes", operation.MaxResultBytes), nil)
	}
	if !json.Valid(result) {
		return nil, operation.NewError("invalid_response", "operation returned invalid JSON", nil)
	}
	return result, nil
}
