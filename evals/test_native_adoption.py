"""Exercise configured-check grading with actual subprocesses and files."""
import os
from pathlib import Path
import json
import shutil
import sys
import tempfile
import unittest
from repositories.agent import grade_configured_checks


class AdoptionGradeTests(unittest.TestCase):
    def grade(self, script):
        with tempfile.TemporaryDirectory() as temp:
            work = Path(temp)
            (work / '.loop').mkdir()
            for name in ('feedback.py', 'native_command.py'):
                shutil.copyfile(Path(__file__).parent / 'repositories' / name, work / '.loop' / name)
            target = work / 'value.txt'
            target.write_bytes(b'fixed')
            argv = [sys.executable, '-c', script]
            (work / '.loop/feedback.json').write_text(json.dumps({'checks': {'focused': argv, 'suite': argv}}))
            result = grade_configured_checks(work, target, b'broken', os.environ.copy(), work, 'fixture assertion')
            self.assertEqual(target.read_bytes(), b'fixed')
            return result

    def test_real_assertion_detects_regression_and_restores(self):
        result = self.grade("from pathlib import Path; assert Path('value.txt').read_bytes() == b'fixed', 'fixture assertion'")
        self.assertTrue(all(result.values()), result)

    def test_noop_cannot_pass(self):
        self.assertFalse(all(self.grade('pass').values()))

    def test_always_failing_cannot_pass(self):
        self.assertFalse(all(self.grade("raise AssertionError('fixture assertion')").values()))
