import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from lifecycle import Fixture, TOKEN, grade, stage_passed


class LifecycleTests(unittest.TestCase):
    def test_grader_requires_observed_api_behaviour(self):
        fixture = Fixture()
        try:
            with tempfile.TemporaryDirectory() as temp:
                work = Path(temp)
                env = dict(os.environ, ENERGY_API_URL=f"http://127.0.0.1:{fixture.server.server_port}/admin", ENERGY_API_TOKEN=TOKEN)
                (work / "verify.py").write_text('''import os, json, urllib.request
request = urllib.request.Request(os.environ['ENERGY_API_URL'] + '/api/status', headers={'Authorization':'Bearer ' + os.environ['ENERGY_API_TOKEN']})
with urllib.request.urlopen(request) as response:
    data = json.load(response)
assert data['car_soc'] == 50 and data['battery_soc'] == 80
''')
                (work / "verification.json").write_text(json.dumps({"argv": [sys.executable, "verify.py"]}))
                self.assertTrue(all(grade(work, env, fixture).values()))
                (work / "verify.py").write_text('pass\n')
                self.assertFalse(grade(work, env, fixture)["normal"])
        finally:
            fixture.close()

    def test_failed_setup_is_not_rescued_by_existing_scaffold(self):
        self.assertFalse(stage_passed(1, {"cli_scaffolded": True}))
        self.assertFalse(stage_passed(None, {"cli_scaffolded": True}))

    def test_missing_command_is_not_success(self):
        fixture = Fixture()
        try:
            with tempfile.TemporaryDirectory() as temp:
                self.assertFalse(grade(Path(temp), os.environ, fixture)["verification_command"])
        finally:
            fixture.close()


if __name__ == "__main__":
    unittest.main()
