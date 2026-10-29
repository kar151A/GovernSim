from io import BytesIO
from html import escape
from sqlalchemy import select
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from .audit import now, events, verify
from .db import Asset, Review, Decision, Scenario, ChangeEvent
from .service import resolve_asset, current_assessment
from .agents import load_evidence


def package(session, asset_id):
    asset = resolve_asset(session, asset_id)
    assessment = current_assessment(session, asset_id)
    reviews = [r.data for r in session.scalars(select(Review).join(Decision).where(Decision.asset_id == asset_id))]
    evidence = load_evidence(session, asset_id)
    return dict(schema_version='1.0', generated_at=now(), disclaimer=assessment['disclaimer'], asset=asset, executive_summary={'name': asset['name'], 'status': assessment['status'], 'obligations': assessment['applicable_obligations'], 'evidence_gaps': assessment['evidence_gaps'], 'human_reviews': assessment['human_reviews']}, obligation_mapping=assessment['decisions'], control_status=[{'control_id': d['control_id'], 'status': d['deterministic_status'], 'obligation_id': d['obligation_id']} for d in assessment['decisions']], evidence_inventory=[{k:v for k,v in e.items() if k not in ('embedding', 'raw_content')} for e in evidence], human_approvals=reviews, exceptions=[r for r in reviews if r['action'] in ('OVERRIDE','CHALLENGE','REJECT')], open_remediation_items=[{'obligation_id': d['obligation_id'], 'control_id': d['control_id'], 'missing_types': d['missing_types'], 'reason': d['reason']} for d in assessment['decisions'] if d['deterministic_status'] != 'COMPLIANT'], decision_trail=events(session, asset_id), integrity=verify(session), note='Current kernel projection; immutable saved assessment snapshots remain in the decision trail. Asset-scoped audit events can have sequence gaps because the chain spans the whole estate. Use /audit/verify and global /audit/export for full verification.')


def markdown(data):
    s = data['executive_summary']
    rows = ['# GovernSim · Governance audit package', '', f'Generated: {data["generated_at"]}', '', data['disclaimer'], '', f'## {s["name"]}', '', f'Status: **{s["status"]}** · obligations: {s["obligations"]} · evidence gaps: {s["evidence_gaps"]}', '', '## Obligation mapping and provenance', '']
    for d in data['obligation_mapping']:
        p = d['provenance_links']
        rows.extend([f'### {d["obligation_id"]} — {d["title"]}', '', f'- Status: {d["deterministic_status"]}; control: {d["control_id"]}', f'- Finding: {d["reason"]}', f'- Source: [{p["source_document"]}]({p["source_url"]}), {p["source_clause"]}', f'- Evidence: {", ".join(d["evidence_ids"]) or "Missing"}; missing: {", ".join(d["missing_types"]) or "None"}', f'- Model: {p["model_version"]}; rules: {p["rule_version"]}; policy: {p["policy_version"]}', f'- Confidence: {p["confidence"]}; reviewer: {p["reviewer"] or "None"}; action: {p["reviewer_action"]}', f'- Timestamp: {p["timestamp"]}; context: {p["context_hash"]}', f'- Scope note: {p["coverage_note"]}', ''])
    rows.extend(['## Evidence inventory', ''])
    for item in data['evidence_inventory']:
        rows.extend([f'- {item["evidence_id"]} | {item["evidence_type"]} | {item["reviewer_status"]} | {item["source_uri"]}', f'  - SHA-256: {item["content_hash"]}; captured: {item["captured_at"]}; valid until: {item["valid_until"]}'])
    rows.extend(['', '## Human reviews and exceptions', ''])
    for r in data['human_approvals']:
        rows.append(f'- {r["created_at"]}: {r["reviewer"]} — {r["action"]}: {r["comment"]}')
    rows.extend(['', '## Audit integrity', '', f'Chain valid: {data["integrity"]["valid"]}; checked events: {data["integrity"]["checked"]}', '', f'Head anchor: `{data["integrity"]["head_hash"]}`', '', data['integrity']['limitation'], '', data['note']])
    return '\n'.join(rows)


def pdf(data):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, title='GovernSim audit package', author='GovernSim', rightMargin=42, leftMargin=42, topMargin=42, bottomMargin=42)
    styles = getSampleStyleSheet()
    styles['BodyText'].fontSize = 9
    styles['BodyText'].leading = 13
    styles['BodyText'].wordWrap = 'CJK'
    flow = []
    for line in markdown(data).splitlines():
        if not line:
            flow.append(Spacer(1, 7))
            continue
        style = styles['Heading1'] if line.startswith('# ') else styles['Heading2'] if line.startswith('## ') else styles['Heading3'] if line.startswith('### ') else styles['BodyText']
        flow.append(Paragraph(escape(line.lstrip('# ').replace('**', '')), style))
    def footer(canvas, document):
        canvas.setFillColor(colors.HexColor('#64748b'))
        canvas.setFont('Helvetica', 8)
        canvas.drawString(42, 22, 'GovernSim | Decision support | Representative controls')
        canvas.drawRightString(document.pagesize[0]-42, 22, str(document.page))
    doc.build(flow, onFirstPage=footer, onLaterPages=footer)
    return buffer.getvalue()
