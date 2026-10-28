import unittest
from report import aggregate, IDENTITY


def trial(condition, passed=True):
    return {**dict.fromkeys(IDENTITY, "fixed"), "condition": condition,
            "passed": passed, "duration_seconds": 10,
            "usage": {"usage_complete": True, "failed_command_count": 0,
                      "tokens": {"input_tokens": 100, "cached_input_tokens": 80, "output_tokens": 10}}}


class ReportTests(unittest.TestCase):
    def test_failure_costs_remain_in_totals(self):
        result = aggregate([trial("baseline"), trial("baseline", False), trial("skill")])
        group = result["conditions"]["baseline"]
        self.assertEqual(group["passed"], 1)
        self.assertEqual(group["total_observed_tokens"]["input_tokens"], 200)
        self.assertEqual(group["median_tokens"]["uncached_input_tokens"], 20)
        self.assertFalse(result["minimum_three_pairs"])

    def test_different_models_cannot_be_pooled(self):
        a, b = trial("baseline"), trial("skill")
        b["model"] = "different"
        with self.assertRaises(ValueError):
            aggregate([a, b])

    def test_missing_tokens_are_unknown_even_when_task_passes(self):
        item = trial("skill")
        item["usage"]["usage_complete"] = False
        item["usage"]["tokens"] = None
        group = aggregate([item])["conditions"]["skill"]
        self.assertIsNone(group["median_tokens"])
        self.assertEqual(group["unknown_usage_trials"], 1)

    def test_missing_provenance_is_rejected(self):
        item = trial("skill")
        del item["harness_sha256"]
        with self.assertRaises(ValueError):
            aggregate([item])


if __name__ == "__main__":
    unittest.main()
