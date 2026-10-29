# GovernSim evaluation report

Synthetic deterministic fixtures only; not estimates of enterprise or legal accuracy.

| Metric | Observed result |
| --- | --- |
| evidence_gap_precision | 1.0 |
| evidence_gap_recall | 1.0 |
| false_positive_rate | 0.0 |
| type_compatibility_accuracy_on_manual_golden_set | 1.0 |
| simulation_correctness | 1.0 |
| representative_obligation_coverage | 1.0 |
| provenance_completeness | 1.0 |
| human_review_escalation_accuracy | 1.0 |
| audit_package_generation_ms | 7.846 |

25 artifact cases (20 faults and 5 valid controls), 8 manually labeled type-compatibility pairs, 3 simulation cases and 3 escalation cases.

Type compatibility is a coarse guard, not semantic mapping accuracy. All changed mappings require human review. No validated LLM mapping benchmark is claimed.

Timing measures one local SQLite run and varies by machine. PostgreSQL, optional cloud LLMs and browser QA are reported separately in docs/VERIFICATION.md.

Run `python scripts/evaluate.py` to reproduce metrics; run `pytest backend/tests -q` for the regression suite.
