import unittest
from lifecycle_report import compare, IDENTITY


def report(condition, costs, passed=True):
    return {**dict.fromkeys(IDENTITY, "same"), "condition": condition,
            "stages": [{"stage": n, "task": str(n), "passed": passed,
                        "usage": {"usage_complete": True, "tokens": {
                            "input_tokens": cost, "cached_input_tokens": 0, "output_tokens": 0}}}
                       for n, cost in enumerate(costs)]}


class LifecycleReportTests(unittest.TestCase):
    def test_setup_is_paid_before_savings_count(self):
        comparison = compare(report("natural", [100, 100, 100]), report("loop", [200, 50, 50]))
        self.assertEqual(comparison["first_observed_total_token_break_even_after_tasks"], 3)
        self.assertEqual(comparison["cumulative"][0]["loop_minus_natural_total_tokens"], 100)

    def test_no_extrapolated_payoff_and_no_reward_for_failure(self):
        self.assertIsNone(compare(report("natural", [100]), report("loop", [200]))["first_observed_total_token_break_even_after_tasks"])
        self.assertIsNone(compare(report("natural", [100]), report("loop", [50], False))["first_observed_total_token_break_even_after_tasks"])

    def test_unknown_usage_is_not_free(self):
        result = report("loop", [50])
        result["stages"][0]["usage"]["usage_complete"] = False
        with self.assertRaises(ValueError):
            compare(report("natural", [100]), result)


if __name__ == "__main__":
    unittest.main()
