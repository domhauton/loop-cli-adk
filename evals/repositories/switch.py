#!/usr/bin/env python3
"""Prove a component-switch fixture distinguishes stale from relevant checks."""
import argparse
from dataclasses import replace
import json
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile

if __package__:
    from .profiles import PROFILES
    from .run import exercise, mutation_detected
    from .native_command import command, command_passed
else:
    from profiles import PROFILES
    from run import exercise, mutation_detected
    from native_command import command, command_passed


def cases():
    """Use separate sensor and configuration components at one pinned revision."""
    sensor = PROFILES['porsche-timestamp']
    config = replace(sensor,
        focus=('{python}', '-m', 'pytest', '--no-cov', '-q', 'tests/test_config_flow.py'),
        mutation_file='custom_components/porscheconnect/config_flow.py',
        before='entry_data.pop(field, None)', after='entry_data.get(field, None)',
        failure_marker='test_reconfigure_ignores_and_removes_stale_auth_data')
    return sensor, config


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--python', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    source, output = args.source.resolve(), args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    sensor, config = cases()
    revision = subprocess.check_output(['git', 'rev-parse', '--verify', sensor.revision + '^{commit}'], cwd=source, text=True).strip()
    env = {k: os.environ[k] for k in ('PATH', 'HOME', 'TMPDIR', 'SYSTEMROOT', 'WINDIR') if k in os.environ}
    with tempfile.TemporaryDirectory(prefix='loop-switch-preflight-') as temp:
        work = Path(temp) / 'project'
        work.mkdir()
        archive = Path(temp) / 'source.tar'
        subprocess.run(['git', 'archive', '--format=tar', '--output', str(archive), revision], cwd=source, check=True)
        with tarfile.open(archive) as tar:
            tar.extractall(work, filter='data')
        env['PYTHONPATH'] = str(work)
        results = []
        for index, case in enumerate((sensor, config), 1):
            logs = output / f'component-{index}'
            logs.mkdir()
            results.append(exercise(case, work, env, logs, args.python))
        stale_passes = relevant_detects = False
        if all(r['passed'] for r in results):
            target = work / config.mutation_file
            original = target.read_bytes()
            try:
                target.write_bytes(original.replace(config.before.encode(), config.after.encode()))
                stale, _ = command([args.python if a == '{python}' else a for a in sensor.focus], work, env, output, 'stale-focused')
                relevant, text = command([args.python if a == '{python}' else a for a in config.focus], work, env, output, 'relevant-focused')
                stale_passes = command_passed(stale)
                relevant_detects = mutation_detected(relevant, text, config.failure_marker)
            finally:
                target.write_bytes(original)
    report = {'schema_version': 1, 'kind': 'deterministic_component_switch', 'source_revision': revision,
              'model_tokens': None, 'components': results,
              'stale_sensor_check_passes_with_config_regression': stale_passes,
              'relevant_config_check_detects_regression': relevant_detects,
              'passed': all(r['passed'] for r in results) and stale_passes and relevant_detects}
    (output / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report['passed'] else 1)


if __name__ == '__main__':
    main()
