import hashlib
import json
import uuid
from datetime import datetime, timezone
from sqlalchemy import select, text
from .db import AuditEvent


def now():
    return datetime.now(timezone.utc).isoformat()


def uid(prefix):
    return f'{prefix}-{uuid.uuid4().hex[:16]}'


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def append_event(session, action, actor, payload, asset_id=None):
    if session.bind.dialect.name == 'postgresql':
        session.execute(text('SELECT pg_advisory_xact_lock(742901)'))
    # Flush is important when multiple events are written in one transaction.
    session.flush()
    previous = session.scalar(select(AuditEvent).order_by(AuditEvent.sequence.desc()).limit(1))
    sequence = previous.sequence + 1 if previous else 1
    previous_hash = previous.content_hash if previous else '0' * 64
    event_id = uid('EVT')
    content = dict(sequence=sequence, event_id=event_id, asset_id=asset_id, timestamp=now(), action=action, actor=actor, payload=payload, previous_hash=previous_hash)
    content_hash = digest(content)
    session.add(AuditEvent(sequence=sequence, event_id=event_id, asset_id=asset_id, previous_hash=previous_hash, content_hash=content_hash, canonical_payload=canonical(content)))
    session.flush()
    return dict(sequence=sequence, event_id=event_id, content_hash=content_hash, previous_hash=previous_hash)


def verify(session):
    previous = '0' * 64
    count = 0
    for count, event in enumerate(session.scalars(select(AuditEvent).order_by(AuditEvent.sequence)), 1):
        payload = json.loads(event.canonical_payload)
        if event.sequence != count or event.previous_hash != previous or payload.get('previous_hash') != previous or payload.get('sequence') != count or payload.get('event_id') != event.event_id or payload.get('asset_id') != event.asset_id or digest(payload) != event.content_hash:
            return dict(valid=False, checked=count, failed_sequence=event.sequence, head_hash=previous)
        previous = event.content_hash
    return dict(valid=True, checked=count, head_hash=previous, limitation='Hash-chain verification is relative to the stored history. Retain externally signed head anchors to detect privileged truncation or replacement.')


def events(session, asset_id=None):
    query = select(AuditEvent).order_by(AuditEvent.sequence)
    if asset_id:
        query = query.where(AuditEvent.asset_id == asset_id)
    return [dict(**json.loads(row.canonical_payload), content_hash=row.content_hash) for row in session.scalars(query)]
