import io
import json
import unittest
from usage import summarise


def events(*items):
    return io.BytesIO(b"\n".join(json.dumps(item).encode() for item in items))


def turn(**usage):
    return {"type": "turn.completed", "usage": usage}


class UsageTests(unittest.TestCase):
    def test_cached_tokens_are_a_subset_not_added_twice(self):
        report = summarise(events(
            turn(input_tokens=100, cached_input_tokens=80, output_tokens=20, reasoning_output_tokens=10),
            turn(input_tokens=40, cached_input_tokens=10, output_tokens=5, reasoning_output_tokens=2)))
        self.assertEqual(report["tokens"], dict(input_tokens=140, cached_input_tokens=90, output_tokens=25))
        self.assertEqual(report["reasoning_output_tokens"], 12)
        self.assertTrue(report["usage_complete"])

    def test_missing_usage_is_not_zero_cost(self):
        report = summarise(events({"type": "turn.failed"}))
        self.assertIsNone(report["tokens"])
        self.assertFalse(report["usage_complete"])
        with self.assertRaises(ValueError):
            summarise(events(turn(input_tokens=4, output_tokens=2)))

    def test_failed_later_turn_marks_partial_measurement(self):
        report = summarise(events(turn(input_tokens=4, cached_input_tokens=0, output_tokens=2),
                                  {"type": "turn.failed"}))
        self.assertFalse(report["usage_complete"])
        self.assertIsNone(report["reasoning_output_tokens"])

    def test_bad_usage_and_exact_invalid_json(self):
        for tokens in (-1, True, "1"):
            with self.assertRaises(ValueError):
                summarise(events(turn(input_tokens=tokens, cached_input_tokens=0, output_tokens=1)))
        with self.assertRaises(ValueError):
            summarise(events(turn(input_tokens=1, cached_input_tokens=2, output_tokens=1)))
        with self.assertRaises(ValueError):
            summarise(io.BytesIO(b'{"type":"turn.completed",}\n'))

    def test_counts_completed_commands_once_without_content(self):
        item = {"type": "command_execution", "exit_code": 1, "aggregated_output": "secret"}
        report = summarise(events({"type": "item.started", "item": item},
                                  {"type": "item.completed", "item": item}))
        self.assertEqual(report["command_count"], 1)
        self.assertEqual(report["failed_command_count"], 1)
        self.assertNotIn("secret", json.dumps(report))


if __name__ == "__main__":
    unittest.main()
