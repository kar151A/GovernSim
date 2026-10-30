"""FastAPI boundary: authentication, RBAC, atomic workflows and static UI."""
import hashlib
import hmac
import json
import logging
import time
from contextlib import asynccontextmanager
from typing import Annotated
import networkx as nx
from fastapi import FastAPI, Depends, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select, text
from . import config
from . import auth
from .locking import transaction_lock
from .audit import append_event, digest, events, now, uid, verify
from .db import SessionLocal, init_db, Asset, Control, Obligation, Evidence, EvidenceAttestation, Decision, Review, Assessment, Scenario, Mapping, ChangeEvent
from .schemas import AssetInput, EvidenceInput, EvidenceReview, ReviewInput, ChangeInput, ControlInput, ObligationInput, MappingInput, MappingApproval, EvidenceEvent
from . import agents, service, reports
from .kernel import RULE_VERSION, evidence_state, evidence_scope, assess
from .seed import seed

logger = logging.getLogger('governsim')
# One process serializes SQLite transactions; PostgreSQL audit appends also use an advisory lock.

@asynccontextmanager
async def lifespan(app):
    if config.AUTH_KEY:
        auth.cipher()
    elif not (config.ALLOW_LEGACY_API_KEYS and config.API_KEYS):
        raise RuntimeError('No authentication encryption key. Run python scripts/bootstrap.py and restart.')
    init_db()
    with SessionLocal.begin() as session:
        agents.init_vector_store(session)
        if config.SEED_DEMO:
            seed(session)
    yield

app = FastAPI(title='GovernSim', version='1.0.0', description='Predictive governance decision support. Not legal advice.', lifespan=lifespan, redoc_url=None)
app.include_router(auth.router)
app.add_middleware(CORSMiddleware, allow_origins=['http://localhost:5173', 'http://127.0.0.1:5173'], allow_credentials=False, allow_methods=['GET', 'POST'], allow_headers=['Authorization', 'Content-Type'])
security = HTTPBearer(auto_error=False)

@app.middleware('http')
async def request_context(request: Request, call_next):
    started = time.monotonic()
    request_id = uid('REQ')
    try:
        if int(request.headers.get('content-length', '0')) > 1_000_000:
            return JSONResponse({'detail': 'Request exceeds 1 MB limit'}, status_code=413)
    except ValueError:
        return JSONResponse({'detail': 'Invalid content length'}, status_code=400)
    response = await call_next(request)
    response.headers.update({'X-Request-ID': request_id, 'X-Content-Type-Options': 'nosniff', 'X-Frame-Options': 'DENY', 'Referrer-Policy': 'no-referrer', 'Cache-Control': 'no-store', 'Content-Security-Policy': "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"})
    if request.url.path in ('/docs', '/docs/oauth2-redirect'):
        # Standard Swagger UI uses its documented CDN and inline initialization.
        # Keep this allowance scoped to API documentation, never the product UI.
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self' https://cdn.jsdelivr.net 'unsafe-inline'; style-src 'self' https://cdn.jsdelivr.net 'unsafe-inline'; img-src 'self' data: https://fastapi.tiangolo.com; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'"
    logger.info(json.dumps({'request_id': request_id, 'method': request.method, 'path': request.url.path, 'status': response.status_code, 'duration_ms': round((time.monotonic()-started)*1000, 2)}))
    return response

@app.exception_handler(RequestValidationError)
async def validation_error(request, exc):
    # FastAPI's default validation response includes input values; omit them for credentials.
    errors = [{'loc': error['loc'], 'msg': error['msg'], 'type': error['type']} for error in exc.errors()]
    return JSONResponse({'detail': errors}, status_code=422)

@app.exception_handler(ValueError)
async def invalid_value(request, exc):
    return JSONResponse({'detail': str(exc)}, status_code=422)


def principal(request: Request, credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)]):
    account = auth.account_principal(request)
    if account:
        return account
    if credentials and config.ALLOW_LEGACY_API_KEYS:
        hashed = hashlib.sha256(credentials.credentials.encode()).hexdigest()
        for key, identity in config.API_KEYS.items():
            if hmac.compare_digest(key, hashed):
                return identity
    raise HTTPException(401, 'Sign in with your account and complete two-factor verification', headers={'WWW-Authenticate': 'Bearer'})


def role(*allowed):
    def check(identity=Depends(principal)):
        if identity['role'] not in allowed:
            raise HTTPException(403, 'This role cannot perform this action')
        return identity
    return check

Read = Annotated[dict, Depends(principal)]
Write = Annotated[dict, Depends(role('AI_OWNER', 'RISK_OFFICER', 'ADMIN'))]
Reviewer = Annotated[dict, Depends(role('COMPLIANCE_REVIEWER', 'RISK_OFFICER', 'ADMIN'))]
Admin = Annotated[dict, Depends(role('ADMIN'))]


def db():
    with transaction_lock:
        with SessionLocal() as session:
            try:
                yield session
                session.commit()
            except Exception:
                session.rollback()
                raise
DB = Annotated[object, Depends(db)]

@app.get('/health')
def health(session: DB):
    session.execute(text('SELECT 1'))
    return {'status': 'ok', 'service': 'GovernSim', 'version': '1.0.0', 'rule_version': RULE_VERSION}

@app.get('/api/session')
def session_info(identity: Read):
    return identity

@app.get('/api/assets')
def list_assets(session: DB, identity: Read):
    result = []
    for row in session.scalars(select(Asset).order_by(Asset.id)):
        projection = service.current_assessment(session, row.id)
        result.append({**row.data, 'governance_status': projection['status'], 'open_gaps': projection['evidence_gaps'], 'human_reviews': projection['human_reviews'], 'applicable_obligations': projection['applicable_obligations']})
    return result

@app.post('/assets', status_code=201)
@app.post('/api/assets', status_code=201)
def create_asset(value: AssetInput, session: DB, identity: Write):
    for dependency in value.dependencies:
        service.get_or_404(session, Asset, dependency)
    record = dict(value.model_dump(mode='json'), asset_id=uid('AS'), created_at=now(), change_history=[], last_reviewed_at=None, synthetic=False)
    session.add(Asset(id=record['asset_id'], data=record))
    append_event(session, 'ASSET_REGISTERED', identity['name'], record, record['asset_id'])
    return record

@app.get('/assets/{asset_id}')
@app.get('/api/assets/{asset_id}')
def asset_profile(asset_id: str, session: DB, identity: Read):
    return {'asset': service.resolve_asset(session, asset_id), 'assessment': service.current_assessment(session, asset_id), 'evidence': agents.load_evidence(session, asset_id), 'assessments': [a.data for a in session.scalars(select(Assessment).where(Assessment.asset_id == asset_id))]}

@app.post('/assets/{asset_id}/evidence', status_code=201)
@app.post('/api/assets/{asset_id}/evidence', status_code=201)
def submit_evidence(asset_id: str, value: EvidenceInput, session: DB, identity: Write):
    asset = service.resolve_asset(session, asset_id)
    control = service.get_or_404(session, Control, value.control_id).data
    try:
        record = agents.ingest(session, asset, control, value, identity['name'])
    except ValueError as exc:
        raise HTTPException(409 if 'Duplicate' in str(exc) else 422, str(exc)) from exc
    append_event(session, 'EVIDENCE_INGESTED', identity['name'], {'evidence_id': record['evidence_id'], 'content_hash': record['content_hash'], 'scope': record['scope']}, asset_id)
    return record

@app.post('/api/evidence/{evidence_id}/review')
def review_evidence(evidence_id: str, value: EvidenceReview, session: DB, identity: Reviewer):
    item = service.get_or_404(session, Evidence, evidence_id)
    if item.data['submitted_by'] == identity['name']:
        raise HTTPException(403, 'Evidence must be verified by a different named principal')
    if value.action == 'VERIFY' and not item.data.get('coverage_terms'):
        raise HTTPException(422, 'No control coverage indicators found. Submit a relevant artifact before verification.')
    record = dict(attestation_id=uid('ATT'), evidence_id=evidence_id, reviewer=identity['name'], **value.model_dump(), created_at=now())
    session.add(EvidenceAttestation(id=record['attestation_id'], evidence_id=evidence_id, data=record))
    receipt = append_event(session, 'EVIDENCE_REVIEWED', identity['name'], record, item.asset_id)
    return {**record, 'assessment': service.persist_assessment(session, item.asset_id, identity['name']), 'audit_receipt': receipt}

@app.post('/obligations', status_code=201)
@app.post('/api/obligations', status_code=201)
def create_obligation(value: ObligationInput, session: DB, identity: Admin):
    if session.get(Obligation, value.obligation_id):
        raise HTTPException(409, 'Obligation already exists')
    # Initial library addition is an explicit admin action; subsequent mappings use dual review.
    for control_id in value.control_ids:
        control = service.get_or_404(session, Control, control_id).data
        if not set(value.evidence_required).issubset(control['linked_evidence_types']):
            raise HTTPException(422, 'Obligation evidence is incompatible with selected control')
    record = dict(value.model_dump(), approved=True, version=1, added_by=identity['name'], added_at=now())
    session.add(Obligation(id=value.obligation_id, data=record))
    append_event(session, 'OBLIGATION_ADDED', identity['name'], record)
    return record

@app.post('/controls', status_code=201)
@app.post('/api/controls', status_code=201)
def create_control(value: ControlInput, session: DB, identity: Admin):
    if session.get(Control, value.control_id):
        raise HTTPException(409, 'Control already exists')
    record = dict(value.model_dump(), validation_logic='EVIDENCE_VALIDITY_V1', added_by=identity['name'])
    session.add(Control(id=value.control_id, data=record))
    append_event(session, 'CONTROL_ADDED', identity['name'], record)
    return record

@app.get('/api/library')
def library(session: DB, identity: Read):
    return {'controls': [c.data for c in session.scalars(select(Control).order_by(Control.id))], 'obligations': [o.data for o in session.scalars(select(Obligation).order_by(Obligation.id))], 'mappings': [m.data for m in session.scalars(select(Mapping))]}

@app.post('/mappings/propose')
@app.post('/api/mappings/propose')
def mapping_proposal(value: MappingInput, session: DB, identity: Write):
    obligation = service.get_or_404(session, Obligation, value.obligation_id).data
    control = service.get_or_404(session, Control, value.control_id).data
    result = agents.propose_mapping(obligation, control)
    if not set(obligation['evidence_required']).issubset(control['linked_evidence_types']):
        raise HTTPException(422, 'Mapping does not cover the obligation evidence requirements')
    record = dict(mapping_id=uid('MAP'), **value.model_dump(), **result, proposed_by=identity['name'], created_at=now())
    session.add(Mapping(id=record['mapping_id'], data=record))
    append_event(session, 'MAPPING_PROPOSED', identity['name'], record)
    return record

@app.post('/mappings/approve')
@app.post('/api/mappings/approve')
def mapping_approval(value: MappingApproval, session: DB, identity: Reviewer):
    mapping = service.get_or_404(session, Mapping, value.mapping_id)
    if mapping.data['approval_state'] != 'PENDING':
        raise HTTPException(409, 'Mapping already reviewed')
    if mapping.data['proposed_by'] == identity['name']:
        raise HTTPException(403, 'A different named reviewer must approve the mapping')
    mapping.data = {**mapping.data, 'approval_state': 'APPROVED' if value.approve else 'REJECTED', 'reviewer': identity['name'], 'comment': value.comment, 'reviewed_at': now()}
    if value.approve:
        row = service.get_or_404(session, Obligation, mapping.data['obligation_id'])
        row.data = {**row.data, 'control_ids': [mapping.data['control_id']], 'version': row.data.get('version', 1) + 1}
    append_event(session, 'MAPPING_REVIEWED', identity['name'], mapping.data)
    return mapping.data

@app.post('/assess/{asset_id}')
@app.post('/api/assess/{asset_id}')
def run_assessment(asset_id: str, session: DB, identity: Write):
    return service.persist_assessment(session, asset_id, identity['name'])

@app.post('/simulate')
@app.post('/api/simulate')
def run_simulation(value: ChangeInput, session: DB, identity: Write):
    return service.simulate(session, value, identity['name'])

@app.get('/api/simulations')
def scenarios(session: DB, identity: Read):
    return [s.data for s in session.scalars(select(Scenario))]

@app.get('/simulations/{simulation_id}')
@app.get('/api/simulations/{simulation_id}')
def simulation(simulation_id: str, session: DB, identity: Read):
    return service.get_or_404(session, Scenario, simulation_id).data

@app.post('/api/changes')
def change(value: ChangeInput, session: DB, identity: Write):
    if value.change_type == 'POLICY_CHANGE' and identity['role'] != 'ADMIN':
        raise HTTPException(403, 'Only an admin can activate a versioned policy profile')
    return service.apply_change(session, value, identity['name'])

@app.get('/api/changes')
def changes(session: DB, identity: Read):
    return sorted([c.data for c in session.scalars(select(ChangeEvent))], key=lambda c:c['created_at'], reverse=True)

@app.post('/api/policies/activate')
def policy_estate(value: ChangeInput, session: DB, identity: Admin):
    if value.change_type != 'POLICY_CHANGE':
        raise HTTPException(422, 'Policy activation requires POLICY_CHANGE')
    results = []
    for row in session.scalars(select(Asset).order_by(Asset.id)).all():
        update = value.model_copy(update={'asset_id': row.id})
        results.append(service.apply_change(session, update, identity['name']))
    return {'affected_assets': len(results), 'changes': results}

@app.get('/api/reviews')
def review_queue(session: DB, identity: Read):
    pending = []
    for asset in session.scalars(select(Asset)):
        projection = service.current_assessment(session, asset.id)
        snapshots = sorted([a.data for a in session.scalars(select(Assessment).where(Assessment.asset_id == asset.id))], key=lambda a:a['assessed_at'], reverse=True)
        # Display stable saved decision IDs; regenerate snapshots after input mutations via UI.
        current = next((a for a in snapshots if a['context_hash'] == projection['context_hash']), None)
        if current:
            for decision in current['decisions']:
                live = next((d for d in projection['decisions'] if d['obligation_id'] == decision['obligation_id'] and d['control_id'] == decision['control_id']), decision)
                if live['human_review_required']:
                    pending.append({**live, 'decision_id': decision['decision_id'], 'asset_name': asset.data['name']})
    evidence = [e for asset in session.scalars(select(Asset)) for e in agents.load_evidence(session, asset.id) if e['reviewer_status'] == 'PENDING']
    return {'decisions': pending, 'evidence': evidence, 'history': sorted([r.data for r in session.scalars(select(Review))], key=lambda r:r['created_at'], reverse=True), 'mappings': [m.data for m in session.scalars(select(Mapping)) if m.data['approval_state'] == 'PENDING']}

@app.post('/decisions/{decision_id}/review')
@app.post('/api/decisions/{decision_id}/review')
def review_decision(decision_id: str, value: ReviewInput, session: DB, identity: Reviewer):
    decision = service.get_or_404(session, Decision, decision_id)
    projection = service.current_assessment(session, decision.asset_id)
    if projection['context_hash'] != decision.data['context_hash']:
        raise HTTPException(409, 'Decision is stale; run a new assessment before review')
    current = next(d for d in projection['decisions'] if d['obligation_id'] == decision.data['obligation_id'] and d['control_id'] == decision.data['control_id'])
    if value.action in ('APPROVE', 'OVERRIDE') and (current['missing_types'] or any(s in ('HASH_MISMATCH','CONFLICTING') for s in current['evidence_states'].values())):
        raise HTTPException(422, 'Approval cannot bypass missing or conflicting evidence')
    record = dict(review_id=uid('REV'), decision_id=decision_id, asset_id=decision.asset_id, obligation_id=decision.data['obligation_id'], control_id=decision.data['control_id'], context_hash=projection['context_hash'], reviewer=identity['name'], **value.model_dump(), created_at=now())
    session.add(Review(id=record['review_id'], decision_id=decision_id, data=record))
    append_event(session, 'DECISION_REVIEWED', identity['name'], record, decision.asset_id)
    session.flush()
    return {'review': record, 'assessment': service.persist_assessment(session, decision.asset_id, identity['name'])}

@app.get('/audit/verify')
@app.get('/api/audit/verify')
def audit_integrity(session: DB, identity: Read):
    return verify(session)

@app.get('/api/audit/export')
def global_audit(session: DB, identity: Read):
    return {'events': events(session), 'integrity': verify(session)}

@app.get('/audit/{asset_id}')
@app.get('/api/audit/{asset_id}')
def audit(asset_id: str, session: DB, identity: Read):
    service.get_or_404(session, Asset, asset_id)
    return {'events': events(session, asset_id), 'integrity': verify(session)}

@app.get('/reports/audit-package/{asset_id}')
@app.get('/api/reports/audit-package/{asset_id}')
def audit_report(asset_id: str, session: DB, identity: Read, format: str = Query('json', pattern='^(json|markdown|pdf)$')):
    data = reports.package(session, asset_id)
    if format == 'markdown':
        return Response(reports.markdown(data), media_type='text/markdown', headers={'Content-Disposition': f'attachment; filename="{asset_id}-audit.md"'})
    if format == 'pdf':
        return Response(reports.pdf(data), media_type='application/pdf', headers={'Content-Disposition': f'attachment; filename="{asset_id}-audit.pdf"'})
    return data

@app.get('/governance-graph/{asset_id}')
@app.get('/api/governance-graph/{asset_id}')
def graph(asset_id: str, session: DB, identity: Read):
    asset = service.resolve_asset(session, asset_id)
    projection = service.current_assessment(session, asset_id)
    graph = nx.DiGraph()
    graph.add_node(asset_id, label=asset['name'], kind='asset')
    for dependency in asset.get('dependency_versions', {}):
        graph.add_node(dependency, label=session.get(Asset, dependency).data['name'], kind='dependency')
    for parent in [asset_id, *asset.get('dependency_versions', {})]:
        for child in session.get(Asset, parent).data['dependencies']:
            graph.add_edge(parent, child, relation='depends_on')
    for decision in projection['decisions']:
        oid, cid = decision['obligation_id'], decision['control_id']
        graph.add_node(oid, label=decision['title'], kind='obligation', status=decision['deterministic_status'], source_url=decision['provenance_links']['source_url'])
        graph.add_node(cid, label=decision['control_name'], kind='control')
        graph.add_edge(asset_id, oid, relation='subject_to')
        graph.add_edge(oid, cid, relation='implemented_by')
        for eid in decision['evidence_ids']:
            graph.add_node(eid, label=eid, kind='evidence')
            graph.add_edge(cid, eid, relation='supported_by')
    return {'nodes': [{'id':key, **data} for key,data in graph.nodes(data=True)], 'edges': [{'source':a, 'target':b, **data} for a,b,data in graph.edges(data=True)]}

@app.get('/api/retrieval/{asset_id}')
def retrieval(asset_id: str, session: DB, identity: Read, query: str = Query(min_length=3, max_length=500)):
    service.get_or_404(session, Asset, asset_id)
    return {'method': '128-dimensional signed lexical hashing; pgvector on PostgreSQL, cosine fallback on SQLite', 'results': agents.retrieve(session, asset_id, query)}

@app.post('/api/agents/explain/{asset_id}')
async def explain(asset_id: str, session: DB, identity: Read, query: str = Query(min_length=3, max_length=500)):
    service.get_or_404(session, Asset, asset_id)
    try:
        result = await agents.grounded_explanation(session, asset_id, query)
    except Exception as exc:
        logger.warning('Grounded explanation failed: %s', type(exc).__name__)
        raise HTTPException(502, 'Explanation provider unavailable or output failed grounding validation') from exc
    append_event(session, 'AGENT_EXPLANATION_CREATED', identity['name'], {'asset_id': asset_id, 'provider': result['provider'], 'model': result['model'], 'citations': result['citations'], 'usage': result.get('usage'), 'cost': None, 'output_hash': digest(result)}, asset_id)
    return result

@app.post('/api/events', status_code=201)
def ingest_event(value: EvidenceEvent, session: DB, identity: Write):
    from datetime import datetime, timezone, timedelta
    kinds = {'MODEL_EVALUATED': ('C-02','EVALUATION_REPORT'), 'ACCESS_REVIEW_COMPLETED': ('C-05','ACCESS_REVIEW'), 'MONITORING_EXPORTED': ('C-07','MONITORING_REPORT'), 'HUMAN_HANDOFF_RECORDED': ('C-06','HUMAN_OVERSIGHT_RECORD')}
    cid, kind = kinds[value.event_type]
    evidence = EvidenceInput(control_id=cid, evidence_type=kind, source_system=value.source_system, source_uri=value.source_uri, raw_content=value.content, valid_until=datetime.now(timezone.utc)+timedelta(days=90))
    record = agents.ingest(session, service.resolve_asset(session, value.asset_id), session.get(Control, cid).data, evidence, identity['name'])
    append_event(session, 'EVENT_EVIDENCE_CAPTURED', identity['name'], {'event_type': value.event_type, 'evidence_id': record['evidence_id'], 'content_hash': record['content_hash']}, value.asset_id)
    return record

# API routes precede static serving; unknown /api routes remain JSON 404s.
if config.FRONTEND_DIST.exists():
    app.mount('/static', StaticFiles(directory=config.FRONTEND_DIST), name='static')
    @app.get('/')
    def ui():
        return FileResponse(config.FRONTEND_DIST / 'index.html')
