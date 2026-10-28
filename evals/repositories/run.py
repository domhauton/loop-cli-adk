#!/usr/bin/env python3
"""Exercise native feedback loops in pinned disposable repository snapshots."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile
import time

if __package__:
    from .profiles import PROFILES
    from .native_command import command, command_passed
else:
    from profiles import PROFILES
    from native_command import command, command_passed


def mutation_detected(result, text, marker):
    return (result['exit_code'] not in (0, None) and not result['timed_out']
            and result['output_within_limit'] and marker in text)


def exercise(profile, work, env, logs, python):
    def invoke(args, label):
        return command([python if a == '{python}' else a for a in args], work, env, logs, label)
    stages, passed = {}, False
    for index, argv in enumerate(profile.setup):
        label = 'setup_' + str(index)
        stages[label], _ = invoke(argv, label)
        if not command_passed(stages[label]):
            return {'passed': False, 'failure_phase': label, 'stages': stages}
    stages['baseline'], _ = invoke(profile.focus, 'baseline')
    if not command_passed(stages['baseline']):
        return {'passed': False, 'failure_phase': 'baseline', 'stages': stages}
    target = work / profile.mutation_file
    original = target.read_bytes()
    before, after = profile.before.encode(), profile.after.encode()
    if original.count(before) != 1:
        return {'passed': False, 'failure_phase': 'mutation_anchor', 'stages': stages}
    try:
        target.write_bytes(original.replace(before, after))
        stages['mutation'], text = invoke(profile.focus, 'mutation')
        detected = mutation_detected(stages['mutation'], text, profile.failure_marker)
    finally:
        target.write_bytes(original)
    stages['restored'], _ = invoke(profile.focus, 'restored')
    stages['native_suite'], _ = invoke(profile.suite, 'native-suite')
    passed = detected and all(command_passed(stages[k]) for k in ('restored', 'native_suite'))
    return {'passed': passed, 'mutation_detected': detected, 'source_restored': target.read_bytes() == original,
            'stages': stages, 'failure_phase': None if passed else 'verification'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', choices=tuple(PROFILES), required=True)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--python', default='python3', help='Prepared interpreter with the project test requirements installed')
    args = parser.parse_args()
    profile, source, output = PROFILES[args.profile], args.source.resolve(), args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    revision = subprocess.check_output(['git', 'rev-parse', '--verify', profile.revision + '^{commit}'], cwd=source, text=True).strip()
    env = {k: os.environ[k] for k in ('PATH', 'HOME', 'TMPDIR', 'SYSTEMROOT', 'WINDIR') if k in os.environ}
    env.update(CGO_ENABLED='0', GOWORK='off')
    with tempfile.TemporaryDirectory(prefix='loop-native-eval-') as temp:
        work = Path(temp) / 'project'
        work.mkdir()
        archive = Path(temp) / 'source.tar'
        subprocess.run(['git', 'archive', '--format=tar', '--output', str(archive), revision], cwd=source, check=True)
        with tarfile.open(archive) as tar:
            tar.extractall(work, filter='data')
        env['PYTHONPATH'] = str(work)
        result = exercise(profile, work, env, output, args.python)
    report = {'schema_version': 1, 'profile': args.profile, 'language': profile.language,
        'source_revision': revision, 'harness_sha256': hashlib.sha256(Path(__file__).read_bytes() + Path(__file__).with_name('profiles.py').read_bytes() + Path(__file__).with_name('native_command.py').read_bytes()).hexdigest(),
        'kind': 'native_repository_feedback', 'model_tokens': None,
        'scope': 'Existing focused tests and native language suite; not production, browser, database or full repository deployment validation.', **result}
    (output / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report['passed'] else 1)


if __name__ == '__main__':
    main()
