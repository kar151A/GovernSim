"""Transactional workflow orchestration and counterfactual isolation."""
from copy import deepcopy
from sqlalchemy import select
from fastapi import HTTPException
from .audit import append_event, digest, now, uid
from .db import Asset, Obligation, Control, Evidence, Review, Assessment, Decision, Scenario, ChangeEvent
from .agents import load_evidence
from .kernel import assess, RISK_ORDER
from .schemas import AssetInput


def get_or_404(session, model, key):
    row = session.get(model, key)
    if not row:
        raise HTTPException(404, f'{model.__name__} not found')
    return row


def resolve_asset(session, asset_id):
    asset = deepcopy(get_or_404(session, Asset, asset_id).data)
    versions = {}
    # Traverse dependencies: a transitive vendor/model change invalidates evidence too.
    visited = {asset_id}
    def visit(key):
        if key in visited:
            return
        visited.add(key)
        row = get_or_404(session, Asset, key)
        versions[key] = digest(row.data)
        for child in row.data['dependencies']:
            visit(child)
    for key in asset['dependencies']:
        visit(key)
    asset['dependency_versions'] = versions
    return asset


def resources(session, asset_id):
    return ([o.data for o in session.scalars(select(Obligation).order_by(Obligation.id))], [c.data for c in session.scalars(select(Control).order_by(Control.id))], load_evidence(session, asset_id), sorted([r.data for r in session.scalars(select(Review).join(Decision).where(Decision.asset_id == asset_id))], key=lambda r: (r['created_at'], r['review_id'])))


def current_assessment(session, asset_id):
    return assess(resolve_asset(session, asset_id), *resources(session, asset_id))


def persist_assessment(session, asset_id, actor):
    result = current_assessment(session, asset_id)
    result['assessment_id'] = uid('ASM')
    for decision in result['decisions']:
        decision['assessment_id'] = result['assessment_id']
    session.add(Assessment(id=result['assessment_id'], asset_id=asset_id, data=result))
    session.flush()
    for decision in result['decisions']:
        session.add(Decision(id=decision['decision_id'], asset_id=asset_id, assessment_id=result['assessment_id'], data=decision))
    receipt = append_event(session, 'ASSESSMENT_COMPLETED', actor, {'assessment_id': result['assessment_id'], 'status': result['status'], 'context_hash': result['context_hash'], 'decision_hash': digest(result)}, asset_id)
    # Receipt is separately immutable in the audit chain, not added after decision hashing.
    return {**result, 'audit_receipt': receipt}


def transform(asset, change):
    proposed = deepcopy(asset)
    metadata = {key: proposed.pop(key) for key in list(proposed) if key not in AssetInput.model_fields}
    proposed.update(change.proposed_change)
    proposed = AssetInput.model_validate(proposed).model_dump(mode='json')
    if change.change_type == 'DATA_CHANGE' and proposed['sensitive_data']:
        proposed['risk_tier'] = RISK_ORDER[max(2, RISK_ORDER.index(proposed['risk_tier']))]
    if change.change_type == 'INCIDENT' and (proposed['incident_open'] or proposed['monitoring_config'].get('threshold_breached')):
        proposed['risk_tier'] = 'HIGH' if proposed['risk_tier'] != 'CRITICAL' else 'CRITICAL'
    proposed.update(metadata)
    return proposed


def simulate(session, change, actor):
    asset = resolve_asset(session, change.asset_id)
    obligations, controls, evidence, reviews = resources(session, change.asset_id)
    before = assess(asset, obligations, controls, evidence, reviews)
    proposed = transform(asset, change)
    after = assess(proposed, obligations, controls, evidence, reviews)
    baseline = {d['obligation_id']: d for d in before['decisions']}
    predicted = {d['obligation_id']: d for d in after['decisions']}
    newly_applicable = sorted(set(predicted) - set(baseline))
    changed = [{'obligation_id': d['obligation_id'], 'title': d['title'], 'control_id': d['control_id'], 'before': baseline.get(d['obligation_id'], {}).get('deterministic_status', 'NOT_APPLICABLE'), 'after': d['deterministic_status'], 'reason': d['reason']} for d in after['decisions'] if d['obligation_id'] not in baseline or d['deterministic_status'] != baseline[d['obligation_id']]['deterministic_status'] or d['evidence_ids'] != baseline[d['obligation_id']]['evidence_ids']]
    gaps = [d for d in after['decisions'] if d['missing_types']]
    actions = list(dict.fromkeys(f'{d["control_name"]}: provide reviewed {", ".join(d["missing_types"])} scoped to the proposed configuration.' for d in gaps))
    if after['human_reviews']:
        actions.append('Obtain named compliance review for escalations in the proposed configuration.')
    record = dict(scenario_id=uid('SIM'), **change.model_dump(mode='json'), created_at=now(), actor=actor, baseline_context_hash=before['context_hash'], before=before, after=after, proposed_asset=proposed, newly_applicable_obligations=newly_applicable, retired_obligations=sorted(set(baseline) - set(predicted)), governance_diff=changed, predicted_control_gaps=sorted(set(d['control_id'] for d in gaps)), predicted_evidence_gaps=[{'obligation_id': d['obligation_id'], 'control_id': d['control_id'], 'missing_types': d['missing_types']} for d in gaps], predicted_risk_delta={'before': asset['risk_tier'], 'after': proposed['risk_tier'], 'delta': RISK_ORDER.index(proposed['risk_tier']) - RISK_ORDER.index(asset['risk_tier'])}, recommended_actions=actions, isolation='Production assets, evidence, assessments and decisions are unchanged. Scenario and audit event are persisted.')
    receipt = append_event(session, 'SIMULATION_COMPLETED', actor, {'scenario_id': record['scenario_id'], 'baseline_context_hash': before['context_hash'], 'proposed_context_hash': after['context_hash'], 'scenario_hash': digest(record)}, change.asset_id)
    record['audit_receipt'] = receipt
    session.add(Scenario(id=record['scenario_id'], asset_id=change.asset_id, data=record))
    return record


def apply_change(session, change, actor):
    old = resolve_asset(session, change.asset_id)
    transformed = transform(old, change)
    before = current_assessment(session, change.asset_id)
    if change.expected_context_hash and before['context_hash'] != change.expected_context_hash:
        raise HTTPException(409, 'Scenario baseline is stale; rerun the simulation before recording this change')
    row = get_or_404(session, Asset, change.asset_id)
    transformed.pop('dependency_versions', None)
    event_id = uid('CHG')
    transformed['change_history'] = [*row.data.get('change_history', []), event_id]
    row.data = transformed
    session.flush()
    after = persist_assessment(session, change.asset_id, actor)
    # Reassess every transitive dependent and retain an explicit impact list.
    impacted = []
    for candidate in session.scalars(select(Asset)):
        if candidate.id != change.asset_id and change.asset_id in resolve_asset(session, candidate.id).get('dependency_versions', {}):
            result = persist_assessment(session, candidate.id, actor)
            impacted.append({'asset_id': candidate.id, 'name': candidate.data['name'], 'status': result['status'], 'assessment_id': result['assessment_id']})
    record = dict(event_id=event_id, **change.model_dump(mode='json'), actor=actor, created_at=now(), before_status=before['status'], after_status=after['status'], impacted_assets=impacted, assessment_id=after['assessment_id'], evidence_gaps=after['evidence_gaps'], affected_controls=sorted(set(d['control_id'] for d in after['decisions'] if d['missing_types'])), remediation=list(dict.fromkeys(f'{d["control_name"]}: {", ".join(d["missing_types"])}' for d in after['decisions'] if d['missing_types'])))
    record['audit_receipt'] = append_event(session, 'CHANGE_APPLIED', actor, record, change.asset_id)
    session.add(ChangeEvent(id=event_id, asset_id=change.asset_id, data=record))
    return record
