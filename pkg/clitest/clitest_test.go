package clitest

import (
	"context"
	"errors"
	"net/url"
	"strings"
	"testing"
)

const manifest = `{
 "schema_version":1,"name":"fixturectl","description":"Fixture",
 "api":{"base_url_env":"FIXTURE_URL","token_env":"FIXTURE_TOKEN"},
 "commands":[{"name":"billing day","description":"Get billing",
  "input":{"day":{"type":"string","required":true}},
  "http":{"method":"GET","path":"/api/billing","query":{"day":"day"}}}]
}`

func successfulCase() Case {
	return Case{Name: "encoded query", Args: []string{"billing", "day", "--input", `{"day":"2026-10-28 &extra=true+雪"}`},
		Request:  &Request{Path: "/admin%20api/api/billing", Query: url.Values{"day": {"2026-10-28 &extra=true+雪"}}},
		Response: Response{Body: `{ "total": 12.5 }`}}
}

func TestCheckRealCLI(t *testing.T) {
	success := successfulCase()
	unavailable := successfulCase()
	unavailable.Name, unavailable.Response, unavailable.WantExit, unavailable.WantError = "unavailable", Response{Status: 503}, 1, "http_status"
	malformed := successfulCase()
	malformed.Name, malformed.Response, malformed.WantExit, malformed.WantError = "malformed JSON", Response{Body: `{"total":`}, 1, "invalid_response"
	missing := Case{Name: "required input", Args: []string{"billing", "day"}, WantExit: 2, WantError: "invalid_input"}
	env := Environment{BaseURL: "FIXTURE_URL", Token: "FIXTURE_TOKEN", Prefix: "/admin%20api"}
	if err := Check(t.Context(), []byte(manifest), env, success, unavailable, malformed, missing); err != nil {
		t.Fatal(err)
	}
}

func TestCheckDetectsWrongExpectations(t *testing.T) {
	for _, tc := range []struct {
		name, want string
		change     func(*Case)
	}{
		{"path", "request mismatch", func(c *Case) { c.Request.Path = "/wrong" }},
		{"query", "request mismatch", func(c *Case) { c.Request.Query = url.Values{"day": {"wrong"}} }},
		{"exit", "exit:", func(c *Case) { c.WantExit = 1; c.WantError = "http_status" }},
		{"unexpected request", "requests:", func(c *Case) { c.Request = nil; c.WantExit = 2; c.WantError = "invalid_input" }},
		{"missing request", "requests:", func(c *Case) { c.Args = []string{"billing", "day"}; c.WantExit = 2; c.WantError = "invalid_input" }},
		{"private body", "private details", func(c *Case) { c.Response.Body = `{"secret":"loop-fixture-private"}` }},
	} {
		t.Run(tc.name, func(t *testing.T) {
			c := successfulCase()
			tc.change(&c)
			err := Check(t.Context(), []byte(manifest), Environment{BaseURL: "FIXTURE_URL", Token: "FIXTURE_TOKEN", Prefix: "/admin%20api"}, c)
			if err == nil || !strings.Contains(err.Error(), tc.want) {
				t.Fatalf("got %v, want %q", err, tc.want)
			}
		})
	}
}

func TestCheckRejectsIncompleteCasesAndHonoursCancellation(t *testing.T) {
	env := Environment{BaseURL: "FIXTURE_URL", Token: "FIXTURE_TOKEN"}
	for _, c := range []Case{{}, {Name: "no expected response"}, {Name: "error without exit", WantError: "http_status"}, {Name: "invalid status", Response: Response{Status: 99}}} {
		if err := Check(t.Context(), []byte(manifest), env, c); err == nil {
			t.Fatalf("accepted incomplete case: %+v", c)
		}
	}
	if err := Check(t.Context(), []byte(manifest), env); err == nil {
		t.Fatal("accepted no cases")
	}
	ctx, cancel := context.WithCancel(t.Context())
	cancel()
	if err := Check(ctx, []byte(manifest), env, successfulCase()); !errors.Is(err, context.Canceled) {
		t.Fatalf("got %v", err)
	}
}

func TestCheckDetectsManifestMutations(t *testing.T) {
	for _, replacement := range [][2]string{{`"/api/billing"`, `"/wrong"`}, {`"query":{"day":"day"}`, `"query":{"day":"date"}`}, {`"required":true`, `"required":false`}} {
		changed := strings.Replace(manifest, replacement[0], replacement[1], 1)
		cases := []Case{successfulCase(), {Name: "required", Args: []string{"billing", "day"}, WantError: "invalid_input", WantExit: 2}}
		err := Check(t.Context(), []byte(changed), Environment{BaseURL: "FIXTURE_URL", Token: "FIXTURE_TOKEN", Prefix: "/admin%20api"}, cases...)
		if err == nil {
			t.Fatalf("missed mutation %s", replacement[1])
		}
	}
}
