#!/usr/bin/env python3
"""Experimental native-test frontend; no test framework or project semantics."""
import json
import os
from pathlib import Path
import sys

from native_command import command, command_passed


def main():
    root = Path(__file__).resolve().parent.parent
    settings = json.loads((root / '.loop/feedback.json').read_text())
    checks = settings['checks']
    if len(sys.argv) != 2 or sys.argv[1] == 'list':
        print(json.dumps({'checks': checks}))
        return 0
    name = sys.argv[1]
    if name not in checks or not name.isidentifier():
        print(json.dumps({'error': 'unknown check'}))
        return 2
    argv = checks[name]
    if not isinstance(argv, list) or not argv or any(not isinstance(a, str) or not a for a in argv):
        print(json.dumps({'error': 'invalid command argv'}))
        return 2
    logs = root / '.loop/logs'
    logs.mkdir(exist_ok=True)
    result, output = command(argv, root, os.environ, logs, name)
    passed = command_passed(result)
    # Successful test logs rarely change the next decision. Keep failures useful,
    # with an explicit truncation indicator and the complete bounded log on disk.
    excerpt = '' if passed else output[:2000] + (('\n...\n' + output[-2000:]) if len(output) > 4000 else output[2000:])
    print(json.dumps({'check': name, 'passed': passed, **result,
        'log_path': str(Path('.loop/logs') / (name + '.log')),
        'output_excerpt': excerpt, 'excerpt_truncated': not passed and len(output) > 4000}))
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())
