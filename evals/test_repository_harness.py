import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from repositories.profiles import Profile
from repositories.run import command, command_passed, exercise, mutation_detected


class RepositoryHarnessTests(unittest.TestCase):
    def test_existing_suite_detects_mutation_and_source_is_restored(self):
        with tempfile.TemporaryDirectory() as temp:
            work = Path(temp)
            (work / 'source.txt').write_text('correct')
            (work / 'check.py').write_text("from pathlib import Path\nassert Path('source.txt').read_text() == 'correct', 'EXPECTED_MISMATCH'\n")
            argv = (sys.executable, 'check.py')
            profile = Profile('fixture', 'Python', argv, argv, 'source.txt', 'correct', 'broken', 'EXPECTED_MISMATCH')
            result = exercise(profile, work, os.environ, work, sys.executable)
            self.assertTrue(result['passed'])
            self.assertTrue(result['mutation_detected'])
            self.assertEqual((work / 'source.txt').read_text(), 'correct')
            self.assertEqual(result['stages']['native_suite']['exit_code'], 0)

    def test_infrastructure_failure_is_not_a_caught_regression(self):
        base = {'exit_code': 1, 'timed_out': False, 'output_within_limit': True}
        self.assertFalse(mutation_detected(base, 'missing compiler', 'assertion failed'))
        self.assertFalse(mutation_detected({**base, 'timed_out': True}, 'assertion failed', 'assertion failed'))
        self.assertFalse(mutation_detected({**base, 'exit_code': None}, 'assertion failed', 'assertion failed'))

    def test_output_is_bounded_and_cannot_count_as_success(self):
        with tempfile.TemporaryDirectory() as temp:
            work = Path(temp)
            with patch('repositories.native_command.MAX_LOG_BYTES', 2048):
                result, text = command([sys.executable, '-c', "print('x'*10000)"], work, os.environ, work, 'overflow')
            self.assertFalse(result['output_within_limit'])
            self.assertFalse(command_passed(result))
            self.assertLessEqual((work / 'overflow.log').stat().st_size, 2048)
            self.assertLessEqual(len(text), 2048)
