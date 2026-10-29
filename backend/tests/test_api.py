from datetime import datetime, timezone, timedelta
import json
import pytest
from sqlalchemy import select, text
from app import db
from app.audit import digest, verify
from conftest import headers


def body(**overrides):
    return {'asset_id':'AS-SUPPORT','change_type':'GEOGRAPHY','proposed_change':{'deployment_geographies':['IN','EU']},'reason':'Evaluate new deployment region.',**overrides}


def artifact(**overrides):
    return {'control_id':'C-02','evidence_type':'MODEL_CARD','source_system':'CI pipeline','source_uri':'pipeline://eval/2026-123','valid_until':(datetime.now(timezone.utc)+timedelta(days=30)).isoformat(),'raw_content':'Reviewed model documentation and validation for the deployed version. Distinct test artifact.',**overrides}


def test_authentication_and_role_spoofing(client):
    assert client.get('/api/assets').status_code==401
    assert client.get('/api/assets',headers={'X-Role':'ADMIN'}).status_code==401
    assert client.post('/api/simulate',json=body(),headers=headers('AUDITOR')).status_code==403
    assert client.post('/api/assess/AS-SUPPORT',json={},headers=headers('COMPLIANCE_REVIEWER')).status_code==403


def test_seed_counts(client):
    assert len(client.get('/api/assets',headers=headers()).json())==5
    library=client.get('/api/library',headers=headers()).json()
    assert len(library['controls'])==10 and len(library['obligations'])==30
    with client.factory() as session:
        assert len(session.scalars(select(db.Evidence)).all())==25


def test_simulation_is_isolated_and_persisted(client):
    with client.factory() as session:
        before={table.__name__:len(session.scalars(select(table)).all()) for table in (db.Asset,db.Decision,db.Assessment,db.Evidence)}
    original=client.get('/api/assets/AS-SUPPORT',headers=headers()).json()['asset']
    response=client.post('/api/simulate',json=body(),headers=headers())
    assert response.status_code==200,response.text
    result=response.json()
    assert 'O-GDPR-01' in result['newly_applicable_obligations']
    assert result['after']['evidence_gaps']>result['before']['evidence_gaps']
    assert client.get('/api/assets/AS-SUPPORT',headers=headers()).json()['asset']==original
    assert client.get(f'/api/simulations/{result["scenario_id"]}',headers=headers()).status_code==200
    with client.factory() as session:
        assert before=={table.__name__:len(session.scalars(select(table)).all()) for table in (db.Asset,db.Decision,db.Assessment,db.Evidence)}
        assert verify(session)['valid']


def test_duplicate_evidence_rejected(client):
    first=client.post('/api/assets/AS-SUPPORT/evidence',json=artifact(),headers=headers('AI_OWNER'))
    assert first.status_code==201,first.text
    assert client.post('/api/assets/AS-SUPPORT/evidence',json=artifact(),headers=headers('AI_OWNER')).status_code==409


def test_hash_mismatch_rejected(client):
    assert client.post('/api/assets/AS-SUPPORT/evidence',json=artifact(expected_hash='0'*64),headers=headers()).status_code==422


def test_evidence_verification_requires_independent_principal(client):
    result=client.post('/api/assets/AS-SUPPORT/evidence',json=artifact(),headers=headers()).json()
    same=client.post(f'/api/evidence/{result["evidence_id"]}/review',json={'action':'VERIFY','comment':'I verified the source authenticity and model coverage.'},headers=headers())
    assert same.status_code==403
    other=client.post(f'/api/evidence/{result["evidence_id"]}/review',json={'action':'VERIFY','comment':'I verified the source authenticity and model coverage.'},headers=headers('COMPLIANCE_REVIEWER'))
    assert other.status_code==200,other.text


def test_unrelated_artifact_cannot_be_verified(client):
    record=client.post('/api/assets/AS-SUPPORT/evidence',json=artifact(raw_content='Lunch menu: sandwich, soup, coffee and cake.'),headers=headers('AI_OWNER')).json()
    result=client.post(f'/api/evidence/{record["evidence_id"]}/review',json={'action':'VERIFY','comment':'Attempt to verify an unrelated artifact.'},headers=headers('COMPLIANCE_REVIEWER'))
    assert result.status_code==422


def test_obligation_mapped_to_wrong_control_rejected(client):
    result=client.post('/api/mappings/propose',json={'obligation_id':'O-GDPR-03','control_id':'C-05','rationale':'This is intentionally an incompatible control mapping.'},headers=headers())
    assert result.status_code==422


def test_mapping_requires_second_named_reviewer(client):
    result=client.post('/api/mappings/propose',json={'obligation_id':'O-GDPR-03','control_id':'C-04','rationale':'Processor contract DPA records are maintained in vendor due diligence.'},headers=headers()).json()
    payload={'mapping_id':result['mapping_id'],'approve':True,'comment':'Mapping and source reviewed for the required processor DPA.'}
    assert client.post('/api/mappings/approve',json=payload,headers=headers()).status_code==403
    assert client.post('/api/mappings/approve',json=payload,headers=headers('COMPLIANCE_REVIEWER')).status_code==200


def test_policy_update_affects_multiple_assets(client):
    result=client.post('/api/policies/activate',json=body(change_type='POLICY_CHANGE',proposed_change={'policy_version':'strict-v2'}),headers=headers())
    assert result.status_code==200,result.text
    assert result.json()['affected_assets']==5
    assert all(a['policy_version']=='strict-v2' for a in client.get('/api/assets',headers=headers()).json())


def test_only_admin_can_activate_policy(client):
    result=client.post('/api/changes',json=body(change_type='POLICY_CHANGE',proposed_change={'policy_version':'strict-v2'}),headers=headers('AI_OWNER'))
    assert result.status_code==403


def test_change_propagates_to_dependents(client):
    result=client.post('/api/changes',json=body(asset_id='AS-VENDOR',change_type='MODEL_CHANGE',proposed_change={'version':'99.0'}),headers=headers())
    assert result.status_code==200,result.text
    affected={a['asset_id'] for a in result.json()['impacted_assets']}
    assert {'AS-MODEL','AS-SUPPORT','AS-HIRING'}.issubset(affected)
    support=client.get('/api/assets/AS-SUPPORT',headers=headers()).json()
    assert support['assessment']['evidence_gaps']>0


def test_review_override_with_justification_is_conditional(client):
    profile=client.get('/api/assets/AS-HIRING',headers=headers()).json()
    decision=next(d for d in profile['assessments'][0]['decisions'] if d['control_id']=='C-06')
    response=client.post(f'/api/decisions/{decision["decision_id"]}/review',json={'action':'OVERRIDE','comment':'Named human confirms oversight for this exact validated context.'},headers=headers('COMPLIANCE_REVIEWER'))
    assert response.status_code==200,response.text
    matching=next(d for d in response.json()['assessment']['decisions'] if d['obligation_id']==decision['obligation_id'])
    assert matching['deterministic_status']=='CONDITIONAL_APPROVAL'
    assert response.json()['review']['reviewer']=='compliance_reviewer'


def test_approval_cannot_bypass_missing_evidence(client):
    result=client.post('/api/changes',json=body(change_type='AUTONOMY_CHANGE',proposed_change={'autonomy_level':'AUTONOMOUS'}),headers=headers())
    assert result.status_code==200,result.text
    profile=client.get('/api/assets/AS-SUPPORT',headers=headers()).json()
    last=sorted(profile['assessments'],key=lambda a:a['assessed_at'])[-1]
    d=next(d for d in last['decisions'] if d['control_id']=='C-06')
    result=client.post(f'/api/decisions/{d["decision_id"]}/review',json={'action':'APPROVE','comment':'This approval should not bypass missing or wrongly scoped evidence.'},headers=headers('COMPLIANCE_REVIEWER'))
    assert result.status_code==422


def test_stale_decision_review_is_rejected(client):
    profile=client.get('/api/assets/AS-HIRING',headers=headers()).json()
    decision=profile['assessments'][0]['decisions'][0]
    client.post('/api/changes',json=body(asset_id='AS-HIRING',change_type='MODEL_CHANGE',proposed_change={'version':'2.0'}),headers=headers())
    response=client.post(f'/api/decisions/{decision["decision_id"]}/review',json={'action':'CHALLENGE','comment':'Old assessment must not accept new review after configuration changes.'},headers=headers('COMPLIANCE_REVIEWER'))
    assert response.status_code==409


def test_audit_append_only_and_hash_verification(client):
    assert client.get('/api/audit/verify',headers=headers()).json()['valid']
    with client.factory() as session:
        with pytest.raises(Exception):
            session.execute(text("UPDATE audit_events SET content_hash='tampered' WHERE sequence=1"))
        session.rollback()
        with pytest.raises(Exception):
            session.execute(text('DELETE FROM audit_events WHERE sequence=1'))
        session.rollback()
        session.execute(text('DROP TRIGGER audit_events_no_update'))
        session.execute(text("UPDATE audit_events SET content_hash='tampered' WHERE sequence=1"))
        session.commit()
    assert not client.get('/api/audit/verify',headers=headers()).json()['valid']


def test_report_formats_and_provenance(client):
    for format,content_type in [('json','application/json'),('markdown','text/markdown'),('pdf','application/pdf')]:
        response=client.get(f'/api/reports/audit-package/AS-SUPPORT?format={format}',headers=headers('AUDITOR'))
        assert response.status_code==200,response.text
        assert content_type in response.headers['content-type']
        if format=='pdf':
            assert response.content.startswith(b'%PDF')
        if format=='json':
            assert all(d['provenance_links']['source_url'] for d in response.json()['obligation_mapping'])


def test_change_schema_blocks_cross_type_fields(client):
    assert client.post('/api/simulate',json=body(proposed_change={'risk_tier':'LOW'}),headers=headers()).status_code==422
    assert client.post('/api/simulate',json=body(change_type='AUTONOMY_CHANGE',proposed_change={'autonomy_level':'MAKE_IT_UP'}),headers=headers()).status_code==422


def test_raw_event_capture_requires_review(client):
    result=client.post('/api/events',json={'asset_id':'AS-SUPPORT','event_type':'ACCESS_REVIEW_COMPLETED','source_system':'IAM pipeline','source_uri':'iam://run/123','content':'Access review confirms least privilege and permission scope for this model.'},headers=headers('AI_OWNER'))
    assert result.status_code==201,result.text
    assert result.json()['reviewer_status']=='PENDING'


def test_grounded_offline_explanation_does_not_set_status(client):
    result=client.post('/api/agents/explain/AS-SUPPORT?query=model%20validation',json={},headers=headers())
    assert result.status_code==200,result.text
    assert 'status' not in result.json()
    assert set(result.json()['citations']).issubset({s['evidence_id'] for s in result.json()['sources']})


def test_graph_contains_real_relations(client):
    data=client.get('/api/governance-graph/AS-SUPPORT',headers=headers()).json()
    assert {'asset','dependency','control','evidence','obligation'}.issubset({n['kind'] for n in data['nodes']})
    assert all(e['source'] in {n['id'] for n in data['nodes']} and e['target'] in {n['id'] for n in data['nodes']} for e in data['edges'])


def test_stale_scenario_cannot_overwrite_new_registry_context(client):
    scenario=client.post('/api/simulate',json=body(),headers=headers()).json()
    response=client.post('/api/changes',json=body(change_type='MODEL_CHANGE',proposed_change={'version':'2.0'}),headers=headers())
    assert response.status_code==200
    response=client.post('/api/changes',json={**body(),'expected_context_hash':scenario['baseline_context_hash']},headers=headers())
    assert response.status_code==409


def test_concurrent_requests_preserve_chain(client):
    from concurrent.futures import ThreadPoolExecutor
    def simulate(index):
        return client.post('/api/simulate',json=body(reason=f'Concurrent scenario number {index}.'),headers=headers()).status_code
    with ThreadPoolExecutor(max_workers=6) as executor:
        assert list(executor.map(simulate,range(12)))==[200]*12
    assert client.get('/api/audit/verify',headers=headers()).json()['valid']


def test_built_ui_static_files_and_docs_security(client):
    from app import config
    import re
    assert client.get('/docs').status_code==200
    assert 'https://cdn.jsdelivr.net' in client.get('/docs').headers['content-security-policy']
    if not config.FRONTEND_DIST.exists():
        pytest.skip('Build the frontend to exercise the static delivery path')
    response=client.get('/')
    assert response.status_code==200
    assert 'https://cdn.jsdelivr.net' not in response.headers['content-security-policy']
    files=re.findall(r'(?:src|href)="(/static/[^\"]+)"',response.text)
    assert files
    assert all(client.get(path).status_code==200 for path in files)
    assert client.get('/static/.env').status_code==404
    assert client.get('/static/policies/internal-policy.md').status_code==200
