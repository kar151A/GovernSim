# GovernSim illustrative internal policy v1

This authored demonstration policy is not a regulation or legal advice. It applies to the synthetic example estate and illustrates configurable internal governance gates.

## GS-POL-01 — Model documentation gate
Require a reviewed model card scoped to the deployed model, provider, prompt, data and dependency versions.

## GS-POL-02 — Tool permission review
Require a reviewed access record scoped to the agent's permissions and autonomy. Added permissions require renewed review.

## GS-POL-03 — Autonomous high-risk release
Block autonomous operation of an internally high-risk or critical asset until valid oversight evidence and a named, context-specific governance approval exist. Approval is conditional and does not repair unrelated gaps.

## GS-POL-04 — Incident remediation review
An incident or monitoring breach requires a named review. Missing incident remediation evidence remains an open gap even after escalation.

## GS-POL-05 — Sensitive data lineage
Sensitive data requires reviewed lineage scoped to the data sources, geography, sensitivity and processing context.

## Versioned evidence windows
- baseline-v1: evidence captured no more than 180 days ago and not expired.
- strict-v2: evidence captured no more than 30 days ago and not expired.

An explicit admin action is required to activate a different profile. Agents cannot edit active kernel code or policy values. These are demonstration thresholds, not thresholds prescribed by the external frameworks.
