# API reference

Governance operations require an authenticated account session issued after password and two-factor verification. Browser mutations require the matching `X-CSRF-Token` plus an allowed `Origin`. `/health` and the sign-in shell are public. Account enrollment/login routes are deliberately reachable before a full session; none issues a full session before the second factor succeeds. Roles are assigned locally, never by a browser form. OpenAPI is at `/docs`. Legacy bearer tokens are disabled unless explicitly enabled for automation; see [authentication](AUTHENTICATION.md).

| Account endpoint | Purpose |
| --- | --- |
| `POST /api/auth/email/request` | Email a short-lived code for `signup` (approved pending account) or `reset` (enabled enrolled account). Generic success response; TLS SMTP required. |
| `POST /api/auth/email/enroll` | Verify the requesting browser’s email code plus matching `password`/`password_confirm`, then prepare authenticator enrollment. |
| `POST /api/auth/password/reset` | Consume a reset email code with new matching passwords; revoke all sessions/flows; preserve MFA and require sign-in. |
| `POST /api/auth/password/change` | Require an account session, CSRF and `current_password`; set matching new passwords and revoke all sessions/flows. |
| `POST /api/auth/enroll/start` | Original offline API compatibility: consume a valid administrator invitation and prepare password + authenticator enrollment. The website uses email verification. |
| `POST /api/auth/enroll/confirm` | Verify the first authenticator code, issue a session, and return one-use recovery codes once. |
| `POST /api/auth/login` | Check email/password and create a five-minute verification flow, without workspace access. |
| `POST /api/auth/verify` | Verify authenticator or recovery code and issue the account session. |
| `POST /api/auth/logout` | Validate CSRF, revoke the server session, and clear cookies. |
| `GET /api/session` | Resolve the current server-owned identity, role and session validity. |

| Endpoint | Roles | Purpose |
| --- | --- | --- |
| `GET /health` | Public | Database connectivity and version. |
| `GET /api/session` | Any authenticated | Server-resolved name and role. |
| `GET /api/assets` | Any authenticated | Registry with current kernel projections. |
| `POST /assets` | AI_OWNER, RISK_OFFICER, ADMIN | Register a strictly validated asset. |
| `GET /assets/{asset_id}` | Any authenticated | Asset, current projection, evidence and immutable saved assessments. |
| `POST /assets/{asset_id}/evidence` | AI_OWNER, RISK_OFFICER, ADMIN | Capture raw text and scoped artifact metadata. New evidence is pending. |
| `POST /api/evidence/{evidence_id}/review` | COMPLIANCE_REVIEWER, RISK_OFFICER, ADMIN | Append VERIFY, REJECT or CONFLICT attestation; submitter cannot self-verify. |
| `POST /obligations` | ADMIN | Add a source-attributed representative requirement. |
| `POST /controls` | ADMIN | Add a control whose scope uses known asset fields. |
| `GET /api/library` | Any authenticated | Controls, requirements and mapping proposals. |
| `POST /mappings/propose` | AI_OWNER, RISK_OFFICER, ADMIN | Propose compatible mapping with rationale; does not activate it. |
| `POST /mappings/approve` | COMPLIANCE_REVIEWER, RISK_OFFICER, ADMIN | Different named principal approves/rejects mapping. |
| `POST /assess/{asset_id}` | AI_OWNER, RISK_OFFICER, ADMIN | Save assessment and decision snapshots plus hash-chain receipt. |
| `POST /simulate` | AI_OWNER, RISK_OFFICER, ADMIN | Compare baseline and proposed configuration in isolation. |
| `GET /simulations/{simulation_id}` | Any authenticated | Retrieve saved scenario and audit receipt. |
| `GET /api/simulations` | Any authenticated | Saved scenarios. |
| `POST /api/changes` | AI_OWNER, RISK_OFFICER, ADMIN | Explicitly apply a registry change and reassess transitive dependents. Policy changes require ADMIN. |
| `POST /api/policies/activate` | ADMIN | Apply one of two versioned policy profiles estate-wide. |
| `GET /api/changes` | Any authenticated | Material change events and remediation. |
| `GET /api/reviews` | Any authenticated | Current saved escalations, unverified evidence, pending mappings and review history. |
| `POST /decisions/{decision_id}/review` | COMPLIANCE_REVIEWER, RISK_OFFICER, ADMIN | APPROVE, REJECT, CHALLENGE or OVERRIDE with justification. |
| `GET /audit/{asset_id}` | Any authenticated | Asset event trail and estate chain integrity. |
| `GET /audit/verify` | Any authenticated | Verify full stored history. |
| `GET /api/audit/export` | Any authenticated | Export complete chain for independent anchoring. |
| `GET /reports/audit-package/{asset_id}?format=json` | Any authenticated | Current evidence package; also `markdown` and `pdf`. |
| `GET /governance-graph/{asset_id}` | Any authenticated | NetworkX graph serialized as nodes and edges. |
| `GET /api/retrieval/{asset_id}?query=...` | Any authenticated | Rank recorded evidence using local lexical vectors. |
| `POST /api/agents/explain/{asset_id}?query=...` | Any authenticated | Retrieved-source summary; never a compliance decision. |
| `POST /api/events` | AI_OWNER, RISK_OFFICER, ADMIN | Capture evidence from evaluations, access reviews, monitoring or handoff events. |

Root endpoints in the original brief also have `/api/*` aliases for the frontend.

## Simulation request

```json
{
  "asset_id": "AS-SUPPORT",
  "change_type": "GEOGRAPHY",
  "proposed_change": {"deployment_geographies": ["IN", "EU"]},
  "reason": "Evaluate EU expansion before release"
}
```

Change types and their allowed fields:

| Type | Fields |
| --- | --- |
| GEOGRAPHY | deployment_geographies |
| MODEL_CHANGE | version |
| DATA_CHANGE | data_sources, sensitive_data, processes_personal_data, dpia_required |
| VENDOR_CHANGE | model_provider, version |
| TOOL_PERMISSION_CHANGE | tools_and_permissions |
| AUTONOMY_CHANGE | autonomy_level |
| POLICY_CHANGE | policy_version (`baseline-v1` or `strict-v2`) |
| INCIDENT | incident_open, monitoring_config |
| PROMPT_CHANGE | prompt_version |

When recording a saved scenario with `/api/changes`, include `expected_context_hash` from its `baseline_context_hash`. Stale scenarios are rejected with 409. `risk_tier` cannot be lowered through a free-form change payload. Introducing sensitive data or an incident conservatively escalates the internal tier; this is a demo internal policy, not legal classification.

## Evidence request

```json
{
  "control_id": "C-02",
  "evidence_type": "MODEL_CARD",
  "source_system": "Model registry",
  "source_uri": "registry://model/my-agent/1.0/card",
  "valid_until": "2027-01-31T23:59:59Z",
  "raw_content": "Model documentation, evaluation limits and validation results for the deployed version.",
  "confidence": 1
}
```

Content is UTF-8 text, up to 100,000 characters. The source reference is recorded, never fetched. `expected_hash`, when supplied, is SHA-256 of the exact UTF-8 `raw_content` bytes. A mismatching hash is rejected. Duplicate content for the same type/control/asset/scope is rejected with 409. Coverage indicators only assist verification; the named reviewer remains responsible for authenticity and actual coverage.

## Named review

```json
{"action":"APPROVE","comment":"I reviewed the current oversight artifact and approve this exact configuration conditionally."}
```

Justification must contain at least twenty characters. Missing/conflicting evidence cannot be waived by APPROVE or OVERRIDE. Overrides yield conditional approval for that requirement/context, never universal compliance. Old context hashes are rejected.
