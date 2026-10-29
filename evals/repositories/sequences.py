"""Distinct native regressions for retained-workspace maintenance trials."""
from dataclasses import replace
from .profiles import PROFILES
from .agent import SYMPTOMS


def sequence(name):
    """Return ordered (profile, symptom) stages without changing source snapshots."""
    base = PROFILES[name]
    stages = [(base, SYMPTOMS[name])]
    additions = {
        'loop-definition': (
            ('m.SchemaVersion != 1', 'm.SchemaVersion < 1', 'accepted invalid bytes',
             'Manifest parsing accepts unsupported future schema versions. Restore the supported-version contract.'),
            ('c.HTTP.Method != "GET"', 'c.HTTP.Method == ""', 'accepted invalid bytes',
             'Manifest parsing accepts write operations despite the read-only command contract. Restore validation.')),
        'landing-counters': (
            ('this.from = this.initialized ? this.sample(now) : target;',
             'this.from = this.initialized ? this.target : target;', 'AssertionError',
             'Updating a counter during animation jumps to the previous target. Preserve continuity from its displayed value.'),
            ('this.from = this.target;\n    this.duration = 0;',
             'this.target = this.from;\n    this.duration = 0;', 'AssertionError',
             'Settling a counter displays the old value rather than the confirmed target. Restore reduced-motion settling.')),
        'porsche-timestamp': (
            ('measurement_node="MILEAGE",', 'measurement_node="RANGE",', 'test_mileage_sensor',
             'The mileage sensor reports remaining range rather than total distance travelled. Restore its data binding.'),
            ('measurement_leaf="status",', 'measurement_leaf="chargeMode",', 'test_charger_sensor',
             'The charging status sensor no longer reports the vehicle charging state. Restore its data binding.')),
    }
    for before, after, marker, symptom in additions[name]:
        stages.append((replace(base, before=before, after=after, failure_marker=marker, setup=()), symptom))
    return stages
