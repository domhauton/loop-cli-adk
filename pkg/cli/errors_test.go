package cli

import (
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
	"strings"
	"testing"

	"github.com/domhauton/loop-cli-adk/pkg/operation"
)

func TestWriteErrorPreservesProtocolDetailsWithoutCause(t *testing.T) {
	cause := errors.New("private credential and URL")
	public := operation.NewError("rpc_status", "remote operation unavailable", cause)
	public.Details = map[string]string{"rpc_code": "UNAVAILABLE"}
	var out bytes.Buffer
	if got := WriteError(&out, fmt.Errorf("private wrapper: %w", public)); got != 1 {
		t.Fatalf("exit = %d", got)
	}
	var envelope errorEnvelope
	if err := json.Unmarshal(out.Bytes(), &envelope); err != nil {
		t.Fatal(err)
	}
	if envelope.Error.Details["rpc_code"] != "UNAVAILABLE" || strings.Contains(out.String(), "private") {
		t.Fatalf("unsafe or missing public details: %s", &out)
	}
	if !errors.Is(public, cause) {
		t.Fatal("cause was lost")
	}
}

func TestWriteErrorOmitsAbsentDetails(t *testing.T) {
	var out bytes.Buffer
	WriteError(&out, operation.NewError("invalid_input", "input is required", nil))
	if out.String() != `{"error":{"code":"invalid_input","message":"input is required"}}`+"\n" {
		t.Fatalf("changed existing error shape: %s", &out)
	}
}
