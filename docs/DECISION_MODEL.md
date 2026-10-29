# Decision model and provenance

## Separation of roles

The kernel is a pure Python function. It receives only structured asset, obligation, control, evidence and review values. It does not call an LLM, retrieve web content or allow generated text to update active rules.

Modular agent functions perform ingestion, lexical retrieval, proposal generation, evidence auditing, change impact, counterfactual assessment and report composition. LLM summaries are optional, grounded in recorded excerpts, recorded with model/provider/usage metadata and excluded from status decisions. No cost estimate is fabricated when pricing is unknown.

## Applicability

- NIST and ISO-aligned outcomes are representative organizational controls, not statutory legal duties.
- GDPR examples are activated for EU personal-data processing. DPIA examples additionally require the explicit DPIA flag or sensitive-data flag. This is a deliberately simplified screening model.
- EU interaction disclosure is separate from high-risk obligations. High-risk examples require the explicit `ai_act_high_risk` classification flag.
- DPDP examples are **readiness controls**; phased commencement and actual territorial/material scope require qualified review.
- Internal risk tiers are separate from legal AI Act classification.

## Evidence validity

Each artifact is immutable. Its raw content, SHA-256, source reference, source system, capture/expiry dates, artifact type, control, asset and configuration scope are retained. New evidence is pending. Attestations are separate append-only records; a different named principal verifies the source and coverage.

A finding requires the right artifact type for **each** required type. Evidence must be verified, above the confidence threshold, unexpired, sufficiently recent and scoped to the current configuration and dependency versions. Confidence is artifact metadata, not a probability that legal compliance is established. A hash mismatch or conflicting attestation requires review; a different valid artifact does not hide the conflict.

Scope fields vary by control. Model version changes invalidate model validation; changed geography invalidates relevant privacy/vendor/lineage scopes; new permissions invalidate access/oversight scopes. Transitive dependency digests currently invalidate all dependent artifacts conservatively. This can create more work than a finer dependency model; it is intentional and documented.

External source authenticity is not cryptographically verified by this MVP. Source references and hashes support traceability, while authenticity/coverage remain explicit human checks. Lexical coverage indicators can reject clearly unrelated artifacts but cannot prove semantic sufficiency.

## Decision states

| State | Meaning within this MVP |
| --- | --- |
| COMPLIANT | The selected representative controls have current valid evidence and no active blocking/review rule. This is not legal certification. |
| EVIDENCE_GAP | One or more required evidence types lack valid, reviewed, scoped coverage. |
| HUMAN_REVIEW_REQUIRED | High-risk operation, an incident, conflicting evidence or a reviewer challenge needs human action. Missing types remain visible separately. |
| CONDITIONAL_APPROVAL | A named justified approval/override is valid for this exact requirement, control and context. It cannot repair missing/conflicting evidence. |
| BLOCKED | A high-risk autonomous gate lacks scoped human approval, or a reviewer rejected the finding. |

Asset status is the most restrictive result using the ordering `BLOCKED > EVIDENCE_GAP > HUMAN_REVIEW_REQUIRED > CONDITIONAL_APPROVAL > COMPLIANT`. The response also carries evidence-gap and review counts; an aggregate status does not erase the other findings.

## Reviews and staleness

Every decision contains a context digest over asset metadata, transitive dependency versions, evidence/attestations, approved library definitions and kernel version. Reviews bind to that digest, obligation and control. Any of those inputs changing makes the prior review inapplicable. Time-based expiry is rechecked by the kernel even if the stored digest has not changed.

Saved assessment snapshots and decisions do not change after creation. Current screens recompute a live projection. The review queue uses stable saved decision IDs that match the live context. Registering/changing inputs should be followed by an assessment; registry changes and evidence verification do this automatically.

## Simulations and recorded changes

A simulation deep-copies asset inputs, validates a type-specific patch and runs the same kernel against both configurations. It saves only a scenario and audit event, preserving registered assets, evidence and saved production assessments/decisions. It reports new/retired requirements, changed findings, gaps, internal risk delta and remediation.

Recording a change is a separate explicit action. UI-submitted saved scenarios carry the baseline context hash; stale baselines are rejected. Changes are atomic with the reassessments, dependency impact records and audit events.

## Append-only audit

An event hash covers canonical JSON of its global sequence, event ID, asset ID, timestamp, actor, action, payload and previous hash. Appends are serialized. SQLite is supported with one server worker and a process transaction lock. PostgreSQL also obtains a transaction-scoped advisory lock for the chain.

Database triggers reject UPDATE and DELETE on audit events, evidence, attestations, assessments, decisions and reviews. These triggers are not protection from a database superuser. A privileged administrator can replace or truncate history, so retain externally signed head anchors independently.

Full verification checks global sequence continuity, previous hashes, canonical hashes and row/payload identity. Asset-filtered trails can have sequence gaps; use the estate-wide export for full verification. Nothing here claims WORM storage, external signing or immunity to privileged database administration.
