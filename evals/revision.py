#!/usr/bin/env python3
"""Run the CI revision-comparison task locally using the authenticated Codex CLI."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace

from agent import checked
from ci import prepare, assess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sdk', type=Path, required=True)
    parser.add_argument('--condition', choices=('baseline', 'candidate'), required=True)
    parser.add_argument('--trial', type=int, choices=(1, 2, 3), required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--model', default='gpt-6.1-sol')
    parser.add_argument('--timeout', type=int, default=300)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    sdk = args.sdk.resolve()
    with tempfile.TemporaryDirectory(prefix='loop-revision-eval-') as temp:
        work = Path(temp) / 'project'
        metadata, prompt = output / 'metadata.json', output / 'prompt.txt'
        prepare(SimpleNamespace(sdk=sdk, workspace=work, prompt=prompt, metadata=metadata,
            condition=args.condition, trial=args.trial, model=args.model))
        env = dict(os.environ, CGO_ENABLED='0', GOWORK='off', GOCACHE=str(work / '.eval-cache'))
        with (output / 'events.jsonl').open('wb') as events, (output / 'stderr.txt').open('wb') as stderr:
            try:
                result = subprocess.run(['codex', '--no-daemon', 'exec', '--ignore-user-config',
                    '--ephemeral', '--json', '--model', args.model, '-c', 'model_reasoning_effort="low"',
                    '--sandbox', 'workspace-write', '-c', 'approval_policy="never"',
                    '-c', 'sandbox_workspace_write.network_access=true', '-C', str(work), '-'],
                    input=prompt.read_bytes(), stdout=events, stderr=stderr, env=env, timeout=args.timeout)
                outcome = 'success' if result.returncode == 0 else 'failure'
            except subprocess.TimeoutExpired:
                outcome = 'timeout'
        (output / 'outcome.txt').write_text(outcome)
        import shutil
        shutil.copytree(work, output / 'artifact', ignore=shutil.ignore_patterns('.git', '.eval-cache', '__pycache__'))
        data = json.loads(metadata.read_text())
        data['executor'] = 'local_codex_exec'
        data['codex_version'] = checked(['codex', '--version'], sdk, env).stdout.strip()
        metadata.write_text(json.dumps(data, indent=2) + '\n')
        assess(SimpleNamespace(sdk=sdk, workspace=work, metadata=metadata,
            log=output / 'events.jsonl', outcome=output / 'outcome.txt', output=output / 'result.json'))


if __name__ == '__main__':
    main()
