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
    monkeypatch.setattr(config,'ALLOW_LEGACY_API_KEYS',True)
    monkeypatch.setattr(db,'SessionLocal',factory)
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
        # Exercise real cookie + TOTP authentication on PostgreSQL too.
        import secrets
        import time
        import pyotp
        from cryptography.fernet import Fernet
        from app.auth import hashed, CSRF_COOKIE
        from app.db import AuthUser, AuthInvitation
        monkeypatch.setattr(config, 'AUTH_KEY', Fernet.generate_key().decode())
        monkeypatch.setattr(config, 'AUTH_ALLOWED_ORIGINS', {'http://testserver'})
        monkeypatch.setattr(config, 'ALLOW_LEGACY_API_KEYS', False)
        monkeypatch.setattr(config, 'AUTH_COOKIE_SECURE', False)
        invitation = secrets.token_urlsafe(32)
        with factory.begin() as session:
            user = AuthUser(id='pg-auth-user', email='pg-owner@example.test', role='AI_OWNER',
                            enabled=True, last_totp_step=-1, recovery_hashes=[])
            session.add(user)
            session.flush()
            session.add(AuthInvitation(token_hash=hashed(invitation), user_id=user.id, expires_at=time.time()+300))
        origin = {'Origin': 'http://testserver'}
        setup = client.post('/api/auth/enroll/start', headers=origin, json={
            'email': 'pg-owner@example.test', 'password': 'a sufficiently long test passphrase', 'invitation': invitation})
        assert setup.status_code == 200, setup.text
        confirmed = client.post('/api/auth/enroll/confirm', headers=origin,
                                json={'code': pyotp.TOTP(setup.json()['secret']).now()})
        assert confirmed.status_code == 200, confirmed.text
        assert client.get('/api/assets').status_code == 200
        mutation_headers = {**origin, 'X-CSRF-Token': client.cookies.get(CSRF_COOKIE)}
        assert client.post('/api/assess/AS-SUPPORT', headers=mutation_headers, json={}).status_code == 200
        assert client.post('/api/auth/logout', headers=mutation_headers, json={}).status_code == 200
        assert client.get('/api/assets', headers=headers).status_code == 401
        with factory() as session:
            with pytest.raises(Exception):
                session.execute(text('DELETE FROM audit_events WHERE sequence=1'))
            session.rollback()
    engine.dispose()
