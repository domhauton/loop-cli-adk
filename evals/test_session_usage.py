from datetime import datetime, timezone
import io
import json
import unittest
from session_usage import counters


def event(second, count):
    return {"type": "event_msg", "timestamp": f"2026-10-28T21:00:{second:02}Z",
            "payload": {"type": "token_count", "info": {"total_token_usage": {
                "input_tokens": count, "cached_input_tokens": count // 2,
                "output_tokens": count, "reasoning_output_tokens": 0, "total_tokens": count * 2}}}}


def stream(*events):
    return io.BytesIO(b"\n".join(json.dumps(e).encode() for e in events))


class SessionUsageTests(unittest.TestCase):
    def test_subtracts_last_counter_before_boundary(self):
        result = counters(stream(event(1, 10), event(3, 20), event(5, 40)), datetime(2026, 10, 28, 21, 0, 4, tzinfo=timezone.utc))
        self.assertEqual(result["since_boundary"]["total_tokens"], 40)
        self.assertEqual(result["parent_totals"]["total_tokens"], 80)

    def test_reset_or_missing_boundary_is_unknown_not_negative(self):
        with self.assertRaises(ValueError):
            counters(stream(event(1, 10), event(2, 5)))
        with self.assertRaises(ValueError):
            counters(stream(event(1, 10)), datetime(2026, 10, 28, tzinfo=timezone.utc))

    def test_unrelated_content_is_not_returned(self):
        result = counters(stream({"type": "message", "payload": {"text": "private source"}}, event(1, 10)))
        self.assertNotIn("private source", json.dumps(result))


if __name__ == "__main__":
    unittest.main()
