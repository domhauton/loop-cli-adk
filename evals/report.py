#!/usr/bin/env python3
"""Aggregate comparable trials, retaining failures and separate token categories."""
import argparse
import json
from pathlib import Path
import statistics

IDENTITY = ("experiment_version", "harness_sha256", "task_sha256", "skill_sha256",
            "loop_revision", "model", "reasoning_effort", "codex_version", "task")


def aggregate(trials):
    if not trials:
        raise ValueError("at least one trial is required")
    if any(any(key not in trial for key in IDENTITY) for trial in trials):
        raise ValueError("trial lacks controlled experiment provenance")
    for trial in trials[1:]:
        if any(trial[key] != trials[0][key] for key in IDENTITY):
            raise ValueError("trial setup differs; report separate experiments")
    if any(t.get("condition") not in ("baseline", "skill") for t in trials):
        raise ValueError("unknown experiment condition")
    groups = {}
    for condition in ("baseline", "skill"):
        items = [t for t in trials if t["condition"] == condition]
        known = [t for t in items if t["usage"]["usage_complete"]]
        costs = [{**t["usage"]["tokens"], "uncached_input_tokens": t["usage"]["tokens"]["input_tokens"] - t["usage"]["tokens"]["cached_input_tokens"]} for t in known]
        groups[condition] = {
            "trials": len(items), "passed": sum(t["passed"] is True for t in items),
            "harness_failures": sum(bool(t.get("harness_error")) for t in items),
            "unknown_usage_trials": len(items) - len(known),
            "median_tokens": {key: statistics.median(c[key] for c in costs) for key in costs[0]} if costs else None,
            "total_observed_tokens": {key: sum(c[key] for c in costs) for key in costs[0]} if costs else None,
            "median_duration_seconds": statistics.median(t["duration_seconds"] for t in items) if items else None,
            "failed_commands": sum(t["usage"]["failed_command_count"] for t in items),
        }
    return {"schema_version": 1, "identity": {k: trials[0][k] for k in IDENTITY},
            "minimum_three_pairs": all(g["trials"] >= 3 for g in groups.values()),
            "conditions": groups,
            "claim": "Descriptive measurements only; inspect task success before token differences."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("results", nargs="+", type=Path)
    args = parser.parse_args()
    if len({p.resolve() for p in args.results}) != len(args.results):
        parser.error("duplicate result files would double-count a trial")
    print(json.dumps(aggregate([json.loads(p.read_text()) for p in args.results]), indent=2))


if __name__ == "__main__":
    main()
