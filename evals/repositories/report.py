#!/usr/bin/env python3
"""Compare native repair trials per repository without pooling unlike tasks."""
import argparse
import hashlib
import json
from pathlib import Path
import statistics

IDENTITY = ('source_revision', 'harness_sha256', 'model', 'reasoning_effort', 'codex_version')


def aggregate(records):
    if not records or len({r['evidence_sha256'] for r in records}) != len(records):
        raise ValueError('expected distinct measured trial evidence')
    profiles = {}
    for profile in sorted({r['profile'] for r in records}):
        selected = [r for r in records if r['profile'] == profile]
        for key in IDENTITY:
            if len({r[key] for r in selected}) != 1:
                raise ValueError('incompatible ' + key + ' for ' + profile)
        if any(r['condition'] not in ('natural', 'skill') for r in selected):
            raise ValueError('unknown condition')
        groups = {}
        for condition in ('natural', 'skill'):
            runs = [r for r in selected if r['condition'] == condition]
            known = [r for r in runs if r['usage']['usage_complete']]
            costs = [{**r['usage']['tokens'],
                'uncached_input_tokens': r['usage']['tokens']['input_tokens'] - r['usage']['tokens']['cached_input_tokens'],
                'total_tokens': r['usage']['tokens']['input_tokens'] + r['usage']['tokens']['output_tokens']} for r in known]
            groups[condition] = {'trials': len(runs), 'passed': sum(r['passed'] is True for r in runs),
                'unknown_usage': len(runs) - len(known),
                'prepared_feedback_used': sum(r.get('used_prepared_feedback') is True for r in runs),
                'median_tokens': {k: statistics.median(c[k] for c in costs) for k in costs[0]} if costs else None,
                'total_tokens': sum(c['total_tokens'] for c in costs) if len(known) == len(runs) and runs else None,
                'median_commands': statistics.median(r['usage']['command_count'] for r in runs) if runs else None}
        valid = all(g['trials'] >= 3 and g['trials'] == g['passed'] and not g['unknown_usage'] for g in groups.values())
        if any('used_prepared_feedback' in r for r in selected):
            valid = valid and all(r.get('used_prepared_feedback') is True for r in selected if r['condition'] == 'skill')
        a, b = groups['natural'], groups['skill']
        ratio = b['total_tokens'] / a['total_tokens'] if valid and a['total_tokens'] else None
        profiles[profile] = {'identity': {k: selected[0][k] for k in IDENTITY},
            'conditions': groups, 'comparison_valid': valid, 'skill_to_natural_total_token_ratio': ratio}
    return {'schema_version': 1, 'profiles': profiles,
        'limitations': ['One injected regression per repository, three repetitions per condition; not broad task coverage.',
            'Prepared skill includes command discovery and compact output. Effects are not isolated.',
            'Helper installation and dependency preparation are outside model timing; kit engineering is reported separately.',
            'Repository streams ran concurrently; order alternated within each stream. Cache effects remain possible.',
            'Total input includes cached input once; this is not a monetary-cost comparison.']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('results', nargs='+', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    records = []
    for path in args.results:
        record = json.loads(path.read_text())
        digest = hashlib.sha256()
        with path.with_name('events.jsonl').open('rb') as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                digest.update(chunk)
        record['evidence_sha256'] = digest.hexdigest()
        records.append(record)
    report = {**aggregate(records), 'records': records}
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report['profiles'], indent=2))


if __name__ == '__main__':
    main()
