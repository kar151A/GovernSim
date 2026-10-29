"""Idempotent, explicitly synthetic fixtures. Exactly 5 assets and 25 artifacts."""
from datetime import datetime, timezone, timedelta
from sqlalchemy import select
from .db import Asset, Control, Obligation, EvidenceAttestation
from .catalog import CONTROLS, OBLIGATIONS
from .schemas import AssetInput, EvidenceInput
from .agents import ingest
from .service import resolve_asset, persist_assessment
from .audit import append_event, uid, now


def seed(session):
    if session.scalar(select(Asset.id).limit(1)):
        return
    for control in CONTROLS:
        session.add(Control(id=control['control_id'], data=control))
    for obligation in OBLIGATIONS:
        session.add(Obligation(id=obligation['obligation_id'], data=obligation))
    specs = [
        ('AS-SUPPORT', dict(name='Customer Support Agent', owner='Customer Experience', business_purpose='Internal support assistant that retrieves customer records, drafts replies and creates approved tickets.', dependencies=['AS-MODEL', 'AS-DATA'], tools_and_permissions=['tickets:read', 'tickets:create:approval'], deployment_geographies=['IN'])),
        ('AS-HIRING', dict(name='Talent Screening Assistant', owner='People Operations', business_purpose='Rank job applications for human recruiters in the EU.', deployment_geographies=['EU'], risk_tier='HIGH', ai_act_high_risk=True, dpia_required=True, autonomy_level='ADVISORY', model_provider='Enterprise model gateway', dependencies=['AS-MODEL'])),
        ('AS-MODEL', dict(name='Enterprise Language Model', asset_type='MODEL', owner='ML Platform', business_purpose='Versioned model used by internal assistants.', processes_personal_data=False, interacts_with_people=False, autonomy_level='ADVISORY', dependencies=['AS-VENDOR'], version='2026.10')),
        ('AS-DATA', dict(name='Customer Knowledge Index', asset_type='DATASET', owner='Data Platform', business_purpose='Retrieval index of customer support and account records.', autonomy_level='ADVISORY', interacts_with_people=False, tools_and_permissions=['index:read'])),
        ('AS-VENDOR', dict(name='Model Gateway Provider', asset_type='VENDOR_MODEL', owner='Vendor Risk', business_purpose='Managed enterprise model hosting dependency.', processes_personal_data=False, interacts_with_people=False, autonomy_level='ADVISORY', model_provider='Synthetic Gateway Inc.')),
    ]
    for key, fields in specs:
        record = dict(AssetInput(**fields).model_dump(mode='json'), asset_id=key, created_at=now(), last_reviewed_at=None, change_history=[], synthetic=True)
        session.add(Asset(id=key, data=record))
    session.flush()
    distribution = {
        'AS-SUPPORT': [('C-01','RISK_ASSESSMENT'),('C-02','MODEL_CARD'),('C-02','EVALUATION_REPORT'),('C-03','POLICY_DOCUMENT'),('C-04','VENDOR_ATTESTATION'),('C-05','ACCESS_REVIEW'),('C-06','HUMAN_OVERSIGHT_RECORD'),('C-07','MONITORING_REPORT'),('C-09','DATA_LINEAGE'),('C-10','APPROVAL')],
        'AS-HIRING': [('C-01','RISK_ASSESSMENT'),('C-02','MODEL_CARD'),('C-02','EVALUATION_REPORT'),('C-04','DPA'),('C-05','ACCESS_REVIEW'),('C-06','HUMAN_OVERSIGHT_RECORD'),('C-07','MONITORING_REPORT')],
        'AS-MODEL': [('C-01','RISK_ASSESSMENT'),('C-02','MODEL_CARD'),('C-02','EVALUATION_REPORT')],
        'AS-DATA': [('C-03','POLICY_DOCUMENT'),('C-05','ACCESS_REVIEW'),('C-09','DATA_LINEAGE')],
        'AS-VENDOR': [('C-04','VENDOR_ATTESTATION'),('C-10','APPROVAL')],
    }
    for asset_id, entries in distribution.items():
        asset = resolve_asset(session, asset_id)
        for control_id, kind in entries:
            control = session.get(Control, control_id).data
            raw = f'SYNTHETIC DEMO FIXTURE — not real enterprise evidence. {kind} for {asset["name"]}. This fixture illustrates {control["name"]}: {", ".join(control["source_terms"])}. Coverage confirmed only in seeded demonstration scope.'
            submitted = EvidenceInput(control_id=control_id, evidence_type=kind, source_system='Synthetic fixture generator', source_uri=f'seed://{asset_id}/{control_id}/{kind}', captured_at=datetime.now(timezone.utc)-timedelta(days=5), valid_until=datetime.now(timezone.utc)+timedelta(days=85), raw_content=raw)
            record = ingest(session, asset, control, submitted, 'seed-owner')
            attestation_id = uid('ATT')
            attestation = dict(attestation_id=attestation_id, evidence_id=record['evidence_id'], action='VERIFY', reviewer='seed-compliance-reviewer', comment='Synthetic demo attestation only; not a real control verification.', created_at=now())
            session.add(EvidenceAttestation(id=attestation_id, evidence_id=record['evidence_id'], data=attestation))
    session.flush()
    append_event(session, 'SYNTHETIC_SEED_CREATED', 'system', {'assets': 5, 'controls': 10, 'obligations': 30, 'evidence': 25})
    for asset_id, _ in specs:
        persist_assessment(session, asset_id, 'seed-system')
