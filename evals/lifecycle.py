#!/usr/bin/env python3
"""Measure cumulative API-verification work with natural tooling or optional Loop."""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import time
import uuid

from agent import ROOT, checked, run
from usage import summarise, MAX_EVENT_BYTES

TOKEN = "local-eval-fixture"
PRIVATE = "private-provider-fixture-detail"
STAGES = (
    "Verify that the running API reports car_soc=50 and battery_soc=80.",
    "Extend verification: an invalid bearer token must be rejected with HTTP 401. Keep verifying the valid-token status. Ordinary verification output must not expose the token or private HTTP error bodies.",
    "The API route changed from /api/status to /api/state; the old route now returns 404. Update your tooling and verification, retaining status and invalid-token checks.",
    "Verify the latest state: car_soc=75 and battery_soc=40. Retain the invalid-token check. Reuse or adapt existing work as you see fit.",
)
CONTRACT = """This is an isolated, synthetic Energy-style JSON API, not production Energy.
Base URL is ENERGY_API_URL. Bearer token is ENERGY_API_TOKEN. Both are provided
as environment variables to your commands. The public fixture token is
local-eval-fixture; no production secrets are present. The current status route
is {route}, serving JSON fields car_soc and battery_soc. Invalid bearer tokens
return HTTP 401. API error bodies are private diagnostics and should not be
printed by verification commands. No POST or other mutations are supported.
"""
GUIDANCE = """Work only in this workspace and against the provided local API. Use whatever
testing approach you naturally consider suitable: existing tests, shell commands,
new scripts or reusable helpers. You may retain, reuse or refactor any artefacts
between tasks. Do not publish, access external services or read other projects.
Test the actual running local API for these integration checks; a replacement mock
cannot establish its behaviour. At completion, write verification.json containing
an object with an argv array for a repeatable verification command. It must run
from this directory, consume ENERGY_API_URL and ENERGY_API_TOKEN from the
environment, exit 0 only when the requested checks pass, and exit non-zero on
regressions. Run it before finishing. Do not hardcode the URL or token in code.
"""


class Fixture:
    def __init__(self, token=TOKEN):
        self.token = token
        self.stage = 0
        self.variant = "normal"
        self.calls = []
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                outer.calls.append({"path": self.path, "client": self.headers.get("User-Agent", "")})
                status, body = outer.response(self.path, self.headers.get("Authorization"))
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(body).encode())

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    @property
    def route(self):
        return "/api/state" if self.stage >= 2 else "/api/status"

    def response(self, path, auth):
        if path != "/admin" + self.route:
            return 404, {"private": PRIVATE}
        if auth != "Bearer " + self.token and self.variant != "auth_bypass":
            return 401, {"private": PRIVATE}
        car, battery = (75, 40) if self.stage == 3 else (50, 80)
        return 200, {"car_soc": car + (1 if self.variant == "wrong_state" else 0), "battery_soc": battery + (1 if self.variant == "wrong_battery" else 0)}

    def close(self):
        self.server.shutdown()
        self.thread.join()
        self.server.server_close()


def grade(work, env, fixture):
    try:
        argv = json.loads((work / "verification.json").read_text())["argv"]
        if not isinstance(argv, list) or not 1 <= len(argv) <= 32 or any(not isinstance(a, str) or not a or len(a) > 65536 for a in argv):
            raise ValueError("invalid verification argv")
    except (OSError, ValueError, KeyError, TypeError):
        return {"verification_command": False}
    checks = {"verification_command": True}
    fixture.verification_calls = None
    original_token = fixture.token
    fixture.token = "rotated-fixture-" + uuid.uuid4().hex
    env = dict(env, ENERGY_API_TOKEN=fixture.token)
    variants = ["normal", "wrong_state", "wrong_battery"] + (["auth_bypass"] if fixture.stage >= 1 else [])
    try:
        for variant in variants:
            fixture.variant, fixture.calls = variant, []
            try:
                result = run(argv, work, env, timeout=30)
            except (OSError, subprocess.SubprocessError):
                checks[variant] = False
                continue
            if variant == "normal":
                fixture.verification_calls = {"total": len(fixture.calls), "loop_client": sum(c["client"] == "loop-cli-adk" for c in fixture.calls)}
            output = result.stdout + result.stderr
            checks[variant] = (bool(fixture.calls) and
                ((result.returncode == 0) if variant == "normal" else (result.returncode != 0)) and
                TOKEN not in output and fixture.token not in output and PRIVATE not in output)
    finally:
        fixture.variant = "normal"
        fixture.token = original_token
    return checks


def measure(work, output, prompt, env, model, timeout):
    started = time.monotonic()
    with (output / "events.jsonl").open("wb") as events, (output / "stderr.txt").open("wb") as stderr:
        try:
            result = subprocess.run(["codex", "--no-daemon", "exec", "--ignore-user-config",
                "--ephemeral", "--json", "--model", model, "-c", 'model_reasoning_effort="low"',
                "--sandbox", "workspace-write", "-c", 'approval_policy="never"',
                "-c", "sandbox_workspace_write.network_access=true",
                "-c", "shell_environment_policy.set.ENERGY_API_URL=" + json.dumps(env["ENERGY_API_URL"]),
                "-c", "shell_environment_policy.set.ENERGY_API_TOKEN=" + json.dumps(env["ENERGY_API_TOKEN"]),
                *(["-c", "shell_environment_policy.set.LOOP_EXECUTABLE=" + json.dumps(env["LOOP_EXECUTABLE"])] if "LOOP_EXECUTABLE" in env else []),
                "-C", str(work), "-"],
                input=prompt.encode(), stdout=events, stderr=stderr, env=env, timeout=timeout)
            code = result.returncode
        except subprocess.TimeoutExpired:
            code = None
    with (output / "events.jsonl").open("rb") as stream:
        usage = summarise(iter(lambda: stream.readline(MAX_EVENT_BYTES + 1), b""))
    return {"exit_code": code, "duration_seconds": round(time.monotonic() - started, 3), "usage": usage}


def stage_passed(exit_code, checks):
    return exit_code == 0 and bool(checks) and all(checks.values())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--condition", choices=("natural", "loop"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model", default="gpt-6.1-sol")
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--loop-mode", choices=("scaffold", "runner"), default="scaffold")
    parser.add_argument("--sdk", type=Path, default=ROOT)
    parser.add_argument("--verification-mode", choices=("free", "native", "declarative"), default="free")
    args = parser.parse_args()
    if args.verification_mode != "free" and (args.condition != "loop" or args.loop_mode != "runner"):
        parser.error("verification prototypes require --condition loop --loop-mode runner")
    sdk = args.sdk.resolve()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    with tempfile.TemporaryDirectory(prefix="loop-lifecycle-") as temp:
        work = Path(temp) / "project"
        work.mkdir()
        env = dict(os.environ, CGO_ENABLED="0", GOWORK="off", GOCACHE=str(work / ".eval-cache"))
        (work / "AGENTS.md").write_text(GUIDANCE)
        (work / ".gitignore").write_text("/.eval-cache/\n/bin/\n")
        checked(["git", "init", "-q"], work, env)
        setup = ""
        if args.condition == "loop":
            tools = Path(temp) / "tools"
            tools.mkdir()
            loop = tools / ("loop.exe" if os.name == "nt" else "loop")
            checked(["go", "build", "-o", str(loop), "./cmd/loop"], sdk, env)
            env["LOOP_EXECUTABLE"] = str(loop)
            env["PATH"] = str(tools) + os.pathsep + env["PATH"]
            setup = """For this condition, first use `loop init --name energyctl --dir cli`
to create a reusable project CLI for the documented API. Adapt its example binding
and tests, and build the CLI. Use the generated skills where useful. Count this
as setup work, not a reason to skip the verification deliverable. After setup,
choose how to use the CLI alongside other testing tools as you see fit.
"""
            if args.loop_mode == "runner":
                setup = """For this condition, use the installed Loop manifest runner for the documented
API. Create a small project.json and invoke `loop run --manifest project.json --
status get`. Use `loop --help` for available commands. A named standalone CLI is
not required for this development workflow. Choose how to combine Loop with other
testing tools, retaining useful work between tasks.
"""
            setup += "Available Loop executable: " + str(loop) + "\n"
        if args.verification_mode != "free":
            prototype = ROOT / "evals/prototypes"
            shutil.copyfile(prototype / "loop_verify.py", work / "loop_verify.py")
            shutil.copyfile(prototype / "README.md", work / "VERIFICATION.md")
            (work / "AGENTS.md").write_text(GUIDANCE + "\nFor this experiment, use the " + args.verification_mode + " interface described in VERIFICATION.md. Do not modify supplied loop_verify.py.\n")
            setup += "Read VERIFICATION.md. Use its " + args.verification_mode + " interface for this experiment. The supplied helper is reusable kit code; do not modify it. Create and maintain your own checks.\n"
        fixture = Fixture()
        env.update(ENERGY_API_URL=f"http://127.0.0.1:{fixture.server.server_port}/admin", ENERGY_API_TOKEN=TOKEN)
        results = []
        try:
            for index, task in enumerate(STAGES):
                fixture.stage = index
                fixture.verification_calls = None
                (work / "API.md").write_text(CONTRACT.format(route=fixture.route))
                stage = output / str(index)
                stage.mkdir()
                prompt = GUIDANCE + "\nRead API.md. " + task + "\n" + (setup if index == 0 else "")
                result = measure(work, stage, prompt, env, args.model, args.timeout)
                checks = grade(work, env, fixture) if result["exit_code"] == 0 else {}
                if args.verification_mode != "free":
                    helper = work / "loop_verify.py"
                    checks["supplied_helper_unchanged"] = helper.is_file() and helper.read_bytes() == (ROOT / "evals/prototypes/loop_verify.py").read_bytes()
                if args.condition == "loop" and index == 0 and args.loop_mode == "scaffold":
                    checks["cli_scaffolded"] = (work / "cli/project.json").is_file()
                result.update(stage=index, task=task, checks=checks, verification_calls=getattr(fixture, "verification_calls", None), passed=stage_passed(result["exit_code"], checks))
                results.append(result)
                (stage / "result.json").write_text(json.dumps(result, indent=2) + "\n")
                print(json.dumps({"condition": args.condition, **result}), flush=True)
            shutil.copytree(work, output / "artifact", ignore=shutil.ignore_patterns(".git", ".eval-cache", ".tmp", "bin"))
        finally:
            fixture.close()
        report = {"schema_version": 1, "experiment": "natural_workflow_amortisation_pilot",
            "condition": args.condition, "verification_mode": args.verification_mode, "loop_mode": args.loop_mode if args.condition == "loop" else None, "model": args.model, "reasoning_effort": "low",
            "harness_sha256": hashlib.sha256(Path(__file__).read_bytes() + (ROOT / "evals/prototypes/loop_verify.py").read_bytes() + (ROOT / "evals/prototypes/README.md").read_bytes()).hexdigest(),
            "loop_revision": checked(["git", "rev-parse", "HEAD"], sdk, env).stdout.strip(),
            "codex_version": checked(["codex", "--version"], ROOT, env).stdout.strip(),
            "fixture": "synthetic Energy-style read API; not actual Energy handlers",
            "stages": results, "passed": all(r["passed"] for r in results)}
        (output / "result.json").write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
