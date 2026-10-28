#!/usr/bin/env python3
"""Experimental native-test frontend; no test framework or project semantics."""
import json
import os
from pathlib import Path
import sys

from native_command import command, command_passed


def main():
    root = Path(__file__).resolve().parent.parent
    try:
        with (root / '.loop/feedback.json').open('rb') as source:
            raw = source.read(1024 * 1024 + 1)
        if len(raw) > 1024 * 1024:
            raise ValueError('configuration exceeds limit')
        checks = json.loads(raw)['checks']
        if not isinstance(checks, dict):
            raise ValueError('expected checks')
    except (OSError, ValueError, KeyError, TypeError):
        print(json.dumps({'error': 'invalid feedback configuration'}))
        return 2
    names = sys.argv[1:]
    if not names or names == ['list']:
        print(json.dumps({'checks': checks}))
        return 0
    if len(names) > 16 or len(set(names)) != len(names):
        print(json.dumps({'error': 'select at most 16 distinct checks'}))
        return 2
    # Validate the whole batch before invoking any project command.
    for name in names:
        if name not in checks or not name.isidentifier():
            print(json.dumps({'error': 'unknown check'}))
            return 2
        argv = checks[name]
        if not isinstance(argv, list) or not 1 <= len(argv) <= 128 or any(not isinstance(a, str) or not a or len(a) > 65536 for a in argv):
            print(json.dumps({'error': 'invalid command argv'}))
            return 2
    logs = root / '.loop/logs'
    logs.mkdir(exist_ok=True)
    results = []
    for name in names:
        result, output = command(checks[name], root, os.environ, logs, name)
        passed = command_passed(result)
        with (logs / 'invocations.jsonl').open('a', encoding='utf-8') as audit:
            audit.write(json.dumps({'check': name, 'passed': passed, 'exit_code': result['exit_code']}) + '\n')
        excerpt = '' if passed else output[:2000] + (('\n...\n' + output[-2000:]) if len(output) > 4000 else output[2000:])
        results.append({'check': name, 'passed': passed, **result,
            'log_path': str(Path('.loop/logs') / (name + '.log')),
            'output_excerpt': excerpt, 'excerpt_truncated': not passed and len(output) > 4000})
        if not passed:
            break
    passed = len(results) == len(names) and all(r['passed'] for r in results)
    report = results[0] if len(names) == 1 else {'passed': passed, 'results': results, 'not_run': names[len(results):]}
    print(json.dumps(report))
    return 0 if passed else 1



if __name__ == '__main__':
    raise SystemExit(main())
