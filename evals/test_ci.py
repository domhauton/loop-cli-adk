import io
import json
import unittest
from ci import compare, log_events
from usage import summarise


def trials():
    return [{"condition": c, "trial": n, "model": "fixed", "reasoning_effort": "low",
             "task_sha256": "task", "harness_sha256": "harness", "source_revision": c,
             "passed": True, "usage": {"usage_complete": True,
             "tokens": {"input_tokens": 100, "cached_input_tokens": 80, "output_tokens": 10}}}
            for c in ("baseline", "candidate") for n in (1, 2, 3)]


class CITests(unittest.TestCase):
    def test_extracts_usage_from_timestamped_action_logs(self):
        event = {"type": "turn.completed", "usage": {"input_tokens": 100, "cached_input_tokens": 80, "output_tokens": 10}}
        log = b'2026-10-28T21:00:00.000Z some build output\n' + b'2026-10-28T21:00:01.000Z ' + json.dumps(event, separators=(',', ':')).encode() + b'\n'
        report = summarise(log_events(io.BytesIO(log)))
        self.assertTrue(report["usage_complete"])
        self.assertEqual(report["tokens"]["input_tokens"], 100)

    def test_cheaper_failed_task_is_not_a_win(self):
        records = trials()
        records[-1]["passed"] = False
        records[-1]["usage"]["tokens"]["input_tokens"] = 80
        self.assertFalse(compare(records, 1.1)["passed"])

    def test_missing_usage_and_increased_cost_fail(self):
        records = trials()
        records[-1]["usage"]["usage_complete"] = False
        self.assertFalse(compare(records, 1.1)["passed"])
        records = trials()
        records[-1]["usage"]["tokens"]["output_tokens"] = 200
        self.assertFalse(compare(records, 1.1)["passed"])

    def test_changed_source_and_mixed_executors_cannot_be_pooled(self):
        records = trials()
        records[-1]["source_sha256"] = "changed"
        with self.assertRaises(ValueError):
            compare(records, 1.1)
        records = trials()
        records[-1]["executor"] = "local_codex_exec"
        with self.assertRaises(ValueError):
            compare(records, 1.1)
        for ratio in (float('nan'), float('inf'), 0, -1):
            with self.assertRaises(ValueError):
                compare(trials(), ratio)

    def test_requires_distinct_pairs_and_matching_setup(self):
        records = trials()
        self.assertTrue(compare(records, 1.1)["passed"])
        with self.assertRaises(ValueError):
            compare(records[:-1], 1.1)
        records[-1]["model"] = "different"
        with self.assertRaises(ValueError):
            compare(records, 1.1)


if __name__ == "__main__":
    unittest.main()
