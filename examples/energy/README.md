# Energy inspection CLI

This manifest maps Energy's JSON status and dashboard routes. It intentionally
contains no charging controls. `/healthz` is plain text and is not compatible with
the current JSON response contract.

Run the pinned, offline integration from the repository root:

```sh
python3 evals/energy/run.py --automations /path/to/automations
```

The test builds a native executable and checks real Energy handlers against
synthetic state. No production connection is needed. See `evals/README.md` for
what this proves and what it does not.

A production deployment must supply its authorised admin URL and bearer token via
`ENERGY_API_URL` and `ENERGY_API_TOKEN`; the manifest stores names only. The fixture's
bearer wrapper is not a substitute for the project's real ingress authentication.
