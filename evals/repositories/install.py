#!/usr/bin/env python3
"""Validate skill-only installation in an untouched, pinned project snapshot."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile

if __package__:
    from .profiles import PROFILES
    from .native_command import command, command_passed
else:
    from profiles import PROFILES
    from native_command import command, command_passed

SKILL = '.agents/skills/trial-native-test/SKILL.md'


def snapshot(root):
    """Record content, link targets and permissions without following symlinks."""
    result = {}
    for path in root.rglob('*'):
        mode = path.lstat().st_mode
        if path.is_symlink():
            value = ('symlink', os.readlink(path), mode)
        elif path.is_file():
            digest = hashlib.sha256()
            with path.open('rb') as source:
                for chunk in iter(lambda: source.read(1024 * 1024), b''):
                    digest.update(chunk)
            value = ('file', digest.hexdigest(), mode)
        else:
            value = ('directory', '', mode)
        result[path.relative_to(root).as_posix()] = value
    return result


def verify_install(tool, work, logs):
    """Require exactly one new skill, preserved host state, and safe repeat failure."""
    before = snapshot(work)
    env = dict(os.environ, PATH='')
    argv = [*tool, 'init', '--mode', 'testing', '--name', 'trial', '--dir', str(work)]
    run, output = command(argv, work, env, logs, 'install')
    try:
        result = json.loads(output)
    except ValueError:
        result = {}
    after = snapshot(work)
    added = set(after) - set(before)
    allowed = {SKILL, '.agents', '.agents/skills', '.agents/skills/trial-native-test'}
    checks = {'installed': command_passed(run),
              'reported_one_skill': result.get('mode') == 'testing' and result.get('files') == [SKILL],
              'host_unchanged': all(after.get(p) == value for p, value in before.items()),
              'only_skill_added': SKILL in added and added <= allowed and after.get(SKILL, (None,))[0] == 'file'}
    repeated, _ = command(argv, work, env, logs, 'repeat')
    checks['repeat_rejected_without_changes'] = repeated['exit_code'] not in (None, 0) and not repeated['timed_out'] and snapshot(work) == after
    return {'passed': all(checks.values()), 'checks': checks, 'install': run, 'repeat': repeated}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', choices=tuple(PROFILES), required=True)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--loop', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    source, executable, output = args.source.resolve(), args.loop.resolve(), args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    revision = subprocess.check_output(['git', 'rev-parse', '--verify', PROFILES[args.profile].revision + '^{commit}'], cwd=source, text=True).strip()
    with tempfile.TemporaryDirectory(prefix='loop-skill-install-') as temp:
        work = Path(temp) / 'project'
        work.mkdir()
        archive = Path(temp) / 'source.tar'
        subprocess.run(['git', 'archive', '--format=tar', '--output', str(archive), revision], cwd=source, check=True)
        with tarfile.open(archive) as tar:
            tar.extractall(work, filter='data')
        result = verify_install([str(executable)], work, output)
    report = {'schema_version': 1, 'kind': 'native_testing_skill_installation', 'profile': args.profile,
              'source_revision': revision, 'loop_sha256': hashlib.sha256(executable.read_bytes()).hexdigest(),
              'model_tokens': None, **result}
    (output / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report['passed'] else 1)


if __name__ == '__main__':
    main()
