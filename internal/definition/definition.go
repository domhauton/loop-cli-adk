// Package definition owns the persisted manifest, independent of live clients.
package definition

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/url"
	"regexp"
	"strings"
)

// MaxManifestBytes bounds configuration read from outside the process (1 MiB).
const MaxManifestBytes = 1 << 20

var namePattern = regexp.MustCompile(`^[a-z][a-z0-9-]*$`)
var envPattern = regexp.MustCompile(`^[A-Za-z_][A-Za-z0-9_]*$`)

// Manifest is the versioned on-disk project definition.
type Manifest struct {
	SchemaVersion int       `json:"schema_version"`
	Name          string    `json:"name"`
	Description   string    `json:"description"`
	API           API       `json:"api"`
	Commands      []Command `json:"commands"`
}

// API contains environment variable names, never credential values.
type API struct {
	BaseURLEnv string `json:"base_url_env"`
	TokenEnv   string `json:"token_env,omitempty"`
}

// Command declares a discoverable operation and its HTTP binding.
type Command struct {
	Name        string               `json:"name"`
	Description string               `json:"description"`
	Input       map[string]Parameter `json:"input,omitempty"`
	HTTP        HTTP                 `json:"http"`
}

// Parameter is the serialised input declaration.
type Parameter struct {
	Type        string `json:"type"`
	Description string `json:"description,omitempty"`
	Required    bool   `json:"required,omitempty"`
}

// HTTP maps input names to query parameter names for a read operation.
type HTTP struct {
	Method string            `json:"method"`
	Path   string            `json:"path"`
	Query  map[string]string `json:"query,omitempty"`
}

// Parse rejects unknown fields and unsupported behaviour before any API call.
func Parse(data []byte) (Manifest, error) {
	var m Manifest
	if len(data) > MaxManifestBytes {
		return m, fmt.Errorf("manifest size %d exceeds %d bytes", len(data), MaxManifestBytes)
	}
	d := json.NewDecoder(bytes.NewReader(data))
	d.DisallowUnknownFields()
	if err := d.Decode(&m); err != nil {
		return m, fmt.Errorf("decode manifest: %w", err)
	}
	if err := d.Decode(new(any)); err != io.EOF {
		return m, fmt.Errorf("manifest must contain exactly one JSON object")
	}
	if m.SchemaVersion != 1 {
		return m, fmt.Errorf("schema_version must be 1")
	}
	if !namePattern.MatchString(m.Name) {
		return m, fmt.Errorf("name must be a lowercase executable name")
	}
	if !envPattern.MatchString(m.API.BaseURLEnv) {
		return m, fmt.Errorf("api.base_url_env must name an environment variable")
	}
	if m.API.TokenEnv != "" && !envPattern.MatchString(m.API.TokenEnv) {
		return m, fmt.Errorf("api.token_env must name an environment variable")
	}
	if len(m.Commands) == 0 {
		return m, fmt.Errorf("commands must not be empty")
	}
	seen := map[string]bool{}
	for _, c := range m.Commands {
		parts := strings.Split(c.Name, " ")
		for _, part := range parts {
			if !namePattern.MatchString(part) {
				return m, fmt.Errorf("invalid command name %q", c.Name)
			}
		}
		if parts[0] == "describe" || parts[0] == "help" {
			return m, fmt.Errorf("command %q uses a reserved name", c.Name)
		}
		if seen[c.Name] {
			return m, fmt.Errorf("duplicate command %q", c.Name)
		}
		seen[c.Name] = true
		if c.HTTP.Method != "GET" {
			return m, fmt.Errorf("command %q: first slice supports GET only", c.Name)
		}
		u, err := url.Parse(c.HTTP.Path)
		if err != nil || !strings.HasPrefix(c.HTTP.Path, "/") || strings.HasPrefix(c.HTTP.Path, "//") || u == nil || u.RawQuery != "" || u.Fragment != "" || u.Host != "" || strings.Contains(c.HTTP.Path, "\\") || strings.Contains(c.HTTP.Path, "#") || strings.Contains(c.HTTP.Path, "?") {
			return m, fmt.Errorf("command %q: path must be an absolute URL path without query or fragment", c.Name)
		}
		for name, p := range c.Input {
			if !namePattern.MatchString(name) || p.Type != "string" {
				return m, fmt.Errorf("command %q: input %q must have a valid name and type string", c.Name, name)
			}
			if c.HTTP.Query[name] == "" {
				return m, fmt.Errorf("command %q: input %q needs a query mapping", c.Name, name)
			}
		}
		queryNames := map[string]bool{}
		for input, query := range c.HTTP.Query {
			if _, ok := c.Input[input]; !ok {
				return m, fmt.Errorf("command %q: query maps unknown input %q", c.Name, input)
			}
			if query == "" || queryNames[query] {
				return m, fmt.Errorf("command %q: empty or duplicate query name", c.Name)
			}
			queryNames[query] = true
		}
	}
	return m, nil
}
