package definition

import (
	"encoding/json"
	"strings"
	"testing"
)

const validManifest = `{"schema_version":1,"name":"testctl","api":{"base_url_env":"API_URL"},"commands":[{"name":"users list","description":"List users","input":{"name":{"type":"string","required":true}},"http":{"method":"GET","path":"/users","query":{"name":"search"}}}]}`

func TestRoundTrip(t *testing.T) {
	m, err := Parse([]byte(validManifest))
	if err != nil {
		t.Fatal(err)
	}
	data, err := json.Marshal(m)
	if err != nil {
		t.Fatal(err)
	}
	again, err := Parse(data)
	if err != nil {
		t.Fatal(err)
	}
	if again.Commands[0].HTTP.Query["name"] != "search" || !again.Commands[0].Input["name"].Required {
		t.Fatal("round trip lost binding or input contract")
	}
}

func TestRejectInvalidDefinitions(t *testing.T) {
	cases := map[string]string{
		"unknown field":         strings.Replace(validManifest, `"schema_version":1`, `"typo":true,"schema_version":1`, 1),
		"unknown version":       strings.Replace(validManifest, `"schema_version":1`, `"schema_version":2`, 1),
		"write":                 strings.Replace(validManifest, `"GET"`, `"POST"`, 1),
		"external URL":          strings.Replace(validManifest, `"/users"`, `"//other.example/users"`, 1),
		"embedded query":        strings.Replace(validManifest, `"/users"`, `"/users?token=x"`, 1),
		"unsupported input":     strings.Replace(validManifest, `"type":"string"`, `"type":"integer"`, 1),
		"unbound input":         strings.Replace(validManifest, `"query":{"name":"search"}`, `"query":{}`, 1),
		"unknown input binding": strings.Replace(validManifest, `"query":{"name":"search"}`, `"query":{"name":"search","other":"other"}`, 1),
		"reserved command":      strings.Replace(validManifest, `"users list"`, `"describe users"`, 1),
		"trailing object":       validManifest + `{}`,
		"trailing bytes":        validManifest + `broken`,
		"null":                  `null`,
	}
	for name, input := range cases {
		t.Run(name, func(t *testing.T) {
			if _, err := Parse([]byte(input)); err == nil {
				t.Fatalf("accepted invalid bytes: %s", input)
			}
		})
	}
}
