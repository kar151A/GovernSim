"""Pure policy kernel. Never calls an LLM, database or network."""
from datetime import datetime, timezone
import hashlib
from .audit import digest, uid, now
from .catalog import RULE_VERSION, POLICIES

SEVERITY = {'COMPLIANT': 0, 'CONDITIONAL_APPROVAL': 1, 'HUMAN_REVIEW_REQUIRED': 2, 'EVIDENCE_GAP': 3, 'BLOCKED': 4}
RISK_ORDER = ['LOW', 'LIMITED', 'HIGH', 'CRITICAL']


def applies(obligation, asset):
    condition = obligation['applicability_conditions']
    eu = 'EU' in asset['deployment_geographies']
    personal = asset['processes_personal_data']
    return {
        'ALL': True,
        'EU_INTERACTIVE': eu and asset['interacts_with_people'],
        'EU_HIGH_RISK': eu and asset['ai_act_high_risk'],
        'EU_PERSONAL': eu and personal,
        'EU_DPIA': eu and personal and (asset['dpia_required'] or asset['sensitive_data']),
        'IN_PERSONAL': 'IN' in asset['deployment_geographies'] and personal,
        'SENSITIVE': asset['sensitive_data'],
        'INCIDENT': asset['incident_open'] or bool(asset['monitoring_config'].get('threshold_breached')),
        'AUTONOMOUS': asset['autonomy_level'] == 'AUTONOMOUS' and asset['risk_tier'] in ('HIGH', 'CRITICAL'),
    }[condition]


def evidence_scope(asset, control):
    return {key: asset.get(key) for key in control['scope_fields']}


def context_hash(asset, evidence, obligations, controls):
    # Reviews/evidence acceptance and dependency changes revoke prior approval scope.
    return digest({'asset': asset, 'evidence': sorted(evidence, key=lambda x: x['evidence_id']), 'obligations': obligations, 'controls': controls, 'rule_version': RULE_VERSION})


def evidence_state(item, asset, control, required_type, at=None):
    at = at or datetime.now(timezone.utc)
    if hashlib.sha256(item['raw_content'].encode('utf-8')).hexdigest() != item['content_hash']:
        return 'HASH_MISMATCH'
    if item['evidence_type'] != required_type:
        return 'WRONG_TYPE'
    if item['control_id'] != control['control_id'] or item['asset_id'] != asset['asset_id']:
        return 'WRONG_SCOPE'
    if item.get('reviewer_status') == 'CONFLICT':
        return 'CONFLICTING'
    if item.get('reviewer_status') != 'VERIFIED':
        return 'UNVERIFIED'
    if item['confidence'] < .8:
        return 'LOW_CONFIDENCE'
    if not item.get('source_uri') or not item.get('source_system'):
        return 'MISSING_PROVENANCE'
    captured = datetime.fromisoformat(item['captured_at'])
    expires = datetime.fromisoformat(item['valid_until'])
    if captured > at:
        return 'FUTURE_DATED'
    if expires <= at:
        return 'EXPIRED'
    if (at - captured).total_seconds() > POLICIES[asset['policy_version']]['max_evidence_age_days'] * 86400:
        return 'STALE'
    expected = evidence_scope(asset, control)
    if item.get('scope') != expected or item.get('dependency_versions', {}) != asset.get('dependency_versions', {}):
        return 'VERSION_OR_SCOPE_CHANGED'
    # A keyword claim alone is not trusted: acceptance requires named human verification.
    return 'VALID'


def assess(asset, obligations, controls, evidence, reviews=None, at=None):
    reviews = reviews or []
    control_map = {c['control_id']: c for c in controls}
    context = context_hash(asset, evidence, obligations, controls)
    decisions = []
    applicable = [o for o in obligations if o.get('approved', True) and applies(o, asset)]
    for obligation in applicable:
        for control_id in obligation['control_ids']:
            control = control_map[control_id]
            candidates = [e for e in evidence if e['asset_id'] == asset['asset_id'] and e['control_id'] == control_id]
            states = {e['evidence_id']: evidence_state(e, asset, control, e['evidence_type'], at) for e in candidates}
            valid = []
            missing_types = []
            for required in obligation['evidence_required']:
                matches = [e for e in candidates if e['evidence_type'] == required and states[e['evidence_id']] == 'VALID']
                if matches:
                    valid.extend(matches)
                else:
                    missing_types.append(required)
            status = 'EVIDENCE_GAP' if missing_types else 'COMPLIANT'
            rules = ['EVIDENCE_VALIDITY_V1', 'APPLICABILITY_V1']
            reason = f'Missing valid reviewed evidence: {", ".join(missing_types)}.' if missing_types else 'Required scoped, reviewed evidence is current under the selected controls.'
            # A conflicting claim is not silently hidden by another valid artifact.
            conflicting = any(s in ('HASH_MISMATCH', 'CONFLICTING') for s in states.values())
            if conflicting:
                status = 'HUMAN_REVIEW_REQUIRED'
                reason = 'Conflicting evidence or a hash mismatch requires investigation.'
                rules.append('EVIDENCE_CONFLICT_V1')
            high_autonomy = asset['risk_tier'] in ('HIGH', 'CRITICAL') and asset['autonomy_level'] == 'AUTONOMOUS' and control_id == 'C-06'
            incident = (asset['incident_open'] or asset['monitoring_config'].get('threshold_breached')) and control_id == 'C-07'
            if high_autonomy:
                status = 'BLOCKED'
                reason = 'Autonomous high-risk operation requires scoped, named human approval and valid oversight evidence.'
                rules.append('HIGH_AUTONOMY_GATE_V1')
            elif asset['risk_tier'] in ('HIGH', 'CRITICAL') and control_id == 'C-06':
                status = 'HUMAN_REVIEW_REQUIRED'
                reason = 'High-risk deployment requires a named human governance decision.'
                rules.append('HIGH_RISK_REVIEW_V1')
            elif incident:
                status = 'HUMAN_REVIEW_REQUIRED'
                reason = 'An incident or monitoring breach requires human review; missing evidence remains an open gap.'
                rules.append('INCIDENT_ESCALATION_V1')
            matching = [r for r in reviews if r.get('context_hash') == context and r.get('obligation_id') == obligation['obligation_id'] and r.get('control_id') == control_id]
            review = matching[-1] if matching else None
            if review:
                if review['action'] == 'REJECT':
                    status, reason = 'BLOCKED', 'Named reviewer rejected this scoped decision.'
                elif review['action'] == 'CHALLENGE':
                    status, reason = 'HUMAN_REVIEW_REQUIRED', 'Reviewer challenged the decision; investigation is open.'
                elif review['action'] in ('APPROVE', 'OVERRIDE') and not missing_types and not conflicting:
                    status, reason = 'CONDITIONAL_APPROVAL', 'Named, justified approval applies only to this exact evidence and asset context.'
            confidence = min([e['confidence'] for e in valid], default=0)
            decision_id = uid('DEC')
            timestamp = now()
            provenance = {
                'source_obligation': obligation['obligation_id'], 'source_document': obligation['source_document'],
                'source_clause': obligation['source_clause'], 'source_url': obligation['source_url'],
                'coverage_note': obligation['coverage_note'], 'control_id': control_id,
                'evidence_artifacts': [{'evidence_id': e['evidence_id'], 'source_uri': e['source_uri'], 'content_hash': e['content_hash'], 'status': states[e['evidence_id']], 'captured_at': e['captured_at'], 'reviewer': e.get('reviewer')} for e in candidates],
                'evidence_status': 'VALID' if not missing_types and not conflicting else 'GAP_OR_REVIEW', 'missing_types': missing_types,
                'timestamp': timestamp, 'model_version': asset['version'], 'model_provider': asset['model_provider'],
                'rule_version': RULE_VERSION, 'policy_version': asset['policy_version'], 'confidence': confidence,
                'reviewer_action': review['action'] if review else 'PENDING' if status in ('BLOCKED', 'HUMAN_REVIEW_REQUIRED') else 'NONE',
                'reviewer': review['reviewer'] if review else None, 'context_hash': context,
            }
            decisions.append(dict(decision_id=decision_id, asset_id=asset['asset_id'], obligation_id=obligation['obligation_id'], title=obligation['title'], framework=obligation['framework'], control_id=control_id, control_name=control['name'], evidence_ids=list(dict.fromkeys(e['evidence_id'] for e in valid)), rule_ids=rules, rule_version=RULE_VERSION, llm_reasoning_summary=None, deterministic_status=status, reason=reason, confidence=confidence, human_review_required=status in ('BLOCKED', 'HUMAN_REVIEW_REQUIRED'), reviewer=review['reviewer'] if review else None, reviewer_action=provenance['reviewer_action'], created_at=timestamp, missing_types=missing_types, evidence_states=states, provenance_links=provenance, context_hash=context))
    status = max((d['deterministic_status'] for d in decisions), key=lambda s: SEVERITY[s], default='EVIDENCE_GAP')
    gaps = sum(bool(d['missing_types']) for d in decisions)
    return dict(asset_id=asset['asset_id'], assessed_at=now(), status=status, rule_version=RULE_VERSION, policy_version=asset['policy_version'], context_hash=context, decisions=decisions, applicable_obligations=len(applicable), evidence_gaps=gaps, human_reviews=sum(d['human_review_required'] for d in decisions), disclaimer='Decision support for representative controls; not legal advice or a certification of compliance.')
