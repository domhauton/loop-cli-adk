package execution

import (
	"context"
	"encoding/json"
	"errors"
	"strings"
	"testing"

	"github.com/domhauton/loop-cli-adk/pkg/operation"
)

func TestHandlerResultsRespectContract(t *testing.T) {
	for _, tc := range []struct{ name, result, code string }{
		{"invalid", `not JSON`, "invalid_response"},
		{"oversized", `"` + strings.Repeat("x", operation.MaxResultBytes) + `"`, "response_limit"},
	} {
		t.Run(tc.name, func(t *testing.T) {
			e, err := New([]Entry{{Descriptor: operation.Descriptor{Name: "test"}, Handler: func(context.Context, map[string]string) (json.RawMessage, error) {
				return json.RawMessage(tc.result), nil
			}}})
			if err != nil {
				t.Fatal(err)
			}
			_, err = e.Execute(context.Background(), "test", json.RawMessage(`{}`))
			var public *operation.Error
			if !errors.As(err, &public) || public.Code != tc.code {
				t.Fatalf("expected %s, got %v", tc.code, err)
			}
		})
	}
}
