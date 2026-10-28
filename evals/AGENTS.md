# Evaluation tooling

Own deterministic external-project validation, opt-in agent trials and observed
usage accounting. No production Go package imports this directory. Use Python's
standard library; project consumers do not need Python.

Keep experiments isolated from live services and other working trees. Pin external
source revisions. Preserve failed trials and distinguish harness failures from
candidate failures. A missing usage event means unknown cost, never zero.
Cached input is included in total input. Do not add it twice or convert account
allowance percentages to money. Do not commit raw transcripts or private source.

Freeze prompts, grader, model and setup within a comparison. Grade observable
behaviour independently of the candidate's own claims. Test the grader with real
compiled fixtures; a mutation is only caught if the original tests passed first.
Do not teach the skill the hidden answers or tune only against one task.

Run `python3 -m unittest discover -s evals -p 'test_*.py'` for changes here.
Agent trials consume allowance and are opt-in, never automatic CI work. The Energy
integration requires an authorised local checkout; do not provision credentials.
