"""Frozen development tasks and independent fixture contracts for agent evals."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Input:
    name: str
    query: str
    required: bool = True


@dataclass(frozen=True)
class Case:
    name: str
    command: tuple[str, ...]
    path: str
    inputs: tuple[Input, ...]
    task: str

    @property
    def prompt(self):
        return self.task + """
Keep `status get` working. Use the shared runtime and add meaningful offline tests
for the new command, including path/query encoding, an API base path prefix,
bearer auth, invalid input and an upstream error. Cover both supplied and omitted
optional inputs when present. Run the relevant checks.
Do not change dependencies or the runtime. Do not publish, browse, access live
services or use tools outside this workspace. Stop when implementation and tests
are complete. The local SDK replacement is intentional evaluation setup.
"""


CASES = {
    'add_billing_day': Case('add_billing_day', ('billing', 'day'), '/api/billing',
        (Input('day', 'day'),),
        'Extend this project CLI with `billing day`. The admin API contract is GET\n'
        '/api/billing with required string query parameter `day`, returning a JSON object.'),
    'add_audit_events': Case('add_audit_events', ('audit', 'events'), '/api/audit/events',
        (Input('after', 'since'), Input('limit', 'page_size', False)),
        'Extend this project CLI with `audit events`. This synthetic admin API uses GET\n'
        '/api/audit/events and returns a JSON object. The CLI accepts required string\n'
        'input `after`, mapped to API query `since`, and optional string input `limit`,\n'
        'mapped to API query `page_size`. Omitting limit must omit page_size entirely;\n'
        'do not supply a default. These are strings, not numeric or date parsers.'),
}
