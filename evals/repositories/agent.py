#!/usr/bin/env python3
"""Measure native regression repair with natural tooling or prepared feedback."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from usage import summarise, MAX_EVENT_BYTES
from repositories.profiles import PROFILES
from repositories.native_command import command, command_passed
from repositories.run import mutation_detected

SYMPTOMS = {
    'loop-definition': 'Manifest parsing accepts unknown fields. Restore strict rejection while preserving valid manifests.',
    'landing-counters': 'Counter animation exceeds confirmed server totals after the animation duration. Restore clamping while preserving BigInt precision and decreasing counters.',
    'porsche-timestamp': 'The Last updated sensor reports unknown even when the vehicle provides a valid GLOBAL_TIMESTAMP. It must expose vehicle report time and remain unknown when that timestamp is absent.',
}


def digest_files(work, paths):
    return {p: hashlib.sha256((work / p).read_bytes()).hexdigest() if (work / p).is_file() else None for p in paths}


def grade_configured_checks(work, target, broken, env, output, marker):
    """Reject no-op and always-failing recipes using a pass/fail/pass contract."""
    repaired = target.read_bytes()
    grades = {}
    try:
        for phase, contents in (('repaired', repaired), ('regressed', broken), ('restored', repaired)):
            target.write_bytes(contents)
            for name in ('focused', 'suite'):
                result, text = command([sys.executable, str(work / '.loop/feedback.py'), name],
                                       work, env, output, f'configured-{phase}-{name}')
                if phase == 'regressed':
                    # Inspect the retained native log: compact excerpts may omit the assertion.
                    log = work / '.loop/logs' / (name + '.log')
                    native = log.read_text(errors='replace') if log.is_file() and log.stat().st_size <= 8 * 1024 * 1024 else ''
                    grades[f'{phase}_{name}'] = mutation_detected(result, native, marker)
                else:
                    grades[f'{phase}_{name}'] = command_passed(result)
    finally:
        target.write_bytes(repaired)
    return grades


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', choices=tuple(PROFILES), required=True)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--condition', choices=('natural', 'skill'), required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--discover-checks', action='store_true', help='Include native-check configuration in the measured task')
    parser.add_argument('--python', default='python3')
    parser.add_argument('--model', default='gpt-6.1-sol')
    parser.add_argument('--timeout', type=int, default=300)
    args = parser.parse_args()
    output, source = args.output.resolve(), args.source.resolve()
    output.mkdir(parents=True, exist_ok=False)
    profile = PROFILES[args.profile]
    revision = subprocess.check_output(['git', 'rev-parse', '--verify', profile.revision + '^{commit}'], cwd=source, text=True).strip()
    harness_files = ('agent.py', 'profiles.py', 'run.py', 'native_command.py', 'feedback.py', 'skill/SKILL.md')
    harness_hash = hashlib.sha256(b''.join((HERE / p).read_bytes() for p in harness_files)).hexdigest()
    env = {k: os.environ[k] for k in ('PATH', 'HOME', 'TMPDIR', 'SYSTEMROOT', 'WINDIR') if k in os.environ}
    env.update(CGO_ENABLED='0', GOWORK='off')
    identity = {'schema_version': 1, 'experiment': 'native_component_adoption_v1' if args.discover_checks else 'native_component_repair_v2',
        'profile': args.profile, 'condition': args.condition, 'source_revision': revision,
        'harness_sha256': harness_hash, 'model': args.model, 'reasoning_effort': 'low',
        'codex_version': subprocess.check_output(['codex', '--version'], text=True).strip()}
    def fail_preflight(phase, evidence):
        report = {**identity, 'passed': False, 'model_started': False, 'usage': summarise([]),
                  'checks': {'preflight': False}, 'failure_phase': phase, 'preflight': evidence}
        (output / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
        print(json.dumps(report, indent=2))
    with tempfile.TemporaryDirectory(prefix='loop-native-agent-') as temp:
        work = Path(temp) / 'project'
        work.mkdir()
        archive = Path(temp) / 'source.tar'
        subprocess.run(['git', 'archive', '--format=tar', '--output', str(archive), revision], cwd=source, check=True)
        with tarfile.open(archive) as tar:
            paths = [m.name for m in tar.getmembers() if m.isfile() and m.name != profile.mutation_file]
            tar.extractall(work, filter='data')
        protected = digest_files(work, paths)
        env['PYTHONPATH'] = str(work)
        env['GOCACHE'] = str(work / '.eval-cache')
        focused = [args.python if a == '{python}' else a for a in profile.focus]
        suite = [args.python if a == '{python}' else a for a in profile.suite]
        setup = []
        for i, argv in enumerate(profile.setup):
            result, _ = command(argv, work, env, output, f'setup-{i}')
            setup.append(result)
            if not command_passed(result):
                fail_preflight('setup', setup)
                return
        baseline, _ = command(focused, work, env, output, 'baseline')
        target = work / profile.mutation_file
        original = target.read_bytes()
        if not command_passed(baseline) or original.count(profile.before.encode()) != 1:
            fail_preflight('baseline_or_anchor', {'setup': setup, 'baseline': baseline})
            return
        broken = original.replace(profile.before.encode(), profile.after.encode())
        target.write_bytes(broken)
        mutation, text = command(focused, work, env, output, 'mutation')
        if not mutation_detected(mutation, text, profile.failure_marker):
            fail_preflight('mutation', {'baseline': baseline, 'mutation': mutation})
            return
        if args.condition == 'skill':
            feedback = work / '.loop'
            feedback.mkdir(exist_ok=True)
            for name in ('native_command.py', 'feedback.py'):
                shutil.copyfile(HERE / name, feedback / name)
            if not args.discover_checks:
                (feedback / 'feedback.json').write_text(json.dumps({'checks': {'focused': focused, 'suite': suite}}))
            skill = work / '.agents/skills/loop-feedback'
            skill.mkdir(parents=True)
            shutil.copyfile(HERE / 'skill/SKILL.md', skill / 'SKILL.md')
        helper_paths = ['.loop/native_command.py', '.loop/feedback.py', '.loop/feedback.json'] if args.condition == 'skill' else []
        if args.discover_checks and '.loop/feedback.json' in helper_paths:
            helper_paths.remove('.loop/feedback.json')
        prepared = digest_files(work, helper_paths)
        subprocess.run(['git', 'init', '-q'], cwd=work, check=True)
        # Keep generated caches out of discovery without changing source guidance.
        (work / '.git/info/exclude').write_text('.eval-cache/\n.loop/logs/\nnode_modules/\n__pycache__/\n')
        prompt = f'''Repair this regression in {profile.mutation_file}: {SYMPTOMS[args.profile]}
Use existing native tests and change only the affected production file; do not
weaken or modify tests, dependency versions or test configuration. This is an
isolated component-repair evaluation, not a release: run the focused component
checks and its native language suite. Browser, database and deployment gates are
outside this experiment and must not be claimed as passed. Work only in this
workspace; do not publish, contact live services or read other projects.
Dependencies are prepared. The Python test interpreter is {args.python}.
'''
        if args.condition == 'skill':
            prompt += 'Use .agents/skills/loop-feedback/SKILL.md for native feedback.\n'
            if args.discover_checks:
                prompt += 'Also create .loop/feedback.json by discovering existing focused and native suite commands. This new helper configuration is permitted; preserve all existing test configuration.\n'
        started = time.monotonic()
        with (output / 'events.jsonl').open('wb') as events, (output / 'stderr.txt').open('wb') as stderr:
            try:
                proc = subprocess.run(['codex', '--no-daemon', 'exec', '--ignore-user-config',
                    '--ephemeral', '--json', '--model', args.model, '-c', 'model_reasoning_effort="low"',
                    '--sandbox', 'workspace-write', '-c', 'approval_policy="never"',
                    '-c', 'sandbox_workspace_write.network_access=true',
                    '-c', 'shell_environment_policy.set.GOCACHE=' + json.dumps(env['GOCACHE']),
                    '-c', 'shell_environment_policy.set.PYTHONPATH=' + json.dumps(str(work)),
                    '-C', str(work), '-'], input=prompt.encode(), env=env, stdout=events,
                    stderr=stderr, timeout=args.timeout)
                exit_code = proc.returncode
            except subprocess.TimeoutExpired:
                exit_code = None
        elapsed = time.monotonic() - started
        with (output / 'events.jsonl').open('rb') as stream:
            usage = summarise(iter(lambda: stream.readline(MAX_EVENT_BYTES + 1), b''))
        focused_result, _ = command(focused, work, env, output, 'grade-focused')
        suite_result, _ = command(suite, work, env, output, 'grade-suite')
        checks = {'model_completed': exit_code == 0, 'protected_files_unchanged': protected == digest_files(work, paths),
            'focused_tests': command_passed(focused_result), 'native_suite': command_passed(suite_result)}
        observed = []
        if args.condition == 'skill':
            checks['helper_unchanged'] = prepared == digest_files(work, helper_paths)
            audit = work / '.loop/logs/invocations.jsonl'
            if audit.is_file():
                with audit.open('rb') as stream:
                    raw = stream.read(65537)
                if len(raw) <= 65536:
                    try:
                        observed = [json.loads(line)['check'] for line in raw.splitlines()]
                    except (ValueError, KeyError, TypeError):
                        observed = []
        configured = {}
        if args.condition == 'skill' and args.discover_checks:
            configured = grade_configured_checks(work, target, broken, env, output, profile.failure_marker)
            checks['configured_checks_detect_regression'] = all(configured.values())
        (output / 'repaired-source.txt').write_bytes(target.read_bytes())
        result = {**identity, 'model_started': True,
            'feedback_checks_observed': observed, 'configured_check_grades': configured,
            'used_prepared_feedback': set(('focused', 'suite')).issubset(observed) if args.condition == 'skill' else None,
            'duration_seconds': round(elapsed, 3), 'usage': usage, 'checks': checks,
            'passed': all(checks.values()), 'preflight': {'setup': setup, 'baseline': baseline, 'mutation': mutation}}
        (output / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
