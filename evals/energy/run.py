#!/usr/bin/env python3
"""Run Loop against committed Energy handlers without changing their checkout."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
import time

PIN = "8c3792048d6f4665fc5d35d815fd3e592c8a1bd2"
ROOT = Path(__file__).resolve().parents[2]


def run(argv, *, cwd, env=None, timeout=180):
    return subprocess.run(argv, cwd=cwd, env=env, check=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          text=True, timeout=timeout)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--automations", type=Path, required=True)
    parser.add_argument("--revision", default=PIN)
    args = parser.parse_args()
    source = args.automations.resolve()
    revision = run(["git", "rev-parse", "--verify", args.revision + "^{commit}"], cwd=source).stdout.strip()
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="loop-energy-") as directory:
        work = Path(directory)
        archive = work / "source.tar"
        run(["git", "archive", "--format=tar", "--output", str(archive), revision], cwd=source)
        snapshot = work / "automations"
        snapshot.mkdir()
        with tarfile.open(archive) as tar:
            tar.extractall(snapshot, filter="data")
        shutil.copyfile(ROOT / "evals/energy/loop_integration_test.go.txt",
                        snapshot / "internal/energy/electricity/loop_integration_test.go")
        binary = work / ("energy.exe" if os.name == "nt" else "energy")
        env = dict(os.environ, CGO_ENABLED="0", GOWORK="off")
        run(["go", "run", "./cmd/loop", "build", "--manifest", "examples/energy/project.json",
             "--sdk-dir", str(ROOT), "--output", str(binary)], cwd=ROOT, env=env)
        env["LOOP_ENERGY_BINARY"] = str(binary)
        result = run(["go", "test", "-json", "-count=1", "-run", "^TestLoopEnergy$",
                      "./internal/energy/electricity"], cwd=snapshot, env=env)
        events = [json.loads(line) for line in result.stdout.splitlines()]
        passed = [e["Test"] for e in events if e.get("Action") == "pass" and "Test" in e]
        print(json.dumps({"schema_version": 1, "source_revision": revision,
                          "loop_revision": run(["git", "rev-parse", "HEAD"], cwd=ROOT).stdout.strip(),
                          "loop_dirty": bool(run(["git", "status", "--porcelain"], cwd=ROOT).stdout),
                          "passed": passed, "duration_seconds": round(time.monotonic()-started, 3),
                          "model_tokens": None, "kind": "offline_integration"}, indent=2))


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as error:
        print(error.stdout or "", end="")
        print(error.stderr or "", end="")
        raise SystemExit(error.returncode)
