// Package httpapi binds read operations to HTTP without frontend dependencies.
package httpapi

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"strings"
	"time"

	"github.com/domhauton/loop-cli-adk/pkg/operation"
)

// DefaultTimeout bounds each request to 30 seconds, including body reads.
const DefaultTimeout = 30 * time.Second

// Config contains one HTTP binding and lazy credential resolution.
type Config struct {
	Path       string
	Query      map[string]string
	BaseURLEnv string
	TokenEnv   string
	Getenv     func(string) string
}

// Bind constructs a read handler. Credentials are resolved only on invocation.
// Redirects are rejected to avoid forwarding credentials or hiding an API move.
func Bind(cfg Config) operation.Handler {
	query := make(map[string]string, len(cfg.Query))
	for k, v := range cfg.Query {
		query[k] = v
	}
	cfg.Query = query
	client := &http.Client{Timeout: DefaultTimeout, CheckRedirect: func(*http.Request, []*http.Request) error { return http.ErrUseLastResponse }}
	return func(ctx context.Context, input map[string]string) (json.RawMessage, error) {
		base := cfg.Getenv(cfg.BaseURLEnv)
		u, err := url.Parse(base)
		if err != nil || u == nil || (u.Scheme != "https" && u.Scheme != "http") || u.Host == "" || u.User != nil || u.RawQuery != "" || u.Fragment != "" {
			return nil, operation.NewError("configuration", "set "+cfg.BaseURLEnv+" to an HTTP(S) base URL without credentials, query or fragment", err)
		}
		// Preserve an API prefix, e.g. /admin/v1, rather than resolving /users at the host root.
		u, err = url.Parse(strings.TrimRight(u.String(), "/") + cfg.Path)
		if err != nil {
			return nil, operation.NewError("configuration", "invalid API path", err)
		}
		q := u.Query()
		for key, value := range input {
			q.Set(cfg.Query[key], value)
		}
		u.RawQuery = q.Encode()
		req, err := http.NewRequestWithContext(ctx, http.MethodGet, u.String(), nil)
		if err != nil {
			return nil, operation.NewError("configuration", "cannot construct API request", err)
		}
		req.Header.Set("Accept", "application/json")
		if cfg.TokenEnv != "" {
			token := cfg.Getenv(cfg.TokenEnv)
			if token == "" {
				return nil, operation.NewError("configuration", "set required credential environment variable "+cfg.TokenEnv, nil)
			}
			req.Header.Set("Authorization", "Bearer "+token)
		}
		res, err := client.Do(req)
		if err != nil {
			return nil, requestError(err)
		}
		defer res.Body.Close()
		if res.StatusCode < 200 || res.StatusCode >= 300 {
			return nil, operation.NewError("http_status", fmt.Sprintf("API returned HTTP %d", res.StatusCode), nil)
		}
		body, err := io.ReadAll(io.LimitReader(res.Body, operation.MaxResultBytes+1))
		if err != nil {
			return nil, requestError(err)
		}
		if len(body) > operation.MaxResultBytes {
			return nil, operation.NewError("response_limit", fmt.Sprintf("API response exceeds %d bytes", operation.MaxResultBytes), nil)
		}
		if !json.Valid(body) {
			return nil, operation.NewError("invalid_response", "API response is not valid JSON", nil)
		}
		return json.RawMessage(body), nil
	}
}

func requestError(err error) error {
	if errors.Is(err, context.Canceled) {
		return operation.NewError("cancelled", "operation cancelled", err)
	}
	if errors.Is(err, context.DeadlineExceeded) {
		return operation.NewError("timeout", "API request timed out", err)
	}
	return operation.NewError("transport", "API request failed", err)
}
