import hashlib
import sys
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import main, db, config

TOKENS = {'ADMIN':'test-admin','AI_OWNER':'test-owner','COMPLIANCE_REVIEWER':'test-reviewer','RISK_OFFICER':'test-risk','AUDITOR':'test-auditor'}

def headers(role='ADMIN'):
    return {'Authorization': f'Bearer {TOKENS[role]}'}

@pytest.fixture
def client(tmp_path, monkeypatch):
    engine = create_engine(f'sqlite:///{tmp_path / "test.db"}', connect_args={'check_same_thread':False})
    factory = sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(db, 'engine', engine)
    monkeypatch.setattr(db, 'SessionLocal', factory)
    monkeypatch.setattr(main, 'SessionLocal', factory)
    monkeypatch.setattr(config, 'SEED_DEMO', True)
    monkeypatch.setattr(config, 'ALLOW_LEGACY_API_KEYS', True)
    monkeypatch.setattr(config, 'API_KEYS', {hashlib.sha256(token.encode()).hexdigest():{'name':role.lower(),'role':role} for role,token in TOKENS.items()})
    with TestClient(main.app) as value:
        value.factory = factory
        yield value
    engine.dispose()

@pytest.fixture
def twin(client):
    from app.service import resolve_asset, resources
    with client.factory() as session:
        asset = resolve_asset(session, 'AS-SUPPORT')
        obligations, controls, evidence, reviews = resources(session, 'AS-SUPPORT')
    return asset, obligations, controls, evidence, reviews
