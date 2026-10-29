import json
import hashlib
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from repositories import lifecycle
from repositories.profiles import Profile
from repositories.lifecycle_report import aggregate, read_verified_record
from usage import summarise
from repositories.report import IDENTITY


class RetainedWorkspaceTests(unittest.TestCase):
    def test_retention_and_model_free_preflight(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / 'source'
            source.mkdir()
            (source / 'values').write_text('a=1\nb=2\nc=3\n')
            (source / 'check.py').write_text("from pathlib import Path\nassert Path('values').read_text() == 'a=1\\nb=2\\nc=3\\n', 'native assertion'\n")
            subprocess.run(['git', 'init', '-q', str(source)], check=True)
            subprocess.run(['git', 'add', '.'], cwd=source, check=True)
            subprocess.run(['git', '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-qm', 'fixture'], cwd=source, check=True)
            argv = (sys.executable, 'check.py')
            stages = [(Profile('HEAD', 'Python', argv, argv, 'values', f'{key}={i}', f'{key}=0', 'native assertion'), 'repair')
                      for i, key in enumerate('abc', 1)]
            calls = []
            def repair(work, output, env, prompt, model, timeout):
                i = len(calls) + 1
                note = work / 'retained-note'
                if calls:
                    self.assertEqual(note.read_text(), str(i-1))
                note.write_text(str(i))
                values = work / 'values'
                values.write_text(values.read_text().replace(f'{"abc"[i-1]}=0', f'{"abc"[i-1]}={i}'))
                (output / 'events.jsonl').write_text(str(i))
                calls.append(i)
                return 0, 0.1, {'usage_complete': True, 'tokens': {'input_tokens': 10, 'cached_input_tokens': 0, 'output_tokens': 1}}
            args = ['lifecycle', '--profile', 'loop-definition', '--source', str(source), '--condition', 'natural', '--output', str(root / 'out')]
            original_check_output = subprocess.check_output
            def metadata(argv, **kwargs):
                return 'fixture-codex' if argv == ['codex', '--version'] else original_check_output(argv, **kwargs)
            with patch.object(lifecycle.subprocess, 'check_output', side_effect=metadata), patch.object(sys, 'argv', args), patch.object(lifecycle, 'sequence', return_value=stages), patch.object(lifecycle, 'invoke_agent', side_effect=repair), patch('builtins.print'):
                lifecycle.main()
            result = json.loads((root / 'out/result.json').read_text())
            self.assertTrue(result['passed'], result)
            self.assertEqual(calls, [1, 2, 3])
            preflight_args = args[:-1] + [str(root / 'preflight'), '--preflight-only']
            def without_codex(argv, **kwargs):
                if argv == ['codex', '--version']:
                    raise AssertionError('deterministic preflight must not require Codex')
                return original_check_output(argv, **kwargs)
            with patch.object(lifecycle.subprocess, 'check_output', side_effect=without_codex), patch.object(sys, 'argv', preflight_args), patch.object(lifecycle, 'sequence', return_value=stages), patch.object(lifecycle, 'invoke_agent', side_effect=AssertionError('model called')), patch('builtins.print'):
                lifecycle.main()
            preflight = json.loads((root / 'preflight/result.json').read_text())
            self.assertTrue(preflight['passed'], preflight)
            self.assertIsNone(preflight['codex_version'])


def records():
    return [{**dict.fromkeys(IDENTITY, 'fixed'), 'profile': 'fixture', 'condition': condition,
             'expected_stages': 3, 'passed': True,
             'stages': [{'passed': True, 'evidence_sha256': f'{condition}-{i}-{stage}',
                         'usage': {'usage_complete': True, 'tokens': {'input_tokens': cost, 'cached_input_tokens': 0, 'output_tokens': 0}}}
                        for stage, cost in enumerate([100, 100, 100] if condition == 'natural' else [150, 50, 50])]}
            for condition in ('natural', 'skill') for i in range(3)]


class LifecycleReportTests(unittest.TestCase):
    def test_setup_is_counted_before_observed_crossover(self):
        r = aggregate(records())['profiles']['fixture']
        self.assertEqual(r['cumulative_median_skill_to_natural_ratios'], [1.5, 1, 250/300])
        self.assertEqual(r['first_sustained_observed_crossover_stage'], 3)

    def test_failed_or_missing_stage_cannot_create_payoff(self):
        for missing in (False, True):
            rows = records()
            if missing:
                rows[-1]['stages'].pop()
            else:
                rows[-1]['stages'][-1]['passed'] = False
            r = aggregate(rows)['profiles']['fixture']
            self.assertFalse(r['comparison_valid'])
            self.assertIsNone(r['first_sustained_observed_crossover_stage'])

    def test_unknown_usage_and_duplicate_evidence_rejected(self):
        rows = records()
        rows[-1]['stages'][-1]['usage']['usage_complete'] = False
        self.assertFalse(aggregate(rows)['profiles']['fixture']['comparison_valid'])
        with self.assertRaises(ValueError):
            aggregate(rows + [rows[0]])


class LifecycleEvidenceTests(unittest.TestCase):
    def test_transcript_verification_preserves_capacity_failure(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            stage_dir = root / 'stage-1'
            stage_dir.mkdir()
            raw = (json.dumps({'type': 'error', 'message': 'Selected model is at capacity. Please try a different model.'}) + '\n').encode()
            events = stage_dir / 'events.jsonl'
            events.write_bytes(raw)
            report = root / 'result.json'
            report.write_text(json.dumps({'expected_stages': 3, 'stages': [{'stage': 1,
                'evidence_sha256': hashlib.sha256(raw).hexdigest(), 'usage': summarise([raw])}]}))
            self.assertEqual(read_verified_record(report)['stages'][0]['model_failure_category'], 'model_capacity')
            events.write_bytes(raw + b'\n')
            with self.assertRaisesRegex(ValueError, 'transcript changed'):
                read_verified_record(report)
