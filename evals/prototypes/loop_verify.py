"""Experimental verification adapter. Not part of Loop's supported runtime API."""
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid


class VerificationError(Exception):
    """Safe failure without credential values or upstream response bodies."""


class Client:
    def __init__(self, manifest="project.json"):
        self.manifest = manifest

    def call(self, command, *, invalid_token=False):
        env = dict(os.environ)
        if invalid_token:
            definition = json.loads(Path(self.manifest).read_text())
            token_env = definition["api"]["token_env"]
            env[token_env] = "invalid-" + uuid.uuid4().hex
        try:
            result = subprocess.run(
                [env.get("LOOP_EXECUTABLE", "loop"), "run", "--manifest", self.manifest, "--", *command],
                env=env, capture_output=True, text=True, timeout=35)
            data = json.loads(result.stdout if result.returncode == 0 else result.stderr)
        except (OSError, subprocess.SubprocessError, ValueError):
            raise VerificationError("Loop invocation failed; diagnostics withheld") from None
        return result.returncode, data

    def expect_json(self, command, expected):
        code, data = self.call(command)
        if code != 0 or not matches(data, expected):
            raise VerificationError("JSON expectation failed")

    def expect_http_status(self, command, status, *, invalid_token=False):
        code, data = self.call(command, invalid_token=invalid_token)
        if (code != 1 or not isinstance(data, dict)
                or not matches(data, {"error": {"code": "http_status", "details": {"http_status": str(status)}}})):
            raise VerificationError("HTTP status expectation failed")


def matches(actual, expected):
    """Object subset matching; arrays and primitive values match exactly by type."""
    if type(actual) is not type(expected):
        return False
    if isinstance(expected, dict):
        return all(key in actual and matches(actual[key], value) for key, value in expected.items())
    if isinstance(expected, list):
        return len(actual) == len(expected) and all(matches(a, b) for a, b in zip(actual, expected))
    return actual == expected


def verify_suite(path):
    suite = json.loads(Path(path).read_text())
    if set(suite) != {"manifest", "checks"} or not isinstance(suite["checks"], list) or not suite["checks"]:
        raise VerificationError("Expected manifest and non-empty checks")
    client = Client(suite["manifest"])
    for check in suite["checks"]:
        if set(check) == {"command", "json_subset"}:
            client.expect_json(check["command"], check["json_subset"])
        elif set(check) == {"command", "http_status", "invalid_token"} and check["invalid_token"] is True:
            client.expect_http_status(check["command"], check["http_status"], invalid_token=True)
        else:
            raise VerificationError("Unsupported check")


def main():
    try:
        if len(sys.argv) != 2:
            raise VerificationError("Usage: python3 loop_verify.py checks.json")
        verify_suite(sys.argv[1])
    except (VerificationError, OSError, ValueError, KeyError, TypeError):
        print("Verification failed; diagnostics withheld", file=sys.stderr)
        return 1
    print("Verification passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
