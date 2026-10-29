"""End-to-end API demo against a running local instance. Uses generated local tokens.
Run from the project root: .venv/Scripts/python scripts/demo.py (Windows)
"""
import json
from pathlib import Path
from datetime import datetime, timezone, timedelta
import httpx

root=Path(__file__).resolve().parents[1]
lines=(root/'.local-keys.txt').read_text(encoding='utf-8').splitlines()
def token(role):
    position=next(i for i,line in enumerate(lines) if line.startswith(role+' ('))
    return lines[position+1]
owner={'Authorization':f'Bearer {token("AI_OWNER")}'}
reviewer={'Authorization':f'Bearer {token("COMPLIANCE_REVIEWER")}'}

def check(response):
    response.raise_for_status()
    return response.json()

with httpx.Client(base_url='http://127.0.0.1:8000/api',timeout=60) as client:
    asset=check(client.post('/assets',headers=owner,json={'name':'Demo Support Agent','owner':'Demo AI Owner','business_purpose':'Internal customer support assistant in India.','deployment_geographies':['IN'],'autonomy_level':'ACTION_WITH_APPROVAL','risk_tier':'HIGH'}))
    key=asset['asset_id']
    print('1. Registered',key)
    assessment=check(client.post(f'/assess/{key}',headers=owner,json={}))
    print('2. Initial assessment:',assessment['status'],'gaps:',assessment['evidence_gaps'])
    result=check(client.post('/simulate',headers=owner,json={'asset_id':key,'change_type':'GEOGRAPHY','proposed_change':{'deployment_geographies':['IN','EU']},'reason':'Explore EU expansion before release.'}))
    print('3. EU simulation:',result['scenario_id'],'new requirements:',len(result['newly_applicable_obligations']))
    evidence=check(client.post(f'/assets/{key}/evidence',headers=owner,json={'control_id':'C-06','evidence_type':'HUMAN_OVERSIGHT_RECORD','source_system':'Demo human handoff event','source_uri':'demo://support/human-handoff','valid_until':(datetime.now(timezone.utc)+timedelta(days=30)).isoformat(),'raw_content':'DEMO ONLY: Human oversight owner is assigned, escalation reaches a named operator and the emergency stop procedure has been exercised.'}))
    print('4. Captured oversight evidence:',evidence['reviewer_status'])
    verification=check(client.post(f'/evidence/{evidence["evidence_id"]}/review',headers=reviewer,json={'action':'VERIFY','comment':'Demo reviewer confirms the sample artifact scope and oversight coverage.'}))
    decision=next(d for d in verification['assessment']['decisions'] if d['control_id']=='C-06')
    review=check(client.post(f'/decisions/{decision["decision_id"]}/review',headers=reviewer,json={'action':'APPROVE','comment':'Demo reviewer approves oversight conditionally for this exact local demonstration configuration.'}))
    print('5. Named review recorded:',review['review']['reviewer'])
    report=check(client.get(f'/reports/audit-package/{key}',headers=reviewer))
    out=root/'artifacts';out.mkdir(exist_ok=True)
    (out/f'{key}-audit.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    pdf=client.get(f'/reports/audit-package/{key}?format=pdf',headers=reviewer);pdf.raise_for_status();(out/f'{key}-audit.pdf').write_bytes(pdf.content)
    print('6. JSON and PDF audit packages saved in artifacts/. Other evidence gaps remain open.')
    print('7. Audit chain:',check(client.get('/audit/verify',headers=reviewer))['valid'])
