#!/usr/bin/env python3
"""Compare cumulative, observed token usage without assuming scripts are rewritten."""
import argparse
import json
from pathlib import Path

IDENTITY = ("model", "reasoning_effort", "harness_sha256", "loop_revision", "codex_version", "fixture")


def compare(natural, loop):
    if natural["condition"] != "natural" or loop["condition"] != "loop":
        raise ValueError("expected one natural workflow and one Loop workflow")
    if any(natural[key] != loop[key] for key in IDENTITY):
        raise ValueError("experiment setup differs")
    if len(natural["stages"]) != len(loop["stages"]) or not natural["stages"]:
        raise ValueError("stage sequences differ or are empty")
    totals = {name: {"input_tokens": 0, "cached_input_tokens": 0, "output_tokens": 0,
                     "uncached_input_tokens": 0, "total_tokens": 0} for name in ("natural", "loop")}
    valid = True
    rows = []
    first = None
    for index, (a, b) in enumerate(zip(natural["stages"], loop["stages"])):
        if a["stage"] != index or b["stage"] != index or a["task"] != b["task"]:
            raise ValueError("stage identity differs")
        valid = valid and a["passed"] and b["passed"]
        for name, stage in (("natural", a), ("loop", b)):
            if not stage["usage"]["usage_complete"]:
                raise ValueError("cannot calculate break-even with unknown usage")
            t = stage["usage"]["tokens"]
            for key in ("input_tokens", "cached_input_tokens", "output_tokens"):
                totals[name][key] += t[key]
            totals[name]["uncached_input_tokens"] += t["input_tokens"] - t["cached_input_tokens"]
            totals[name]["total_tokens"] += t["input_tokens"] + t["output_tokens"]
        delta = totals["loop"]["total_tokens"] - totals["natural"]["total_tokens"]
        if first is None and valid and delta <= 0:
            first = index + 1
        rows.append({"tasks_completed": index + 1, "all_checks_passed_so_far": bool(valid),
                     "natural": dict(totals["natural"]), "loop": dict(totals["loop"]),
                     "loop_minus_natural_total_tokens": delta})
    return {"schema_version": 1, "loop_mode": loop.get("loop_mode", "scaffold"), "identity": {key: natural[key] for key in IDENTITY},
            "first_observed_total_token_break_even_after_tasks": first,
            "all_checks_passed": bool(valid), "cumulative": rows,
            "limitations": ["Total tokens count input plus output, including cached input once; this is not a dollar-cost calculation.",
                            "No future break-even is extrapolated from a short, changing task sequence.",
                            "Both workflows retain and may reuse their own artefacts; no fresh-script behaviour is forced."]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("natural", type=Path)
    parser.add_argument("loop", type=Path)
    args = parser.parse_args()
    print(json.dumps(compare(json.loads(args.natural.read_text()), json.loads(args.loop.read_text())), indent=2))


if __name__ == "__main__":
    main()
