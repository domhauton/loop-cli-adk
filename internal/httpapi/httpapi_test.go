package httpapi

import (
	"context"
	"errors"
	"strings"
	"testing"

	"github.com/domhauton/loop-cli-adk/pkg/operation"
)

func TestRejectCredentialBearingBaseURL(t *testing.T) {
	for _, base := range []string{"https://user:secret-fixture@example.test", "https://example.test?token=secret-fixture", "https://example.test#secret-fixture"} {
		t.Run(base, func(t *testing.T) {
			handler := Bind(Config{Path: "/users", BaseURLEnv: "API_URL", Getenv: func(string) string { return base }})
			_, err := handler(context.Background(), nil)
			var public *operation.Error
			if !errors.As(err, &public) || public.Code != "configuration" {
				t.Fatalf("expected local configuration failure, got %v", err)
			}
			if strings.Contains(err.Error(), "secret-fixture") {
				t.Fatal("credential value leaked into public error")
			}
		})
	}
}
