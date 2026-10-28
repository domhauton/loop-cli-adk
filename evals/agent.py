#!/usr/bin/env python3
"""Run one isolated, opt-in development trial; model calls consume account usage."""
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
from urllib.parse import parse_qs, urlsplit

from usage import summarise, MAX_EVENT_BYTES

ROOT = Path(__file__).resolve().parents[1]
TASK = """Extend this project CLI with `billing day`. The admin API contract is GET
/api/billing with required string query parameter `day`, returning a JSON object.
Keep `status get` working. Use the shared runtime and add meaningful offline tests
for the new command, including path/query encoding, an API base path prefix,
bearer auth, invalid input and an upstream error. Run the relevant checks.
Do not change dependencies or the runtime. Do not publish, browse, access live
services or use tools outside this workspace. Stop when implementation and tests
are complete. The local SDK replacement is intentional evaluation setup.
"""


def run(argv, cwd, env, timeout=180):
    return subprocess.run(argv, cwd=cwd, env=env, capture_output=True, text=True,
                          timeout=timeout)


def checked(argv, cwd, env):
    result = run(argv, cwd, env)
    if result.returncode:
        raise RuntimeError(result.stdout + result.stderr)
    return result


def error_code(text):
    try:
        return json.loads(text)["error"]["code"]
    except (ValueError, TypeError, KeyError):
        return None


def grade(work, env):
    """Exercise the artifact independently; the candidate never sees this oracle."""
    binary = work / ("candidate.exe" if os.name == "nt" else "candidate")
    build = run(["go", "build", "-o", str(binary), "."], work, env)
    checks = {"build": build.returncode == 0}
    if not checks["build"]:
        return checks
    requests = []
    upstream = [200]

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            parsed = urlsplit(self.path)
            requests.append((parsed.path, parse_qs(parsed.query), self.headers.get("Authorization")))
            self.send_response(upstream[0])
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"day":"fixture","total":12.5}' if upstream[0] == 200 else b'{"secret":"private-provider-diagnostic"}')

    with ThreadingHTTPServer(("127.0.0.1", 0), Handler) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        api_env = dict(env, ENERGYCTL_API_URL=f"http://127.0.0.1:{server.server_port}/admin", ENERGYCTL_API_TOKEN="eval-fixture-token")
        try:
            def invoke(args):
                return run([str(binary), *args], work, api_env, timeout=15)
            day = "2026-10-28 &extra=true+雪"
            result = invoke(["billing", "day", "--input", json.dumps({"day": day})])
            checks["request_contract"] = requests == [("/admin/api/billing", {"day": [day]}, "Bearer eval-fixture-token")]
            checks["json_result"] = result.returncode == 0 and result.stderr == "" and json.loads(result.stdout or "null") == {"day": "fixture", "total": 12.5}
            for label, data in (("missing_required", {}), ("unknown_input", {"day": "x", "extra": "y"}), ("wrong_type", {"day": 1})):
                before = len(requests)
                result = invoke(["billing", "day", "--input", json.dumps(data)])
                checks[label] = result.returncode == 2 and not result.stdout and len(requests) == before and error_code(result.stderr) == "invalid_input"
            upstream[0] = 503
            result = invoke(["billing", "day", "--input", '{"day":"2026-10-28"}'])
            checks["safe_upstream_error"] = (result.returncode == 1 and not result.stdout and error_code(result.stderr) == "http_status" and
                "private-provider-diagnostic" not in result.stderr and "eval-fixture-token" not in result.stderr)
        finally:
            server.shutdown()
            thread.join()
    checks["candidate_tests_pass"] = run(["go", "test", "-short", "./..."], work, env).returncode == 0
    # Mutation checks distinguish useful tests from tests that simply repeat success.
    manifest = work / "project.json"
    original = manifest.read_bytes()
    for label in ("path", "query", "required"):
        data = json.loads(original)
        command = next((c for c in data["commands"] if c["name"] == "billing day"), None)
        if command is None:
            checks["tests_detect_" + label] = False
            continue
        if label == "path":
            command["http"]["path"] = "/wrong-endpoint"
        elif label == "query":
            command["http"]["query"] = {"day": "wrong_parameter"}
        else:
            command["input"]["day"]["required"] = False
        try:
            manifest.write_text(json.dumps(data))
            checks["tests_detect_" + label] = checks["candidate_tests_pass"] and run(["go", "test", "-short", "./..."], work, env).returncode != 0
        finally:
            manifest.write_bytes(original)
    return checks


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--condition", choices=("baseline", "skill"), required=True)
    parser.add_argument("--output", type=Path, required=True, help="new directory for local transcripts and result")
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--model", default="gpt-6.1-sol")
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    env = dict(os.environ, CGO_ENABLED="0", GOWORK="off", GOPROXY="off", GOSUMDB="off")
    with tempfile.TemporaryDirectory(prefix="loop-agent-eval-") as temp:
        work = Path(temp) / "energyctl"
        checked(["go", "run", "./cmd/loop", "init", "--name", "energyctl", "--dir", str(work)], ROOT, env)
        checked(["go", "mod", "edit", "-replace", "github.com/domhauton/loop-cli-adk=" + str(ROOT)], work, env)
        # Both conditions get identical code and project conventions. Only the
        # development skill differs; release guidance is irrelevant to this task.
        shutil.rmtree(work / ".agents")
        (work / "AGENTS.md").write_text("Use the shared Loop runtime. Keep command configuration in project.json. Tests use local HTTP fixtures.\n")
        if args.condition == "skill":
            skill = work / ".agents/skills/energyctl-develop"
            skill.mkdir(parents=True)
            text = (ROOT / "internal/authoring/templates/develop-skill.md.tmpl").read_text()
            for name, value in (("Name", "energyctl"), ("BaseURLEnv", "ENERGYCTL_API_URL"), ("TokenEnv", "ENERGYCTL_API_TOKEN")):
                text = text.replace("[[." + name + "]]", value)
            (skill / "SKILL.md").write_text(text)
        with (work / ".gitignore").open("a") as ignore:
            ignore.write("\n/.eval-cache/\n")
        env["GOCACHE"] = str(work / ".eval-cache")
        checked(["go", "test", "-short", "./..."], work, env)
        prompt = TASK + ("\nUse .agents/skills/energyctl-develop/SKILL.md.\n" if args.condition == "skill" else "")
        checked(["git", "init", "-q"], work, env)
        started = time.monotonic()
        command = ["codex", "--no-daemon", "exec", "--ignore-user-config", "--ephemeral", "--json",
                   "--model", args.model, "-c", 'model_reasoning_effort="low"',
                   "--sandbox", "workspace-write", "-c", 'approval_policy="never"',
                   "-c", "sandbox_workspace_write.network_access=true", "-C", str(work), "-"]
        timed_out = False
        with (output / "events.jsonl").open("wb") as events, (output / "stderr.txt").open("wb") as stderr:
            try:
                process = subprocess.run(command, input=prompt.encode(), stdout=events, stderr=stderr,
                                         env=env, timeout=args.timeout)
                exit_code = process.returncode
            except subprocess.TimeoutExpired:
                exit_code, timed_out = None, True
        elapsed = time.monotonic() - started
        with (output / "events.jsonl").open("rb") as stream:
            usage = summarise(iter(lambda: stream.readline(MAX_EVENT_BYTES + 1), b""))
        shutil.copytree(work, output / "artifact", ignore=shutil.ignore_patterns(".git", ".eval-cache", ".tmp", "candidate", "candidate.exe"))
        harness_error = None
        try:
            checks = grade(work, env) if exit_code == 0 else {}
        except (OSError, ValueError, subprocess.SubprocessError) as error:
            checks, harness_error = {}, type(error).__name__ + ": " + str(error)
        result = {"schema_version": 1, "experiment_version": 1,
                  "harness_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  "task_sha256": hashlib.sha256(TASK.encode()).hexdigest(),
                  "skill_sha256": hashlib.sha256((ROOT / "internal/authoring/templates/develop-skill.md.tmpl").read_bytes()).hexdigest(),
                  "loop_revision": checked(["git", "rev-parse", "HEAD"], ROOT, env).stdout.strip(), "task": "add_billing_day", "condition": args.condition,
                  "codex_version": checked(["codex", "--version"], ROOT, env).stdout.strip(),
                  "model": args.model, "reasoning_effort": "low", "exit_code": exit_code,
                  "timed_out": timed_out, "harness_error": harness_error, "duration_seconds": round(elapsed, 3),
                  "usage": usage, "checks": checks,
                  "passed": bool(checks) and all(checks.values())}
        (output / "result.json").write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
