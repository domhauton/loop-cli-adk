import json
import os
from pathlib import Path
import tempfile
import unittest
from agent import ROOT, checked, grade
from cases import CASES


class AgentGraderTests(unittest.TestCase):
    def test_required_and_optional_mappings_with_real_compiled_cli(self):
        env = dict(os.environ, CGO_ENABLED='0', GOWORK='off')
        with tempfile.TemporaryDirectory() as temp:
            work = Path(temp) / 'cli'
            checked(['go', 'run', './cmd/loop', 'init', '--name', 'energyctl', '--dir', str(work)], ROOT, env)
            checked(['go', 'mod', 'edit', '-replace', 'github.com/domhauton/loop-cli-adk=' + str(ROOT)], work, env)
            path = work / 'project.json'
            manifest = json.loads(path.read_text())
            manifest['commands'].append({'name': 'audit events', 'input': {'after': {'type': 'string', 'required': True}, 'limit': {'type': 'string'}}, 'http': {'method': 'GET', 'path': '/api/audit/events', 'query': {'after': 'since', 'limit': 'page_size'}}})
            path.write_text(json.dumps(manifest))
            (work / 'audit_test.go').write_text(r'''package main
import (
 "context"
 "net/url"
 "testing"
 "github.com/domhauton/loop-cli-adk/pkg/clitest"
)
func TestAudit(t *testing.T) {
 err := clitest.Check(context.Background(), manifest,
 clitest.Environment{BaseURL:"ENERGYCTL_API_URL", Token:"ENERGYCTL_API_TOKEN", Prefix:"/admin"},
 clitest.Case{Name:"both", Args:[]string{"audit","events","--input",`{"after":"a&b+雪","limit":"10"}`}, Request:&clitest.Request{Path:"/admin/api/audit/events",Query:url.Values{"since":{"a&b+雪"},"page_size":{"10"}}}, Response:clitest.Response{Body:`{"ok":true}`}},
 clitest.Case{Name:"omitted", Args:[]string{"audit","events","--input",`{"after":"a"}`}, Request:&clitest.Request{Path:"/admin/api/audit/events",Query:url.Values{"since":{"a"}}}, Response:clitest.Response{Body:`{"ok":true}`}},
 clitest.Case{Name:"required", Args:[]string{"audit","events"}, WantError:"invalid_input", WantExit:2},
 )
 if err != nil { t.Fatal(err) }
}
''', encoding='utf-8')
            result = grade(work, env, CASES['add_audit_events'])
            self.assertTrue(all(result.values()), result)
            manifest['commands'][-1]['http']['query']['limit'] = 'incorrect'
            path.write_text(json.dumps(manifest))
            result = grade(work, env, CASES['add_audit_events'])
            self.assertFalse(result['request_contract'])
            self.assertFalse(result['candidate_tests_pass'])
            self.assertFalse(result['tests_detect_query_limit'])
