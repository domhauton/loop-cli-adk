#!/usr/bin/env python3
"""Prepare and grade CI trials; model execution belongs to the official action."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess

from agent import checked, grade
from cases import CASES
from usage import summarise, MAX_EVENT_BYTES, MAX_STREAM_BYTES
from provenance import snapshot


def log_events(stream):
    """Accept JSONL events with GitHub's timestamp prefix, not arbitrary log text."""
    size = 0
    for line in iter(lambda: stream.readline(MAX_EVENT_BYTES + 1), b""):
        size += len(line)
        if len(line) > MAX_EVENT_BYTES or size > MAX_STREAM_BYTES:
            raise ValueError("CI log exceeds size limit")
        line = re.sub(rb"^\d{4}-\d\d-\d\dT[0-9:.]+Z ", b"", line)
        if not line.startswith(b'{"type":'):
            continue
        yield line


def prepare(args):
    sdk, work = args.sdk.resolve(), args.workspace.resolve()
    env = dict(os.environ, CGO_ENABLED="0", GOWORK="off")
    source = snapshot(sdk)
    case = CASES[getattr(args, "task", "add_billing_day")]
    checked(["go", "run", "./cmd/loop", "init", "--name", "energyctl", "--dir", str(work)], sdk, env)
    checked(["go", "mod", "edit", "-replace", "github.com/domhauton/loop-cli-adk=" + str(sdk)], work, env)
    with (work / ".gitignore").open("a") as ignore:
        ignore.write("\n/.eval-cache/\n")
    env["GOCACHE"] = str(work / ".eval-cache")
    checked(["go", "test", "-short", "./..."], work, env)
    checked(["git", "init", "-q"], work, env)
    args.prompt.write_text(case.prompt + "\nUse the generated development and testing guidance relevant to this task.\n")
    args.metadata.write_text(json.dumps({
        "schema_version": 1, "experiment": "revision_comparison", "condition": args.condition,
        "trial": args.trial, "model": args.model, "reasoning_effort": "low",
        "task": case.name, "task_sha256": hashlib.sha256(args.prompt.read_bytes()).hexdigest(),
        "harness_sha256": hashlib.sha256(Path(__file__).read_bytes() + Path(__file__).with_name("agent.py").read_bytes() + Path(__file__).with_name("provenance.py").read_bytes() + Path(__file__).with_name("cases.py").read_bytes()).hexdigest(),
        "source_revision": source["revision"], "source_sha256": source["sha256"],
    }, indent=2) + "\n")


def assess(args):
    metadata = json.loads(args.metadata.read_text())
    env = dict(os.environ, CGO_ENABLED="0", GOWORK="off")
    # Rebind the disposable candidate after transferring it to a fresh runner.
    checked(["go", "mod", "edit", "-replace", "github.com/domhauton/loop-cli-adk=" + str(args.sdk.resolve())], args.workspace, env)
    with args.log.open("rb") as stream:
        usage = summarise(log_events(stream))
    checks, harness_error = {}, None
    try:
        checks = grade(args.workspace.resolve(), env, CASES[metadata["task"]])
        source = snapshot(args.sdk)
        checks["sdk_source_unchanged"] = source == {"revision": metadata["source_revision"], "sha256": metadata["source_sha256"]}
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as error:
        harness_error = type(error).__name__ + ": " + str(error)
    result = {**metadata, "usage": usage, "checks": checks, "harness_error": harness_error,
              "action_outcome": args.outcome.read_text().strip(),
              "passed": bool(checks) and all(checks.values()) and args.outcome.read_text().strip() == "success"}
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


def compare(results, max_ratio):
    if not math.isfinite(max_ratio) or max_ratio <= 0:
        raise ValueError("token ratio must be positive")
    if len(results) != 6 or {(r["condition"], r["trial"]) for r in results} != {(c, n) for c in ("baseline", "candidate") for n in (1, 2, 3)}:
        raise ValueError("exactly three distinct trials per revision are required")
    for key in ("model", "reasoning_effort", "task_sha256", "harness_sha256", "executor", "codex_version"):
        if len({r.get(key) for r in results}) != 1:
            raise ValueError("incomparable experiment field: " + key)
    groups = {}
    for condition in ("baseline", "candidate"):
        trials = [r for r in results if r["condition"] == condition]
        if len({(r["source_revision"], r.get("source_sha256")) for r in trials}) != 1:
            raise ValueError("mixed revisions within condition")
        complete = all(r["usage"]["usage_complete"] for r in trials)
        tokens = [r["usage"]["tokens"] for r in trials] if complete else []
        groups[condition] = {"revision": trials[0]["source_revision"], "passed": sum(r["passed"] for r in trials),
            "usage_complete": complete,
            "total_tokens": sum(t["input_tokens"] + t["output_tokens"] for t in tokens) if complete else None,
            "uncached_input_tokens": sum(t["input_tokens"] - t["cached_input_tokens"] for t in tokens) if complete else None,
            "output_tokens": sum(t["output_tokens"] for t in tokens) if complete else None}
    base, candidate = groups["baseline"], groups["candidate"]
    ratio = candidate["total_tokens"] / base["total_tokens"] if base["total_tokens"] and candidate["total_tokens"] is not None else None
    passed = all(g["passed"] == 3 and g["usage_complete"] for g in groups.values()) and ratio is not None and ratio <= max_ratio
    return {"schema_version": 1, "conditions": groups, "total_token_ratio": ratio,
            "max_token_ratio": max_ratio, "passed": passed,
            "interpretation": "Small-sample regression signal, not a dollar-cost or general productivity claim."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("prepare")
    for name in ("sdk", "workspace", "prompt", "metadata"):
        p.add_argument("--" + name, type=Path, required=True)
    p.add_argument("--condition", choices=("baseline", "candidate"), required=True)
    p.add_argument("--trial", type=int, choices=(1, 2, 3), required=True)
    p.add_argument("--model", required=True)
    p.add_argument("--task", choices=tuple(CASES), default="add_billing_day")
    p = sub.add_parser("grade")
    for name in ("sdk", "workspace", "metadata", "log", "outcome", "output"):
        p.add_argument("--" + name, type=Path, required=True)
    p = sub.add_parser("compare")
    p.add_argument("results", nargs="+", type=Path)
    p.add_argument("--max-token-ratio", type=float, default=1.1)
    p.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "prepare":
        prepare(args)
    elif args.command == "grade":
        assess(args)
    else:
        report = compare([json.loads(p.read_text()) for p in args.results], args.max_token_ratio)
        args.output.write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report, indent=2))
        raise SystemExit(0 if report["passed"] else 1)


if __name__ == "__main__":
    main()
