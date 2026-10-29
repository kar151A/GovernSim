"""Reproducible synthetic evaluation. No production accuracy claims."""
from pathlib import Path
import sys
import os
import tempfile
import json
import time
import copy
from datetime import datetime, timezone, timedelta

root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'backend'))
# Use a fresh disposable SQLite database; do not touch the user's registry.
temp=tempfile.TemporaryDirectory()
os.environ['DATABASE_URL']=f'sqlite:///{Path(temp.name)/"evaluation.db"}'
os.environ['SEED_DEMO']='false'
from app.db import init_db, SessionLocal
from app.seed import seed
from app.service import resolve_asset, resources, simulate
from app.kernel import assess
from app.schemas import ChangeInput
from app.reports import package
from app.agents import propose_mapping

init_db()
with SessionLocal.begin() as session:
    seed(session)
with SessionLocal() as session:
    a=resolve_asset(session,'AS-SUPPORT')
    o,c,e,r=resources(session,'AS-SUPPORT')
    # Hand-labeled deterministic artifact mutations. Positive means an evidence gap is expected.
    cases=[]
    for kind in ('MODEL_CARD','EVALUATION_REPORT','ACCESS_REVIEW','POLICY_DOCUMENT','HUMAN_OVERSIGHT_RECORD'):
        for fault in ('missing','expired','unverified','low_confidence'):
            items=copy.deepcopy(e)
            item=next(x for x in items if x['evidence_type']==kind)
            if fault=='missing': items=[x for x in items if x['evidence_id']!=item['evidence_id']]
            elif fault=='expired': item['valid_until']=(datetime.now(timezone.utc)-timedelta(days=1)).isoformat()
            elif fault=='unverified': item['reviewer_status']='PENDING'
            else: item['confidence']=.3
            prediction=assess(a,o,c,items,r)['evidence_gaps']>0
            cases.append({'name':f'{fault}_{kind}','expected_gap':True,'predicted_gap':prediction})
    for index in range(5):
        items=copy.deepcopy(e)
        items[index]['valid_until']=(datetime.now(timezone.utc)+timedelta(days=index+1)).isoformat()
        cases.append({'name':f'valid_current_fixture_{index+1}','expected_gap':False,'predicted_gap':assess(a,o,c,items,r)['evidence_gaps']>0})
    tp=sum(x['expected_gap'] and x['predicted_gap'] for x in cases)
    fp=sum(not x['expected_gap'] and x['predicted_gap'] for x in cases)
    fn=sum(x['expected_gap'] and not x['predicted_gap'] for x in cases)
    tn=sum(not x['expected_gap'] and not x['predicted_gap'] for x in cases)
    # Independent manually labeled compatible-control retrieval examples (not LLM accuracy).
    golden=[('O-GDPR-03','C-04',True),('O-GDPR-03','C-05',False),('O-INTERNAL_POLICY-01','C-02',True),('O-INTERNAL_POLICY-01','C-07',False),('O-INTERNAL_POLICY-02','C-05',True),('O-INTERNAL_POLICY-02','C-04',False),('O-NIST_AI_RMF-02','C-06',True),('O-NIST_AI_RMF-02','C-09',False)]
    om={x['obligation_id']:x for x in o};cm={x['control_id']:x for x in c}
    mapping=[{'obligation':oid,'control':cid,'expected_type_compatible':expected,'predicted_type_compatible':propose_mapping(om[oid],cm[cid])['compatible_evidence_types']} for oid,cid,expected in golden]
    simulation_checks=[]
    for kind,change,expected in [('GEOGRAPHY',{'deployment_geographies':['IN','EU']},'O-GDPR-01'),('DATA_CHANGE',{'sensitive_data':True},'O-INTERNAL_POLICY-05'),('INCIDENT',{'incident_open':True},'O-INTERNAL_POLICY-04')]:
        result=simulate(session,ChangeInput(asset_id='AS-SUPPORT',change_type=kind,proposed_change=change), 'evaluation')
        simulation_checks.append({'change_type':kind,'expected_new_obligation':expected,'passed':expected in result['newly_applicable_obligations']})
    projection=assess(a,o,c,e,r)
    required={'source_obligation','source_document','source_clause','source_url','control_id','evidence_artifacts','evidence_status','timestamp','model_version','rule_version','confidence','reviewer_action'}
    complete=sum(required.issubset(d['provenance_links']) for d in projection['decisions'])
    all_seen=set()
    escalation=[]
    from app.db import Asset
    from sqlalchemy import select
    for row in session.scalars(select(Asset)):
        result=assess(resolve_asset(session,row.id),*resources(session,row.id))
        all_seen.update(d['obligation_id'] for d in result['decisions'])
    # Scenario coverage is measured separately from all estate fixtures.
    expected_covered=set(om)-{'O-INTERNAL_POLICY-03'}
    all_seen.update(x['expected_new_obligation'] for x in simulation_checks)
    high=copy.deepcopy(a);high.update(risk_tier='HIGH',autonomy_level='AUTONOMOUS')
    high_result=assess(high,o,c,e,r)
    all_seen.update(d['obligation_id'] for d in high_result['decisions'])
    for asset,expected in [(a,False),(high,True),({**a,'incident_open':True},True)]:
        predicted=assess(asset,o,c,e,r)['human_reviews']>0
        escalation.append({'expected_escalation':expected,'predicted_escalation':predicted})
    start=time.perf_counter();report=package(session,'AS-SUPPORT');duration=(time.perf_counter()-start)*1000
    metrics={
        'scope':'Synthetic deterministic fixtures only; not estimates of enterprise or legal accuracy.',
        'evidence_gap_precision':tp/(tp+fp) if tp+fp else 0,'evidence_gap_recall':tp/(tp+fn) if tp+fn else 0,'false_positive_rate':fp/(fp+tn) if fp+tn else 0,
        'confusion_matrix':{'true_positive':tp,'false_positive':fp,'false_negative':fn,'true_negative':tn},
        'type_compatibility_accuracy_on_manual_golden_set':sum(x['expected_type_compatible']==x['predicted_type_compatible'] for x in mapping)/len(mapping),
        'mapping_limitation':'Type compatibility is a coarse guard, not semantic mapping accuracy. All changed mappings require human review. No validated LLM mapping benchmark is claimed.',
        'simulation_correctness':sum(x['passed'] for x in simulation_checks)/len(simulation_checks),
        'representative_obligation_coverage':len(all_seen & set(om))/len(om),'covered_obligations':len(all_seen & set(om)),'library_obligations':len(om),
        'provenance_completeness':complete/len(projection['decisions']),
        'human_review_escalation_accuracy':sum(x['expected_escalation']==x['predicted_escalation'] for x in escalation)/len(escalation),
        'audit_package_generation_ms':round(duration,3),
    }
    output={'generated_at':datetime.now(timezone.utc).isoformat(),'metrics':metrics,'evidence_cases':cases,'mapping_golden_set':mapping,'simulation_checks':simulation_checks,'escalation_checks':escalation}
(root/'evaluation'/'metrics.json').write_text(json.dumps(output,indent=2),encoding='utf-8')
lines=['# GovernSim evaluation report','',metrics['scope'],'','| Metric | Observed result |','| --- | --- |']
for key in ('evidence_gap_precision','evidence_gap_recall','false_positive_rate','type_compatibility_accuracy_on_manual_golden_set','simulation_correctness','representative_obligation_coverage','provenance_completeness','human_review_escalation_accuracy','audit_package_generation_ms'):
    lines.append(f'| {key} | {metrics[key]} |')
lines.extend(['','25 artifact cases (20 faults and 5 valid controls), 8 manually labeled type-compatibility pairs, 3 simulation cases and 3 escalation cases.','',metrics['mapping_limitation'],'','Timing measures one local SQLite run and varies by machine. PostgreSQL, optional cloud LLMs and browser QA are reported separately in docs/VERIFICATION.md.','', 'Run `python scripts/evaluate.py` to reproduce metrics; run `pytest backend/tests -q` for the regression suite.'])
(root/'evaluation'/'REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
print(json.dumps(metrics,indent=2))
# Release pooled SQLite connections before temporary directory removal on Windows.
from app.db import engine
engine.dispose()
temp.cleanup()
