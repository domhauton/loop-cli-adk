#!/usr/bin/env python3
"""Measure adoption and subsequent repairs while retaining each arm's workspace."""
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

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from repositories.agent import digest_files, grade_configured_checks, invoke_agent
from repositories.native_command import command, command_passed
from repositories.profiles import PROFILES
from repositories.sequences import sequence
from repositories.run import mutation_detected


def observed_checks(work):
    """Read only this stage's bounded helper audit before independent grading."""
    try:
        with (work / '.loop/logs/invocations.jsonl').open('rb') as source:
            raw = source.read(65537)
        if len(raw) > 65536:
            return []
        return [json.loads(line)['check'] for line in raw.splitlines()]
    except (OSError, ValueError, KeyError, TypeError):
        return []


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', choices=tuple(PROFILES), required=True)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--condition', choices=('natural', 'skill'), required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--python', default='python3')
    parser.add_argument('--model', default='gpt-6.1-sol')
    parser.add_argument('--timeout', type=int, default=300)
    parser.add_argument('--preflight-only', action='store_true', help='Prove all mutations against native tests without model calls')
    args = parser.parse_args()
    source, output = args.source.resolve(), args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    stages = sequence(args.profile)
    base = stages[0][0]
    revision = subprocess.check_output(['git', 'rev-parse', '--verify', base.revision + '^{commit}'], cwd=source, text=True).strip()
    files = ('lifecycle.py', 'sequences.py', 'agent.py', 'profiles.py', 'native_command.py', 'feedback.py', 'run.py', 'skill/SKILL.md')
    report = {'schema_version': 1, 'experiment': 'native_retained_workspace_v1',
        'profile': args.profile, 'condition': args.condition, 'source_revision': revision,
        'harness_sha256': hashlib.sha256(b''.join((HERE / p).read_bytes() for p in files)).hexdigest(),
        'model': None if args.preflight_only else args.model, 'reasoning_effort': 'low',
        'codex_version': None if args.preflight_only else subprocess.check_output(['codex', '--version'], text=True).strip(),
        'expected_stages': len(stages), 'stages': [], 'passed': False,
        'preflight_only': args.preflight_only}
    env = {k: os.environ[k] for k in ('PATH', 'HOME', 'TMPDIR', 'SYSTEMROOT', 'WINDIR') if k in os.environ}
    env.update(CGO_ENABLED='0', GOWORK='off')
    with tempfile.TemporaryDirectory(prefix='loop-native-sequence-') as temp:
        work = Path(temp) / 'project'
        work.mkdir()
        archive = Path(temp) / 'source.tar'
        subprocess.run(['git', 'archive', '--format=tar', '--output', str(archive), revision], cwd=source, check=True)
        with tarfile.open(archive) as tar:
            paths = [m.name for m in tar.getmembers() if m.isfile() and m.name != base.mutation_file]
            tar.extractall(work, filter='data')
        protected = digest_files(work, paths)
        env.update(PYTHONPATH=str(work), GOCACHE=str(work / '.eval-cache'))
        setup_ok = True
        for i, argv in enumerate(base.setup):
            result, _ = command(argv, work, env, output, f'setup-{i}')
            if not command_passed(result):
                report['setup_failure'] = result
                setup_ok = False
                break
        helper_paths = []
        if args.condition == 'skill' and not args.preflight_only:
            (work / '.loop').mkdir(exist_ok=True)
            for name in ('native_command.py', 'feedback.py'):
                shutil.copyfile(HERE / name, work / '.loop' / name)
                helper_paths.append('.loop/' + name)
            skill = work / '.agents/skills/loop-feedback'
            skill.mkdir(parents=True)
            shutil.copyfile(HERE / 'skill/SKILL.md', skill / 'SKILL.md')
            helper_paths.append('.agents/skills/loop-feedback/SKILL.md')
        prepared = digest_files(work, helper_paths)
        subprocess.run(['git', 'init', '-q'], cwd=work, check=True)
        (work / '.git/info/exclude').write_text('.eval-cache/\n.loop/logs/\nnode_modules/\n__pycache__/\n')
        for index, (profile, symptom) in enumerate(stages if setup_ok else []):
            logs = output / f'stage-{index+1}'
            logs.mkdir()
            focused = [args.python if a == '{python}' else a for a in profile.focus]
            suite = [args.python if a == '{python}' else a for a in profile.suite]
            target = work / profile.mutation_file
            original = target.read_bytes()
            baseline, _ = command(focused, work, env, logs, 'baseline')
            stage = {'stage': index + 1, 'passed': False, 'baseline': baseline}
            report['stages'].append(stage)
            if not command_passed(baseline) or original.count(profile.before.encode()) != 1:
                stage['failure_phase'] = 'baseline_or_anchor'
                break
            broken = original.replace(profile.before.encode(), profile.after.encode())
            target.write_bytes(broken)
            mutation, text = command(focused, work, env, logs, 'mutation')
            stage['mutation'] = mutation
            if not mutation_detected(mutation, text, profile.failure_marker):
                stage['failure_phase'] = 'mutation'
                break
            if args.preflight_only:
                target.write_bytes(original)
                restored, _ = command(suite, work, env, logs, 'restored-suite')
                stage.update(passed=command_passed(restored), restored_suite=restored)
                if not stage['passed']:
                    break
                continue
            audit = work / '.loop/logs/invocations.jsonl'
            audit.unlink(missing_ok=True)
            prompt = f'''Repair this regression in {profile.mutation_file}: {symptom}
Use existing native tests. Change only this production file; preserve existing
tests, dependency versions and test configuration. You may create and retain local
testing helpers or notes. Earlier repairs and any helpers remain in this workspace.
Run focused component checks and the native language suite. This is an isolated
repair, not a release: browser, database and deployment gates are outside scope.
Work only here; do not publish, contact live services or read other projects.
Dependencies are prepared. The Python test interpreter is {args.python}.
'''
            if args.condition == 'skill':
                prompt += '''Use .agents/skills/loop-feedback/SKILL.md. Discover and create
.loop/feedback.json if absent; otherwise reuse or maintain its commands. This new
helper configuration may change, but preserve all original test configuration.
'''
            code, elapsed, usage = invoke_agent(work, logs, env, prompt, args.model, args.timeout)
            observed = observed_checks(work)
            focus_result, _ = command(focused, work, env, logs, 'grade-focused')
            suite_result, _ = command(suite, work, env, logs, 'grade-suite')
            checks = {'model_completed': code == 0, 'protected_files_unchanged': protected == digest_files(work, paths),
                      'focused_tests': command_passed(focus_result), 'native_suite': command_passed(suite_result)}
            if args.condition == 'skill':
                checks['helper_unchanged'] = prepared == digest_files(work, helper_paths)
                checks['helper_used'] = {'focused', 'suite'}.issubset(observed)
                grades = grade_configured_checks(work, target, broken, env, logs, profile.failure_marker)
                checks['configured_checks_detect_regression'] = all(grades.values())
                stage['configured_check_grades'] = grades
            stage.update(passed=all(checks.values()), checks=checks, usage=usage,
                         duration_seconds=round(elapsed, 3), feedback_checks_observed=observed)
            stage['evidence_sha256'] = hashlib.sha256((logs / 'events.jsonl').read_bytes()).hexdigest()
            # Do not erase natural helpers or reset repaired source between tasks.
            if not stage['passed']:
                break
        report['passed'] = len(report['stages']) == len(stages) and all(s['passed'] for s in report['stages'])
    (output / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
