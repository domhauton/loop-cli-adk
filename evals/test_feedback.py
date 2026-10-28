import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


class FeedbackTests(unittest.TestCase):
    def test_compact_results_preserve_native_failures_and_logs(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            helper = root / '.loop'
            helper.mkdir()
            source = Path(__file__).parent / 'repositories'
            for name in ('feedback.py', 'native_command.py'):
                shutil.copyfile(source / name, helper / name)
            config = {'checks': {'focused': [sys.executable, '-c', "print('successful detail '*500)"],
                                 'suite': [sys.executable, '-c', "print('START'+('x'*5000)+'END'); raise SystemExit(1)"]}}
            (helper / 'feedback.json').write_text(json.dumps(config))
            def invoke(name):
                r = subprocess.run([sys.executable, str(helper / 'feedback.py'), name], cwd=root, capture_output=True, text=True)
                return r.returncode, json.loads(r.stdout)
            code, data = invoke('focused')
            self.assertEqual(code, 0)
            self.assertTrue(data['passed'])
            self.assertEqual(data['output_excerpt'], '')
            self.assertGreater((root / data['log_path']).stat().st_size, 4000)
            code, data = invoke('suite')
            self.assertEqual(code, 1)
            self.assertFalse(data['passed'])
            self.assertTrue(data['excerpt_truncated'])
            self.assertIn('START', data['output_excerpt'])
            self.assertIn('END', data['output_excerpt'])
            self.assertGreater((root / data['log_path']).stat().st_size, len(data['output_excerpt']))
            self.assertEqual(invoke('unknown')[0], 2)
