// Package clitest checks project CLI contracts against isolated HTTP fixtures.
// It is development support: production entry points must not import it.
package clitest

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"net/http"
	"net/http/httptest"
	"net/url"
	"strings"
	"sync/atomic"
	"time"

	"github.com/domhauton/loop-cli-adk/pkg/cli"
	"github.com/domhauton/loop-cli-adk/pkg/project"
)

const fixtureToken = "loop-fixture-token"
const privateDetail = "loop-fixture-private"

// Environment identifies the manifest's environment references, never real values.
// Prefix is an optional API base path, for example /admin/v1.
type Environment struct{ BaseURL, Token, Prefix string }

// Request is the independently expected HTTP request. Path is URL-escaped.
// Query is compared as decoded values, including duplicate values.
type Request struct {
	Path  string
	Query url.Values
}

// Response supplies the fixture's status and body. Status defaults to 200.
// A missing error body uses a private sentinel to check diagnostic redaction.
type Response struct {
	Status int
	Body   string
}

// Case checks CLI arguments, HTTP mapping and the public output contract.
// A nil Request requires that no HTTP request occurs. Successful output must be
// the fixture's JSON body, ignoring whitespace. Errors require WantError and a
// non-zero WantExit. Tests for transformations should use their own assertions.
type Case struct {
	Name      string
	Args      []string
	Request   *Request
	Response  Response
	WantError string
	WantExit  int
}

// Check runs independent local fixtures and returns named failures. It never
// consults the process environment. Credentials are fixed synthetic values.
// Context cancellation stops remaining cases; each invocation is capped at 10s.
func Check(ctx context.Context, manifest []byte, env Environment, cases ...Case) error {
	if env.BaseURL == "" || env.BaseURL == env.Token {
		return fmt.Errorf("fixture needs distinct environment names and a base URL name")
	}
	if env.Prefix != "" && (!strings.HasPrefix(env.Prefix, "/") || strings.ContainsAny(env.Prefix, "?#")) {
		return fmt.Errorf("fixture prefix must be an API path")
	}
	if len(cases) == 0 {
		return fmt.Errorf("at least one contract case is required")
	}
	var failures []error
	for _, c := range cases {
		if err := ctx.Err(); err != nil {
			return errors.Join(append(failures, err)...)
		}
		if err := check(ctx, manifest, env, c); err != nil {
			failures = append(failures, fmt.Errorf("%s: %w", c.Name, err))
		}
	}
	return errors.Join(failures...)
}

type observation struct {
	method, path, auth string
	query              url.Values
}

func check(ctx context.Context, manifest []byte, env Environment, c Case) error {
	if c.Name == "" {
		return fmt.Errorf("case name is required")
	}
	if (c.WantError == "") != (c.WantExit == 0) {
		return fmt.Errorf("expected error code and non-zero exit must be specified together")
	}
	status := c.Response.Status
	if status == 0 {
		status = http.StatusOK
	}
	if status < 200 || status > 599 {
		return fmt.Errorf("fixture status must be between 200 and 599")
	}
	body := c.Response.Body
	if body == "" && status >= 400 {
		body = `{"private":"` + privateDetail + `"}`
	}
	if c.WantError == "" && (c.Request == nil || !json.Valid([]byte(body))) {
		return fmt.Errorf("success case needs an expected request and JSON response body")
	}
	var count atomic.Int64
	observed := make(chan observation, 1)
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		count.Add(1)
		select {
		case observed <- observation{r.Method, r.URL.EscapedPath(), r.Header.Get("Authorization"), r.URL.Query()}:
		default:
		}
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(status)
		_, _ = w.Write([]byte(body))
	}))
	defer server.Close()
	p, err := project.New(manifest, func(key string) string {
		if key == env.BaseURL {
			return server.URL + env.Prefix
		}
		if env.Token != "" && key == env.Token {
			return fixtureToken
		}
		return ""
	})
	if err != nil {
		return fmt.Errorf("construct project: %w", err)
	}
	ctx, cancel := context.WithTimeout(ctx, 10*time.Second)
	defer cancel()
	var out, diagnostic bytes.Buffer
	exit := cli.Run(ctx, p, c.Args, &out, &diagnostic)
	var failures []error
	if exit != c.WantExit {
		failures = append(failures, fmt.Errorf("exit: got %d, want %d; diagnostic %s", exit, c.WantExit, preview(diagnostic.Bytes())))
	}
	wantRequests := int64(0)
	if c.Request != nil {
		wantRequests = 1
	}
	if got := count.Load(); got != wantRequests {
		failures = append(failures, fmt.Errorf("requests: got %d, want %d", got, wantRequests))
	}
	if c.Request != nil && count.Load() > 0 {
		got := <-observed
		auth := ""
		if env.Token != "" {
			auth = "Bearer " + fixtureToken
		}
		if got.method != http.MethodGet || got.path != c.Request.Path || got.query.Encode() != c.Request.Query.Encode() || got.auth != auth {
			failures = append(failures, fmt.Errorf("request mismatch: got %s %s?%s (auth matches: %t), want GET %s?%s", got.method, got.path, got.query.Encode(), got.auth == auth, c.Request.Path, c.Request.Query.Encode()))
		}
	}
	if c.WantError != "" {
		var envelope struct {
			Error struct {
				Code    string `json:"code"`
				Message string `json:"message"`
			} `json:"error"`
		}
		if out.Len() != 0 || json.Unmarshal(diagnostic.Bytes(), &envelope) != nil || envelope.Error.Code != c.WantError || envelope.Error.Message == "" {
			failures = append(failures, fmt.Errorf("error contract: stdout %s; stderr %s; want %s", preview(out.Bytes()), preview(diagnostic.Bytes()), c.WantError))
		}
	} else {
		var expected, actual bytes.Buffer
		_ = json.Compact(&expected, []byte(body))
		err := json.Compact(&actual, out.Bytes())
		if err != nil || !bytes.Equal(expected.Bytes(), actual.Bytes()) || diagnostic.Len() != 0 {
			failures = append(failures, fmt.Errorf("result: stdout %s; stderr %s", preview(out.Bytes()), preview(diagnostic.Bytes())))
		}
	}
	if strings.Contains(out.String()+diagnostic.String(), fixtureToken) || strings.Contains(out.String()+diagnostic.String(), privateDetail) {
		failures = append(failures, fmt.Errorf("output exposed fixture credentials or private details"))
	}
	return errors.Join(failures...)
}

func preview(data []byte) string {
	if len(data) > 256 {
		return fmt.Sprintf("%q... (%d bytes)", data[:256], len(data))
	}
	return fmt.Sprintf("%q", data)
}
