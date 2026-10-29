"""Runs in GitHub CI or against a disposable explicitly supplied pgvector DB.
Never points at the user's normal database. Not executed without TEST_POSTGRES_URL.
"""
import os
import hashlib
import pytest
from sqlalchemy import create_engine, text, select
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient
from app import db, main, config

@pytest.mark.skipif(not os.getenv('TEST_POSTGRES_URL'), reason='Disposable PostgreSQL URL not configured')
def test_postgresql_pgvector_workflow(monkeypatch):
    engine=create_engine(os.environ['TEST_POSTGRES_URL'])
    factory=sessionmaker(engine,expire_on_commit=False)
    monkeypatch.setattr(db,'engine',engine)
    monkeypatch.setattr(main,'SessionLocal',factory)
    monkeypatch.setattr(config,'SEED_DEMO',True)
    monkeypatch.setattr(config,'API_KEYS',{hashlib.sha256(b'postgres-test-only').hexdigest():{'name':'pg-test','role':'ADMIN'}})
    headers={'Authorization':'Bearer postgres-test-only'}
    with TestClient(main.app) as client:
        assert client.get('/health').status_code==200
        with factory() as session:
            assert session.scalar(text('SELECT count(*) FROM evidence_vectors'))>=25
        result=client.get('/api/retrieval/AS-SUPPORT?query=model%20validation',headers=headers)
        assert result.status_code==200,result.text
        assert result.json()['results']
        result=client.post('/api/simulate',json={'asset_id':'AS-SUPPORT','change_type':'GEOGRAPHY','proposed_change':{'deployment_geographies':['IN','EU']},'reason':'Verify PostgreSQL simulation.'},headers=headers)
        assert result.status_code==200,result.text
        assert result.json()['newly_applicable_obligations']
        assert client.get('/api/audit/verify',headers=headers).json()['valid']
        with factory() as session:
            with pytest.raises(Exception):
                session.execute(text('DELETE FROM audit_events WHERE sequence=1'))
            session.rollback()
    engine.dispose()
