import unittest
from repositories.report import aggregate, IDENTITY


def records():
    return [{**dict.fromkeys(IDENTITY, 'fixed'), 'evidence_sha256': f'{condition}-{i}',
             'profile': 'fixture', 'condition': condition, 'passed': True,
             'usage': {'usage_complete': True, 'command_count': 2, 'tokens': {
                 'input_tokens': 100, 'cached_input_tokens': 80, 'output_tokens': 10}}}
            for condition in ('natural', 'skill') for i in range(3)]


class NativeReportTests(unittest.TestCase):
    def test_failures_and_missing_usage_cannot_look_cheaper(self):
        rows = records()
        self.assertEqual(aggregate(rows)['profiles']['fixture']['skill_to_natural_total_token_ratio'], 1)
        rows[-1]['passed'] = False
        self.assertIsNone(aggregate(rows)['profiles']['fixture']['skill_to_natural_total_token_ratio'])
        rows = records()
        rows[-1]['usage']['usage_complete'] = False
        self.assertFalse(aggregate(rows)['profiles']['fixture']['comparison_valid'])

    def test_rejects_duplicate_evidence_and_mixed_revisions(self):
        rows = records()
        with self.assertRaises(ValueError):
            aggregate(rows + [rows[0]])
        rows[-1]['source_revision'] = 'other'
        with self.assertRaises(ValueError):
            aggregate(rows)

    def test_abandoned_helper_is_not_a_prepared_workflow_win(self):
        rows = records()
        for row in rows:
            row['used_prepared_feedback'] = row['condition'] == 'skill'
        self.assertTrue(aggregate(rows)['profiles']['fixture']['comparison_valid'])
        rows[-1]['used_prepared_feedback'] = False
        self.assertFalse(aggregate(rows)['profiles']['fixture']['comparison_valid'])
