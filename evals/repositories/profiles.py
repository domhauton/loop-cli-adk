"""Repository-specific contracts; execution and reporting live in the harness."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Profile:
    revision: str
    language: str
    focus: tuple[str, ...]
    suite: tuple[str, ...]
    mutation_file: str
    before: str
    after: str
    failure_marker: str
    setup: tuple[tuple[str, ...], ...] = ()


PROFILES = {
    'loop-definition': Profile(
        '375fa17407392287841ed16a5c62d3ea8634a00b', 'Go',
        ('go', 'test', '-count=1', './internal/definition'),
        ('go', 'test', './...'), 'internal/definition/definition.go',
        'd.DisallowUnknownFields()', '// Regression fixture: unknown fields accepted.',
        'accepted invalid bytes'),
    'landing-counters': Profile(
        'ef410d16b48d6e758bfa83d38531cc31caed52e9', 'TypeScript / Node',
        ('node', '--test', 'tests/counters.test.mjs'), ('npm', 'test'),
        'web/counters.ts', 'Math.min(this.duration, Math.floor(now - this.started))',
        'Math.floor(now - this.started)', 'AssertionError',
        (('npm', 'ci', '--no-audit', '--no-fund'), ('npm', 'run', 'build'))),
    'porsche-timestamp': Profile(
        '45009be1cba72fe2510990b368ee14aa74149a42', 'Python / Home Assistant',
        ('{python}', '-m', 'pytest', '--no-cov', '-q', 'tests/test_sensor.py'),
        ('{python}', '-m', 'pytest', '-q'),
        'custom_components/porscheconnect/sensor.py',
        'value_fn=lambda v: v.last_global_update,', 'value_fn=lambda v: None,',
        'test_last_updated_sensor'),
}
