#!/usr/bin/env python3
"""Report cumulative native-workflow costs, including adoption and failed trials."""
import argparse
import hashlib
import json
from pathlib import Path
import statistics
from .report import IDENTITY
try:
    from ..usage import summarise, MAX_EVENT_BYTES, MAX_STREAM_BYTES
except ImportError:
    from usage import summarise, MAX_EVENT_BYTES, MAX_STREAM_BYTES


def aggregate(records):
    if not records or any(r.get('preflight_only') for r in records):
        raise ValueError('expected measured lifecycle trials')
    evidence = [s['evidence_sha256'] for r in records for s in r['stages'] if 'evidence_sha256' in s]
    if len(evidence) != len(set(evidence)):
        raise ValueError('duplicate stage evidence')
    profiles = {}
    for profile in sorted({r['profile'] for r in records}):
        rows = [r for r in records if r['profile'] == profile]
        for key in (*IDENTITY, 'expected_stages'):
            if len({r[key] for r in rows}) != 1:
                raise ValueError('incompatible ' + key)
        if any(r['condition'] not in ('natural', 'skill') for r in rows):
            raise ValueError('unknown condition')
        groups = {}
        for condition in ('natural', 'skill'):
            selected = [r for r in rows if r['condition'] == condition]
            cumulative = []
            for index in range(rows[0]['expected_stages']):
                costs = []
                for r in selected:
                    prefix = r['stages'][:index+1]
                    if len(prefix) != index+1 or any(not s.get('usage', {}).get('usage_complete') for s in prefix):
                        continue
                    tokens = {k: sum(s['usage']['tokens'][k] for s in prefix)
                              for k in ('input_tokens', 'cached_input_tokens', 'output_tokens')}
                    tokens['total_tokens'] = tokens['input_tokens'] + tokens['output_tokens']
                    tokens['uncached_input_tokens'] = tokens['input_tokens'] - tokens['cached_input_tokens']
                    costs.append(tokens)
                complete = bool(selected) and len(costs) == len(selected)
                cumulative.append({'through_stage': index+1, 'known_sequences': len(costs),
                    'median_tokens': {k: statistics.median(c[k] for c in costs) for k in costs[0]} if complete else None,
                    'sum_total_tokens': sum(c['total_tokens'] for c in costs) if complete else None})
            accepted = sum(r['passed'] and len(r['stages']) == r['expected_stages']
                           and all(s['passed'] and s.get('usage', {}).get('usage_complete') for s in r['stages']) for r in selected)
            groups[condition] = {'sequences': len(selected), 'accepted_sequences': accepted, 'cumulative': cumulative}
        valid = all(g['sequences'] >= 3 and g['sequences'] == g['accepted_sequences'] for g in groups.values())
        ratios = []
        if valid:
            for a, b in zip(groups['natural']['cumulative'], groups['skill']['cumulative']):
                denominator = a['median_tokens']['total_tokens']
                ratios.append(b['median_tokens']['total_tokens'] / denominator if denominator else None)
        # A one-stage crossing followed by a loss is not sustained pay-off.
        crossover = next((i+1 for i in range(len(ratios)) if all(v is not None and v < 1 for v in ratios[i:])), None)
        profiles[profile] = {'identity': {k: rows[0][k] for k in IDENTITY}, 'conditions': groups,
                             'comparison_valid': valid, 'cumulative_median_skill_to_natural_ratios': ratios,
                             'first_sustained_observed_crossover_stage': crossover}
    return {'schema_version': 1, 'profiles': profiles, 'limitations': [
        'Three defects within one component per repository; not general project maintenance.',
        'Each stage uses a fresh model session; workspace files persist in both arms.',
        'Helper command configuration is measured; dependency preparation and helper installation are excluded.',
        'No extrapolation beyond observed stages. A crossover in three repetitions is not statistical proof.',
        'Total input includes cached input once; token counts are not monetary costs.']}


def read_verified_record(path):
    """Verify local transcripts before publishing counters or failure categories."""
    record = json.loads(path.read_text())
    for stage in record['stages']:
        if 'evidence_sha256' not in stage:
            continue
        index = stage['stage']
        if type(index) is not int or not 1 <= index <= record['expected_stages']:
            raise ValueError('invalid stage index')
        events = path.parent / f'stage-{index}' / 'events.jsonl'
        digest, size = hashlib.sha256(), 0
        with events.open('rb') as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b''):
                size += len(chunk)
                if size > MAX_STREAM_BYTES:
                    raise ValueError('event stream exceeds size limit')
                digest.update(chunk)
        if digest.hexdigest() != stage['evidence_sha256']:
            raise ValueError('stage transcript changed')
        with events.open('rb') as source:
            measured = summarise(iter(lambda: source.readline(MAX_EVENT_BYTES + 1), b''))
        if measured != stage['usage']:
            raise ValueError('stage usage differs from transcript')
        with events.open('rb') as source:
            for line in iter(lambda: source.readline(MAX_EVENT_BYTES + 1), b''):
                if not line.strip():
                    continue
                event = json.loads(line)
                if event.get('type') == 'error' and event.get('message') == 'Selected model is at capacity. Please try a different model.':
                    stage['model_failure_category'] = 'model_capacity'
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('results', nargs='+', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    records = [read_verified_record(p) for p in args.results]
    report = {**aggregate(records), 'records': records}
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report['profiles'], indent=2))


if __name__ == '__main__':
    main()
