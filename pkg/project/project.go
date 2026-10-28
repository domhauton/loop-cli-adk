// Package project is the composition facade shared by local and embedded CLIs.
package project

import (
	"context"
	"encoding/json"

	"github.com/domhauton/loop-cli-adk/internal/definition"
	"github.com/domhauton/loop-cli-adk/internal/execution"
	"github.com/domhauton/loop-cli-adk/internal/httpapi"
	"github.com/domhauton/loop-cli-adk/pkg/operation"
)

// Project is a validated definition bound to executable operations.
type Project struct {
	name        string
	description string
	executor    *execution.Executor
}

// New composes a project without accessing the network or reading credentials.
// getenv is consulted only when an operation runs. It must be safe for concurrent calls.
func New(manifest []byte, getenv func(string) string) (*Project, error) {
	m, err := definition.Parse(manifest)
	if err != nil {
		return nil, operation.NewError("invalid_manifest", "invalid project manifest: "+err.Error(), err)
	}
	if getenv == nil {
		return nil, operation.NewError("configuration", "environment reader is required", nil)
	}
	entries := make([]execution.Entry, 0, len(m.Commands))
	for _, c := range m.Commands {
		params := make(map[string]operation.Parameter, len(c.Input))
		for name, p := range c.Input {
			params[name] = operation.Parameter{Type: p.Type, Description: p.Description, Required: p.Required}
		}
		entries = append(entries, execution.Entry{Descriptor: operation.Descriptor{Name: c.Name, Description: c.Description, Input: params}, Handler: httpapi.Bind(httpapi.Config{Path: c.HTTP.Path, Query: c.HTTP.Query, BaseURLEnv: m.API.BaseURLEnv, TokenEnv: m.API.TokenEnv, Getenv: getenv})})
	}
	e, err := execution.New(entries)
	if err != nil {
		return nil, operation.NewError("configuration", "cannot register project operations", err)
	}
	return &Project{name: m.Name, description: m.Description, executor: e}, nil
}

// Name returns the project's executable name.
func (p *Project) Name() string { return p.name }

// Description returns the project's help description.
func (p *Project) Description() string { return p.description }

// Describe returns detached operation descriptors in stable order.
func (p *Project) Describe() []operation.Descriptor { return p.executor.Describe() }

// Execute validates input and invokes a named operation.
func (p *Project) Execute(ctx context.Context, name string, input json.RawMessage) (json.RawMessage, error) {
	return p.executor.Execute(ctx, name, input)
}
