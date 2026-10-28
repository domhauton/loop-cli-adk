import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from lifecycle import Fixture
from prototypes.loop_verify import Client, VerificationError, verify_suite

ROOT = Path(__file__).resolve().parents[1]


class PrototypeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temp.name)
        cls.loop = cls.root / ('loop.exe' if os.name == 'nt' else 'loop')
        subprocess.run(['go', 'build', '-o', str(cls.loop), './cmd/loop'], cwd=ROOT, check=True, capture_output=True)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_both_interfaces_detect_real_api_regressions(self):
        fixture = Fixture()
        try:
            manifest = self.root / 'project.json'
            definition = json.loads((ROOT / 'examples/energy/project.json').read_text())
            manifest.write_text(json.dumps(definition))
            suite = self.root / 'checks.json'
            suite.write_text(json.dumps({'manifest': str(manifest), 'checks': [
                {'command': ['status', 'get'], 'json_subset': {'car_soc': 50, 'battery_soc': 80}},
                {'command': ['status', 'get'], 'http_status': 401, 'invalid_token': True}]}))
            client = Client(str(manifest))
            with patch.dict(os.environ, {'LOOP_EXECUTABLE': str(self.loop),
                    'ENERGY_API_URL': f'http://127.0.0.1:{fixture.server.server_port}/admin',
                    'ENERGY_API_TOKEN': fixture.token}):
                client.expect_json(['status', 'get'], {'car_soc': 50, 'battery_soc': 80})
                client.expect_http_status(['status', 'get'], 401, invalid_token=True)
                verify_suite(suite)
                self.assertTrue(all(c['client'] == 'loop-cli-adk' for c in fixture.calls))
                for variant in ('wrong_state', 'wrong_battery', 'auth_bypass'):
                    fixture.variant = variant
                    with self.assertRaises(VerificationError):
                        verify_suite(suite)
                    result = subprocess.run([sys.executable, str(ROOT / 'evals/prototypes/loop_verify.py'), str(suite)], capture_output=True, text=True)
                    self.assertEqual(result.returncode, 1)
                    self.assertNotIn(fixture.token, result.stdout + result.stderr)
                    self.assertNotIn('private-provider-fixture-detail', result.stdout + result.stderr)
                fixture.variant = 'wrong_state'
                with self.assertRaises(VerificationError):
                    client.expect_json(['status', 'get'], {'car_soc': 50})
                fixture.variant = 'auth_bypass'
                with self.assertRaises(VerificationError):
                    client.expect_http_status(['status', 'get'], 401, invalid_token=True)
        finally:
            fixture.close()
