"""Exercise the grader with a real compiled CLI, without any model calls."""
import json
import os
from pathlib import Path
import tempfile
import unittest

from agent import ROOT, checked, grade


class GraderTests(unittest.TestCase):
    def test_real_cli_passes_but_uncovered_mutations_do_not(self):
        env = dict(os.environ, CGO_ENABLED="0", GOWORK="off")
        with tempfile.TemporaryDirectory(prefix="loop-grader-test-") as temp:
            work = Path(temp) / "candidate"
            checked(["go", "run", "./cmd/loop", "init", "--name", "energyctl", "--dir", str(work)], ROOT, env)
            checked(["go", "mod", "edit", "-replace", "github.com/domhauton/loop-cli-adk=" + str(ROOT)], work, env)
            manifest = work / "project.json"
            data = json.loads(manifest.read_text())
            data["commands"].append({"name": "billing day", "description": "Read a day",
                "input": {"day": {"type": "string", "required": True}},
                "http": {"method": "GET", "path": "/api/billing", "query": {"day": "day"}}})
            manifest.write_text(json.dumps(data))
            before = manifest.read_bytes()
            checks = grade(work, env)
            self.assertEqual(manifest.read_bytes(), before)
            self.assertTrue(checks["candidate_tests_pass"])
            for name, passed in checks.items():
                self.assertEqual(passed, not name.startswith("tests_detect_"), name)


if __name__ == "__main__":
    unittest.main()
