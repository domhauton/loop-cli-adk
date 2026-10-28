// Package operation defines the small contract shared by executors and adapters.
package operation

import (
	"context"
	"encoding/json"
)

// MaxResultBytes bounds a buffered unary result to 4 MiB across all adapters.
const MaxResultBytes = 4 << 20

// Parameter describes a string input supported by the first manifest version.
type Parameter struct {
	Type        string `json:"type"`
	Description string `json:"description,omitempty"`
	Required    bool   `json:"required,omitempty"`
}

// Descriptor is the discoverable contract for one unary JSON operation.
type Descriptor struct {
	Name        string               `json:"name"`
	Description string               `json:"description"`
	Input       map[string]Parameter `json:"input"`
}

// Handler executes an operation after the executor validates its input.
type Handler func(context.Context, map[string]string) (json.RawMessage, error)

// Error carries a safe public message and an underlying diagnostic cause.
// Callers must not serialise the cause, which can contain credentials or URLs.
type Error struct {
	Code    string
	Message string
	cause   error
}

// NewError preserves the cause without exposing it in the public message.
func NewError(code, message string, cause error) *Error {
	return &Error{Code: code, Message: message, cause: cause}
}

// Error returns the safe public message.
func (e *Error) Error() string { return e.Message }

// Unwrap exposes the diagnostic cause to library callers.
func (e *Error) Unwrap() error { return e.cause }
