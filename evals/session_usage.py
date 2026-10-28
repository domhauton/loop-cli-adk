#!/usr/bin/env python3
"""Read cumulative usage counters from one explicitly selected local Codex session."""
import argparse
from datetime import datetime
import json
from pathlib import Path

from usage import MAX_EVENT_BYTES, MAX_STREAM_BYTES

FIELDS = ("input_tokens", "cached_input_tokens", "output_tokens", "reasoning_output_tokens", "total_tokens")


def timestamp(value):
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamps must include a timezone")
    return parsed


def counters(stream, since=None):
    first = last = before = None
    size = 0
    for line in iter(lambda: stream.readline(MAX_EVENT_BYTES + 1), b""):
        size += len(line)
        if len(line) > MAX_EVENT_BYTES or size > MAX_STREAM_BYTES:
            raise ValueError("session exceeds size limit")
        event = json.loads(line)
        payload = event.get("payload", {})
        if event.get("type") != "event_msg" or payload.get("type") != "token_count":
            continue
        usage = (payload.get("info") or {}).get("total_token_usage")
        if not usage:
            continue
        values = {key: usage.get(key) for key in FIELDS}
        if any(type(value) is not int or value < 0 for value in values.values()):
            raise ValueError("missing or invalid usage counters")
        if values["cached_input_tokens"] > values["input_tokens"] or values["reasoning_output_tokens"] > values["output_tokens"] or values["total_tokens"] != values["input_tokens"] + values["output_tokens"]:
            raise ValueError("inconsistent usage counters")
        if last and any(values[key] < last["tokens"][key] for key in FIELDS):
            raise ValueError("usage counter reset; cannot subtract across it")
        current = {"timestamp": event["timestamp"], "tokens": values}
        at = timestamp(current["timestamp"])
        if last and at < timestamp(last["timestamp"]):
            raise ValueError("usage events are out of order")
        first = first or current
        last = current
        if since is not None and at <= since:
            before = current
    if last is None:
        raise ValueError("no measured usage counters")
    if since is not None and (before is None or timestamp(last["timestamp"]) <= since):
        raise ValueError("need counters on both sides of the requested boundary")
    return {"schema_version": 1, "source": "Codex session cumulative token_count",
            "first_observed_at": first["timestamp"], "through": last["timestamp"],
            "parent_totals": last["tokens"],
            "boundary_counter_at": before["timestamp"] if before else None,
            "since_boundary": {key: last["tokens"][key] - before["tokens"][key] for key in FIELDS} if before else None,
            "scope": "Selected session only. Separate subagent and exec sessions are excluded. Cached input and reasoning output are subsets, not additional tokens."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("session", type=Path)
    parser.add_argument("--since", type=timestamp)
    args = parser.parse_args()
    with args.session.open("rb") as stream:
        print(json.dumps(counters(stream, args.since), indent=2))


if __name__ == "__main__":
    main()
