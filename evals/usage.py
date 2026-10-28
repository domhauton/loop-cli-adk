#!/usr/bin/env python3
"""Summarise observed Codex JSONL usage without retaining prompts or tool output."""
import argparse
import json
from pathlib import Path

# A tool event can contain a large diff. Bound both a single event and the stream.
MAX_EVENT_BYTES = 16 * 1024 * 1024
MAX_STREAM_BYTES = 128 * 1024 * 1024
FIELDS = ("input_tokens", "cached_input_tokens", "output_tokens")


def summarise(stream):
    totals = dict.fromkeys(FIELDS, 0)
    completed = failed = commands = failed_commands = size = 0
    reasoning = 0
    reasoning_known = True
    for line in stream:
        size += len(line)
        if len(line) > MAX_EVENT_BYTES or size > MAX_STREAM_BYTES:
            raise ValueError("event stream exceeds size limit")
        if not line.strip():
            continue
        event = json.loads(line)
        if not isinstance(event, dict):
            raise ValueError("event must be an object")
        kind = event.get("type")
        if kind == "turn.completed":
            usage = event.get("usage")
            if not isinstance(usage, dict):
                raise ValueError("completed turn has no measured usage")
            for field in FIELDS:
                value = usage.get(field)
                if type(value) is not int or value < 0:
                    raise ValueError("invalid or missing usage: " + field)
                totals[field] += value
            if usage["cached_input_tokens"] > usage["input_tokens"]:
                raise ValueError("cached input exceeds total input")
            value = usage.get("reasoning_output_tokens")
            if value is None:
                reasoning_known = False
            elif type(value) is not int or value < 0 or value > usage["output_tokens"]:
                raise ValueError("invalid reasoning output usage")
            else:
                reasoning += value
            completed += 1
        elif kind in ("turn.failed", "error"):
            failed += 1
        elif kind == "item.completed":
            item = event.get("item", {})
            if item.get("type") == "command_execution":
                commands += 1
                if item.get("exit_code") not in (None, 0) or item.get("status") == "failed":
                    failed_commands += 1
    return {"schema_version": 1, "usage_source": "codex_exec_turn_completed",
            "usage_complete": completed > 0 and failed == 0,
            "completed_turns": completed, "failure_events": failed,
            "tokens": totals if completed else None,
            "reasoning_output_tokens": reasoning if completed and reasoning_known else None,
            "command_count": commands, "failed_command_count": failed_commands,
            "event_bytes": size}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("events", type=Path)
    args = parser.parse_args()
    with args.events.open("rb") as stream:
        # readline(limit) avoids allocating an unbounded line before checking it.
        result = summarise(iter(lambda: stream.readline(MAX_EVENT_BYTES + 1), b""))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
