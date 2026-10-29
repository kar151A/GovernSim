# Reproducing the synthetic evaluation

From the project root, with backend dependencies installed, run:

```sh
python scripts/evaluate.py
python -m pytest backend/tests -q --junitxml=evaluation/test-results.xml
```

The evaluator uses a temporary SQLite database and disposes of it after completion. It rewrites `metrics.json` and `REPORT.md`; the pytest command rewrites `test-results.xml`. The demo script is different: it calls the running API and creates persistent demo records.

## Interpret the outputs

- `metrics.json` contains explicit expected/predicted artifact, mapping, simulation and escalation cases.
- `REPORT.md` summarizes those observed synthetic cases.
- `test-results.xml` records the test run that generated it, including skipped tests.
- Timestamps and one-run package-generation timings vary between runs.

Perfect scores on this small fixture set establish only those fixture outcomes. They do not measure production accuracy, legal applicability or semantic mapping correctness. A passing local SQLite suite does not establish a PostgreSQL result; inspect the corresponding CI job or run the opt-in disposable-database test. See [verification scope](../docs/VERIFICATION.md).
