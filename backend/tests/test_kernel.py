from copy import deepcopy
from datetime import datetime, timezone, timedelta
import hashlib
from app.kernel import assess, applies, evidence_state
from app.catalog import OBLIGATIONS


def target(result, framework, index):
    return next(d for d in result['decisions'] if d['obligation_id']==f'O-{framework}-{index:02}')


def test_seed_baseline_is_scoped_compliant(twin):
    result=assess(*twin)
    assert result['status']=='COMPLIANT'
    assert result['evidence_gaps']==0


def test_missing_model_card(twin):
    a,o,c,e,r=twin
    e=[item for item in e if item['evidence_type']!='MODEL_CARD']
    assert target(assess(a,o,c,e,r),'INTERNAL_POLICY',1)['deterministic_status']=='EVIDENCE_GAP'


def test_expired_dpia(twin):
    a,o,c,e,r=deepcopy(twin)
    a['deployment_geographies']=['EU']
    a['dpia_required']=True
    privacy=next(control for control in c if control['control_id']=='C-03')
    from app.kernel import evidence_scope
    item=deepcopy(next(item for item in e if item['evidence_type']=='RISK_ASSESSMENT'))
    item.update(control_id='C-03',scope=evidence_scope(a,privacy),valid_until=(datetime.now(timezone.utc)-timedelta(days=1)).isoformat())
    e.append(item)
    d=target(assess(a,o,c,e,r),'GDPR',4)
    assert 'RISK_ASSESSMENT' in d['missing_types']
    assert 'EXPIRED' in d['evidence_states'].values()


def test_model_version_change_requires_revalidation(twin):
    a,o,c,e,r=deepcopy(twin)
    a['version']='new-model'
    d=target(assess(a,o,c,e,r),'NIST_AI_RMF',4)
    assert d['deterministic_status']=='EVIDENCE_GAP'
    assert 'VERSION_OR_SCOPE_CHANGED' in d['evidence_states'].values()


def test_autonomous_high_risk_requires_approval(twin):
    a,o,c,e,r=deepcopy(twin)
    a.update(autonomy_level='AUTONOMOUS',risk_tier='HIGH')
    assert target(assess(a,o,c,e,r),'INTERNAL_POLICY',3)['deterministic_status']=='BLOCKED'


def test_new_eu_deployment_does_not_assume_high_risk(twin):
    a,o,c,e,r=deepcopy(twin)
    a['deployment_geographies'].append('EU')
    result=assess(a,o,c,e,r)
    assert any(d['framework']=='GDPR' for d in result['decisions'])
    assert any(d['obligation_id']=='O-EU_AI_ACT-01' for d in result['decisions'])
    assert not any(d['obligation_id']=='O-EU_AI_ACT-02' for d in result['decisions'])


def test_new_sensitive_data_requires_lineage(twin):
    a,o,c,e,r=deepcopy(twin)
    a['sensitive_data']=True
    a['data_sources'].append('Customer transactions')
    assert target(assess(a,o,c,e,r),'INTERNAL_POLICY',5)['deterministic_status']=='EVIDENCE_GAP'


def test_vendor_replacement_invalidates_attestation(twin):
    a,o,c,e,r=deepcopy(twin)
    a['model_provider']='Different provider'
    assert target(assess(a,o,c,e,r),'ISO_42001',4)['deterministic_status']=='EVIDENCE_GAP'


def test_monitoring_alert_escalates(twin):
    a,o,c,e,r=deepcopy(twin)
    a['monitoring_config']['threshold_breached']=True
    result=assess(a,o,c,e,r)
    assert target(result,'NIST_AI_RMF',5)['human_review_required']
    assert target(result,'INTERNAL_POLICY',4)['human_review_required']


def test_missing_human_oversight(twin):
    a,o,c,e,r=twin
    e=[x for x in e if x['evidence_type']!='HUMAN_OVERSIGHT_RECORD']
    assert target(assess(a,o,c,e,r),'NIST_AI_RMF',2)['deterministic_status']=='EVIDENCE_GAP'


def test_conflicting_evidence_never_silently_passes(twin):
    a,o,c,e,r=deepcopy(twin)
    next(x for x in e if x['control_id']=='C-02')['reviewer_status']='CONFLICT'
    assert target(assess(a,o,c,e,r),'NIST_AI_RMF',4)['deterministic_status']=='HUMAN_REVIEW_REQUIRED'


def test_low_confidence_extraction_does_not_pass(twin):
    a,o,c,e,r=deepcopy(twin)
    next(x for x in e if x['evidence_type']=='MODEL_CARD')['confidence']=.4
    assert target(assess(a,o,c,e,r),'INTERNAL_POLICY',1)['deterministic_status']=='EVIDENCE_GAP'


def test_prompt_change_invalidates_model_card(twin):
    a,o,c,e,r=deepcopy(twin)
    a['prompt_version']='2.0'
    assert target(assess(a,o,c,e,r),'INTERNAL_POLICY',1)['deterministic_status']=='EVIDENCE_GAP'


def test_access_review_overdue(twin):
    a,o,c,e,r=deepcopy(twin)
    item=next(x for x in e if x['evidence_type']=='ACCESS_REVIEW')
    item['captured_at']=(datetime.now(timezone.utc)-timedelta(days=181)).isoformat()
    assert target(assess(a,o,c,e,r),'INTERNAL_POLICY',2)['deterministic_status']=='EVIDENCE_GAP'


def test_incident_without_remediation_retains_gap(twin):
    a,o,c,e,r=deepcopy(twin)
    a['incident_open']=True
    d=target(assess(a,o,c,e,r),'INTERNAL_POLICY',4)
    assert d['human_review_required']
    assert d['missing_types']==['INCIDENT_LOG']


def test_wrong_evidence_type_does_not_satisfy_control(twin):
    a,o,c,e,r=deepcopy(twin)
    next(x for x in e if x['evidence_type']=='MODEL_CARD')['evidence_type']='INCIDENT_LOG'
    assert target(assess(a,o,c,e,r),'INTERNAL_POLICY',1)['deterministic_status']=='EVIDENCE_GAP'


def test_unverified_unrelated_content_cannot_pass(twin):
    a,o,c,e,r=deepcopy(twin)
    item=next(x for x in e if x['evidence_type']=='MODEL_CARD')
    item.update(raw_content='A lunch menu with no control claims.',reviewer_status='PENDING')
    item['content_hash']=hashlib.sha256(item['raw_content'].encode()).hexdigest()
    assert target(assess(a,o,c,e,r),'INTERNAL_POLICY',1)['deterministic_status']=='EVIDENCE_GAP'


def test_evidence_hash_mismatch_escalates(twin):
    a,o,c,e,r=deepcopy(twin)
    next(x for x in e if x['evidence_type']=='MODEL_CARD')['raw_content']='tampered'
    d=target(assess(a,o,c,e,r),'INTERNAL_POLICY',1)
    assert d['deterministic_status']=='HUMAN_REVIEW_REQUIRED'
    assert 'HASH_MISMATCH' in d['evidence_states'].values()


def test_permission_expansion_invalidates_access_review(twin):
    a,o,c,e,r=deepcopy(twin)
    a['tools_and_permissions'].append('tickets:delete')
    assert target(assess(a,o,c,e,r),'INTERNAL_POLICY',2)['deterministic_status']=='EVIDENCE_GAP'


def test_every_conclusion_has_complete_provenance(twin):
    required={'source_obligation','source_document','source_clause','source_url','control_id','evidence_artifacts','evidence_status','timestamp','model_version','rule_version','confidence','reviewer_action','context_hash'}
    for decision in assess(*twin)['decisions']:
        assert required.issubset(decision['provenance_links'])


def test_privacy_dpia_is_conditional_not_universal(twin):
    a=deepcopy(twin[0]);a['deployment_geographies']=['EU'];a['dpia_required']=False
    o=next(o for o in OBLIGATIONS if o['obligation_id']=='O-GDPR-04')
    assert not applies(o,a)
    a['dpia_required']=True
    assert applies(o,a)


def test_dependency_version_change_invalidates_evidence(twin):
    a,o,c,e,r=deepcopy(twin)
    a['dependency_versions']['AS-MODEL']='changed'
    assert assess(a,o,c,e,r)['evidence_gaps']>0
