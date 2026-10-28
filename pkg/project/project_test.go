package project_test

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync/atomic"
	"testing"
	"time"

	"github.com/domhauton/loop-cli-adk/pkg/cli"
	"github.com/domhauton/loop-cli-adk/pkg/operation"
	"github.com/domhauton/loop-cli-adk/pkg/project"
)

const manifest = `{"schema_version":1,"name":"testctl","api":{"base_url_env":"API_URL","token_env":"API_TOKEN"},"commands":[{"name":"users list","description":"List users","input":{"name":{"type":"string","required":true}},"http":{"method":"GET","path":"/users","query":{"name":"search"}}}]}`

func newProject(t *testing.T, url string) *project.Project {
	t.Helper()
	p, err := project.New([]byte(manifest), func(key string) string {
		if key == "API_URL" {
			return url
		}
		return "secret-fixture"
	})
	if err != nil {
		t.Fatal(err)
	}
	return p
}

func TestDiscoveryDoesNotReadCredentials(t *testing.T) {
	p, err := project.New([]byte(manifest), func(string) string { t.Fatal("discovery read environment"); return "" })
	if err != nil {
		t.Fatal(err)
	}
	d := p.Describe()
	d[0].Input["name"] = operation.Parameter{}
	if !p.Describe()[0].Input["name"].Required {
		t.Fatal("discovery mutated registry")
	}
	var out, errout bytes.Buffer
	if status := cli.Run(context.Background(), p, []string{"describe", "users", "list"}, &out, &errout); status != 0 || !json.Valid(out.Bytes()) || errout.Len() != 0 {
		t.Fatalf("status=%d stdout=%s stderr=%s", status, &out, &errout)
	}
}

func TestRequestEncodingAndOutput(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/admin/v1/users" || r.URL.Query().Get("search") != "Ada & Grace" || r.Header.Get("Authorization") != "Bearer secret-fixture" || r.Header.Get("User-Agent") != "loop-cli-adk" {
			t.Errorf("unexpected request: path=%q query=%q", r.URL.Path, r.URL.RawQuery)
		}
		fmt.Fprint(w, "{\n\"users\": [\"Ada\"]\n}")
	}))
	defer server.Close()
	p := newProject(t, server.URL+"/admin/v1/")
	var out, errout bytes.Buffer
	status := cli.Run(context.Background(), p, []string{"users", "list", "--input", `{"name":"Ada & Grace"}`}, &out, &errout)
	if status != 0 || out.String() != "{\"users\":[\"Ada\"]}\n" || errout.Len() != 0 {
		t.Fatalf("status=%d stdout=%s stderr=%s", status, &out, &errout)
	}
}

func TestInvalidInputDoesNotCallAPI(t *testing.T) {
	var requests atomic.Int32
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) { requests.Add(1); fmt.Fprint(w, `{}`) }))
	defer server.Close()
	p := newProject(t, server.URL)
	for _, input := range []string{`{}`, `{"name":null}`, `{"name":7}`, `{"name":"Ada","extra":"x"}`, `null`, `[]`, `{"name":`} {
		t.Run(input, func(t *testing.T) {
			_, err := p.Execute(context.Background(), "users list", json.RawMessage(input))
			var public *operation.Error
			if !errors.As(err, &public) || public.Code != "invalid_input" {
				t.Fatalf("expected invalid_input, got %v", err)
			}
		})
	}
	if requests.Load() != 0 {
		t.Fatal("invalid input reached API")
	}
}

func TestHTTPFailuresAreStructuredAndDoNotExposeBody(t *testing.T) {
	cases := []struct {
		name       string
		status     int
		body, code string
	}{
		{"unauthorised", 401, `secret-fixture`, "http_status"},
		{"redirect", 302, `secret-fixture`, "http_status"},
		{"invalid JSON", 200, `secret-fixture`, "invalid_response"},
		{"too large", 200, strings.Repeat(" ", 4<<20) + `{}`, "response_limit"},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			var requests atomic.Int32
			server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				requests.Add(1)
				w.Header().Set("Location", "/other")
				w.WriteHeader(tc.status)
				fmt.Fprint(w, tc.body)
			}))
			defer server.Close()
			var out, errout bytes.Buffer
			status := cli.Run(context.Background(), newProject(t, server.URL), []string{"users", "list", "--input", `{"name":"Ada"}`}, &out, &errout)
			if status != 1 || out.Len() != 0 || !strings.Contains(errout.String(), `"code":"`+tc.code+`"`) || strings.Contains(errout.String(), "secret-fixture") || requests.Load() != 1 {
				t.Fatalf("status=%d stdout=%s stderr=%s requests=%d", status, &out, &errout, requests.Load())
			}
			var envelope struct {
				Error struct {
					Details map[string]string `json:"details"`
				} `json:"error"`
			}
			if err := json.Unmarshal(errout.Bytes(), &envelope); err != nil {
				t.Fatal(err)
			}
			if tc.code == "http_status" {
				if envelope.Error.Details["http_status"] != fmt.Sprint(tc.status) {
					t.Fatalf("missing HTTP status details: %s", &errout)
				}
			} else if len(envelope.Error.Details) != 0 {
				t.Fatalf("unexpected HTTP details: %s", &errout)
			}

		})
	}
}

func TestCancellation(t *testing.T) {
	started := make(chan struct{})
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) { close(started); <-r.Context().Done() }))
	defer server.Close()
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	result := make(chan error, 1)
	go func() {
		_, err := newProject(t, server.URL).Execute(ctx, "users list", json.RawMessage(`{"name":"Ada"}`))
		result <- err
	}()
	select {
	case <-started:
		cancel()
	case <-time.After(5 * time.Second):
		t.Fatal("request did not start")
	}
	select {
	case err := <-result:
		var public *operation.Error
		if !errors.As(err, &public) || public.Code != "cancelled" {
			t.Fatalf("expected cancellation, got %v", err)
		}
	case <-time.After(5 * time.Second):
		t.Fatal("cancellation did not stop request")
	}
}

func TestMissingCredentialFailsBeforeRequest(t *testing.T) {
	p, err := project.New([]byte(manifest), func(key string) string {
		if key == "API_URL" {
			return "http://127.0.0.1:1"
		}
		return ""
	})
	if err != nil {
		t.Fatal(err)
	}
	_, err = p.Execute(context.Background(), "users list", json.RawMessage(`{"name":"Ada"}`))
	var public *operation.Error
	if !errors.As(err, &public) || public.Code != "configuration" {
		t.Fatalf("expected credential error, got %v", err)
	}
}

func TestCancellationDuringBodyRead(t *testing.T) {
	started := make(chan struct{})
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		fmt.Fprint(w, `{"users":`)
		w.(http.Flusher).Flush()
		close(started)
		<-r.Context().Done()
	}))
	defer server.Close()
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	p := newProject(t, server.URL)
	result := make(chan error, 1)
	go func() { _, err := p.Execute(ctx, "users list", json.RawMessage(`{"name":"Ada"}`)); result <- err }()
	select {
	case <-started:
		cancel()
	case <-time.After(5 * time.Second):
		t.Fatal("body did not start")
	}
	select {
	case err := <-result:
		var public *operation.Error
		if !errors.As(err, &public) || public.Code != "cancelled" {
			t.Fatalf("expected cancelled body read, got %v", err)
		}
	case <-time.After(5 * time.Second):
		t.Fatal("body read did not stop")
	}
}
