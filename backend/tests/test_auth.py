"""Password + MFA boundaries exercised through the real API and isolated database."""
import json
import secrets
import time
from types import SimpleNamespace

from cryptography.fernet import Fernet
import pyotp
import pytest
from sqlalchemy import select

from app import auth, config
from app.db import AuthUser, AuthInvitation, AuthChallenge, AuthSession, AuthThrottle
from conftest import headers

ORIGIN = {'Origin': 'http://testserver'}
EMAIL = 'owner@example.test'
PASSWORD = 'correct horse battery staple'


@pytest.fixture
def account(client, monkeypatch):
    clock = {'now': float(int(time.time() // 30) * 30 + 2)}
    monkeypatch.setattr(auth, 'time', SimpleNamespace(time=lambda: clock['now']))
    monkeypatch.setattr(config, 'AUTH_KEY', Fernet.generate_key().decode())
    monkeypatch.setattr(config, 'AUTH_ALLOWED_ORIGINS', {'http://testserver'})
    monkeypatch.setattr(config, 'AUTH_COOKIE_SECURE', False)
    monkeypatch.setattr(config, 'ALLOW_LEGACY_API_KEYS', False)
    client.clock = clock
    return client


def invite(client, email=EMAIL, role='AI_OWNER', seconds=86400):
    token = secrets.token_urlsafe(32)
    with client.factory.begin() as session:
        user = session.scalar(select(AuthUser).where(AuthUser.email == email))
        if not user:
            user = AuthUser(id=secrets.token_hex(16), email=email, role=role, enabled=True,
                            last_totp_step=-1, recovery_hashes=[])
            session.add(user)
            session.flush()
        session.add(AuthInvitation(token_hash=auth.hashed(token), user_id=user.id,
                                   expires_at=client.clock['now'] + seconds))
    return token


def start(client, invitation=None, password=PASSWORD, email=EMAIL):
    return client.post('/api/auth/enroll/start', headers=ORIGIN,
                       json={'email': email, 'password': password, 'invitation': invitation or invite(client, email)})


def code(client, secret, advance=True):
    if advance:
        client.clock['now'] += 30
    return pyotp.TOTP(secret).at(client.clock['now'])


def enroll(client, email=EMAIL, role='AI_OWNER', password=PASSWORD):
    setup = start(client, invite(client, email, role), password, email)
    assert setup.status_code == 200, setup.text
    secret = setup.json()['secret']
    result = client.post('/api/auth/enroll/confirm', headers=ORIGIN, json={'code': code(client, secret)})
    assert result.status_code == 200, result.text
    return secret, result.json()['recovery_codes'], result


def login(client, email=EMAIL, password=PASSWORD):
    return client.post('/api/auth/login', headers=ORIGIN, json={'email': email, 'password': password})


def csrf(client):
    return {**ORIGIN, 'X-CSRF-Token': client.cookies.get(auth.CSRF_COOKIE)}


def test_password_alone_and_legacy_tokens_cannot_enter(account):
    secret, _, _ = enroll(account)
    account.cookies.clear()
    assert account.get('/api/assets', headers=headers()).status_code == 401
    assert login(account).status_code == 200
    assert auth.SESSION_COOKIE not in account.cookies
    assert account.get('/api/session').status_code == 401
    result = account.post('/api/auth/verify', headers=ORIGIN, json={'code': code(account, secret)})
    assert result.status_code == 200
    assert account.get('/api/session').json()['role'] == 'AI_OWNER'
    assert account.get('/api/assets').status_code == 200


def test_enrollment_is_invite_only_and_role_is_server_owned(account):
    token = invite(account, role='AUDITOR')
    assert account.post('/api/auth/enroll/start', headers=ORIGIN, json={'email': EMAIL, 'password': PASSWORD,
           'invitation': token, 'role': 'ADMIN'}).status_code == 422
    setup = start(account, token)
    assert setup.status_code == 200
    assert account.get('/api/assets').status_code == 401
    result = account.post('/api/auth/enroll/confirm', headers=ORIGIN, json={'code': code(account, setup.json()['secret'])})
    assert result.json()['identity']['role'] == 'AUDITOR'
    assert account.post('/api/assess/AS-SUPPORT', headers=csrf(account), json={}).status_code == 403


@pytest.mark.parametrize('kind', ['unknown', 'expired', 'wrong_email'])
def test_invalid_invitations_fail(account, kind):
    token = secrets.token_urlsafe(32) if kind == 'unknown' else invite(account, seconds=-1 if kind == 'expired' else 300)
    email = 'different@example.test' if kind == 'wrong_email' else EMAIL
    assert start(account, token, email=email).status_code == 401
    assert auth.SESSION_COOKIE not in account.cookies


def test_invitation_is_single_use_and_qr_contains_only_enrollment_data(account):
    token = invite(account)
    setup = start(account, token)
    assert setup.status_code == 200
    assert setup.json()['qr_image'].startswith('data:image/svg+xml;base64,')
    assert start(account, token).status_code == 401
    with account.factory() as session:
        challenge = session.scalar(select(AuthChallenge))
        assert setup.json()['secret'] not in json.dumps(challenge.payload)
        assert PASSWORD not in json.dumps(challenge.payload)


def test_setup_requires_valid_totp_and_preserves_password_spaces(account):
    password = '  a long private passphrase  '
    setup = start(account, password=password)
    secret = setup.json()['secret']
    wrong = str((int(code(account, secret)) + 1) % 1000000).zfill(6)
    assert account.post('/api/auth/enroll/confirm', headers=ORIGIN, json={'code': wrong}).status_code == 401
    result = account.post('/api/auth/enroll/confirm', headers=ORIGIN, json={'code': code(account, secret)})
    assert result.status_code == 200
    account.cookies.clear()
    assert login(account, password=password.strip()).status_code == 401
    assert login(account, password=password).status_code == 200


def test_short_password_validation_does_not_echo_password(account):
    response = start(account, password='secret-short')
    assert response.status_code == 422
    assert 'secret-short' not in response.text


def test_enrollment_and_session_storage_do_not_retain_plaintext_credentials(account):
    secret, recovery, _ = enroll(account)
    raw_session = account.cookies.get(auth.SESSION_COOKIE)
    with account.factory() as session:
        user = session.scalar(select(AuthUser))
        saved = session.scalar(select(AuthSession))
        assert user.password_hash.startswith('$argon2id$')
        assert auth.passwords.verify(PASSWORD, user.password_hash)
        assert user.totp_encrypted != secret
        assert auth.cipher().decrypt(user.totp_encrypted.encode()).decode() == secret
        assert saved.token_hash == auth.hashed(raw_session)
        assert raw_session != saved.token_hash
        assert all(c.replace('-', '') not in user.recovery_hashes for c in recovery)


def test_session_cookie_is_httponly_and_expiring(account):
    _, _, response = enroll(account)
    cookies = response.headers.get_list('set-cookie')
    session_cookie = next(c for c in cookies if c.startswith(auth.SESSION_COOKIE + '='))
    assert 'HttpOnly' in session_cookie and 'SameSite=strict' in session_cookie
    assert 'Max-Age=28800' in session_cookie
    account.clock['now'] += auth.SESSION_SECONDS + 1
    assert account.get('/api/assets').status_code == 401


def test_totp_replay_and_consumed_challenge_are_rejected(account):
    secret, _, _ = enroll(account)
    account.cookies.clear()
    assert login(account).status_code == 200
    assert account.post('/api/auth/verify', headers=ORIGIN,
                        json={'code': code(account, secret, advance=False)}).status_code == 401
    fresh = code(account, secret)
    assert account.post('/api/auth/verify', headers=ORIGIN, json={'code': fresh}).status_code == 200
    assert account.post('/api/auth/verify', headers=ORIGIN, json={'code': fresh}).status_code == 401
    account.cookies.clear()
    assert login(account).status_code == 200
    assert account.post('/api/auth/verify', headers=ORIGIN, json={'code': fresh}).status_code == 401


def test_recovery_codes_are_one_use_and_still_require_password(account):
    _, recovery, _ = enroll(account)
    account.cookies.clear()
    assert account.post('/api/auth/verify', headers=ORIGIN, json={'code': recovery[0], 'recovery': True}).status_code == 401
    assert login(account).status_code == 200
    assert account.post('/api/auth/verify', headers=ORIGIN, json={'code': recovery[0], 'recovery': True}).status_code == 200
    account.cookies.clear()
    assert login(account).status_code == 200
    assert account.post('/api/auth/verify', headers=ORIGIN, json={'code': recovery[0], 'recovery': True}).status_code == 401
    with account.factory() as session:
        assert len(session.scalar(select(AuthUser)).recovery_hashes) == 9


def test_mutations_require_csrf_and_same_origin(account):
    enroll(account)
    assert account.get('/api/assets').status_code == 200
    assert account.post('/api/assess/AS-SUPPORT', headers=ORIGIN, json={}).status_code == 403
    assert account.post('/api/assess/AS-SUPPORT', headers={**csrf(account), 'Origin': 'https://attacker.test'}, json={}).status_code == 403
    assert account.post('/api/assess/AS-SUPPORT', headers=csrf(account), json={}).status_code == 200
    assert account.post('/api/auth/logout', headers=ORIGIN, json={}).status_code == 403
    assert account.get('/api/session').status_code == 200


def test_logout_revokes_the_server_session(account):
    enroll(account)
    old = account.cookies.get(auth.SESSION_COOKIE)
    assert account.post('/api/auth/logout', headers=csrf(account), json={}).status_code == 200
    account.cookies.set(auth.SESSION_COOKIE, old)
    assert account.get('/api/session').status_code == 401
    with account.factory() as session:
        assert session.scalar(select(AuthSession)) is None


def test_expired_flow_cannot_be_used(account):
    secret, _, _ = enroll(account)
    account.cookies.clear()
    assert login(account).status_code == 200
    account.clock['now'] += auth.FLOW_SECONDS + 1
    assert account.post('/api/auth/verify', headers=ORIGIN, json={'code': code(account, secret)}).status_code == 401
    assert auth.SESSION_COOKIE not in account.cookies


def test_five_failed_codes_exhaust_challenge_including_non_ascii_input(account):
    secret, _, _ = enroll(account)
    account.cookies.clear()
    assert login(account).status_code == 200
    for _ in range(5):
        assert account.post('/api/auth/verify', headers=ORIGIN, json={'code': '１２３４５６'}).status_code == 401
    assert account.post('/api/auth/verify', headers=ORIGIN, json={'code': code(account, secret)}).status_code == 401
    with account.factory() as session:
        assert session.scalar(select(AuthChallenge)).attempts == 5


def test_invalid_password_rate_limit_persists_across_failures(account):
    for _ in range(10):
        assert login(account).status_code == 401
    response = login(account)
    assert response.status_code == 429
    assert response.headers['retry-after'] == '900'
    with account.factory() as session:
        assert session.get(AuthThrottle, 'account:' + auth.hashed(EMAIL)).count == 10
    account.clock['now'] += 901
    assert login(account).status_code == 401


def test_unknown_and_incorrect_credentials_have_same_response(account):
    enroll(account)
    account.cookies.clear()
    known = login(account, password='wrong password')
    unknown = login(account, email='nobody@example.test')
    assert known.status_code == unknown.status_code == 401
    assert known.json() == unknown.json()


def test_hostile_or_missing_origin_cannot_start_login(account):
    data = {'email': EMAIL, 'password': PASSWORD}
    assert account.post('/api/auth/login', json=data).status_code == 403
    assert account.post('/api/auth/login', headers={'Origin': 'https://attacker.test'}, json=data).status_code == 403


def test_disabling_account_invalidates_sessions(account):
    enroll(account)
    with account.factory.begin() as session:
        session.scalar(select(AuthUser)).enabled = False
    assert account.get('/api/assets').status_code == 401


def test_challenge_cannot_survive_password_reset(account):
    secret, _, _ = enroll(account)
    account.cookies.clear()
    assert login(account).status_code == 200
    with account.factory.begin() as session:
        session.scalar(select(AuthUser)).password_hash = auth.passwords.hash('different valid passphrase')
    assert account.post('/api/auth/verify', headers=ORIGIN, json={'code': code(account, secret)}).status_code == 401


def test_database_role_changes_take_effect_on_existing_session(account):
    enroll(account)
    with account.factory.begin() as session:
        session.scalar(select(AuthUser)).role = 'AUDITOR'
    assert account.get('/api/session').json()['role'] == 'AUDITOR'
    assert account.post('/api/assess/AS-SUPPORT', headers=csrf(account), json={}).status_code == 403


def test_https_session_cookies_have_secure_flag(account, monkeypatch):
    account.base_url = 'https://testserver'
    monkeypatch.setattr(config, 'AUTH_ALLOWED_ORIGINS', {'https://testserver'})
    monkeypatch.setattr(config, 'AUTH_COOKIE_SECURE', True)
    token = invite(account)
    origin = {'Origin': 'https://testserver'}
    setup = account.post('/api/auth/enroll/start', headers=origin,
                         json={'email': EMAIL, 'password': PASSWORD, 'invitation': token})
    assert setup.status_code == 200
    result = account.post('/api/auth/enroll/confirm', headers=origin,
                          json={'code': code(account, setup.json()['secret'])})
    assert result.status_code == 200
    cookie = next(c for c in result.headers.get_list('set-cookie') if c.startswith(auth.SESSION_COOKIE + '='))
    assert 'Secure' in cookie and 'HttpOnly' in cookie
    assert account.get('/api/session').status_code == 200


def test_local_admin_invitation_and_revocation_cli(account):
    import os
    import subprocess
    import sys
    from pathlib import Path
    root = Path(__file__).resolve().parents[2]
    env = {**os.environ, 'DATABASE_URL': str(account.factory.kw['bind'].url),
           'GOVERNSIM_AUTH_KEY': config.AUTH_KEY}
    result = subprocess.run([sys.executable, 'scripts/manage_users.py', 'invite', '--email', EMAIL, '--role', 'ADMIN'],
                            cwd=root, env=env, capture_output=True, text=True)
    assert result.returncode == 0
    token = result.stdout.split('Invitation code: ')[1].splitlines()[0]
    setup = start(account, token)
    assert setup.status_code == 200
    confirmed = account.post('/api/auth/enroll/confirm', headers=ORIGIN,
                             json={'code': code(account, setup.json()['secret'])})
    assert confirmed.status_code == 200
    assert account.get('/api/session').json()['role'] == 'ADMIN'
    result = subprocess.run([sys.executable, 'scripts/manage_users.py', 'revoke', '--email', EMAIL],
                            cwd=root, env=env, capture_output=True, text=True)
    assert result.returncode == 0
    assert account.get('/api/session').status_code == 401


def test_local_reset_requires_confirmation_and_revokes_every_session(account):
    import os
    import subprocess
    import sys
    from pathlib import Path
    enroll(account)
    root = Path(__file__).resolve().parents[2]
    env = {**os.environ, 'DATABASE_URL': str(account.factory.kw['bind'].url), 'GOVERNSIM_AUTH_KEY': config.AUTH_KEY}
    command = [sys.executable, 'scripts/manage_users.py', 'reset', '--email', EMAIL]
    cancelled = subprocess.run(command, input='NO\n', cwd=root, env=env, capture_output=True, text=True)
    assert cancelled.returncode != 0
    assert account.get('/api/session').status_code == 200
    result = subprocess.run(command, input='RESET\n', cwd=root, env=env, capture_output=True, text=True)
    assert result.returncode == 0
    assert account.get('/api/session').status_code == 401
    with account.factory() as session:
        assert session.scalar(select(AuthUser)).password_hash is None
        assert session.scalar(select(AuthSession)) is None
        assert session.scalar(select(AuthInvitation)) is not None


def test_blank_passphrase_is_rejected(account):
    assert start(account, password=' ' * 20).status_code == 422


def test_missing_encryption_key_fails_closed_during_enrollment(account, monkeypatch):
    monkeypatch.setattr(config, 'AUTH_KEY', '')
    token = invite(account)
    result = start(account, token)
    assert result.status_code == 503
    assert auth.SESSION_COOKIE not in account.cookies
    with account.factory() as session:
        assert session.scalar(select(AuthUser)).password_hash is None


def test_unknown_session_and_wrong_csrf_do_not_authorize_actions(account):
    enroll(account)
    assert account.post('/api/assess/AS-SUPPORT', headers={**ORIGIN, 'X-CSRF-Token': 'not-the-session-csrf'}, json={}).status_code == 403
    account.cookies.clear()
    account.cookies.set(auth.SESSION_COOKIE, secrets.token_urlsafe(32))
    assert account.get('/api/assets').status_code == 401


def test_concurrent_totp_verification_can_succeed_only_once(account):
    from concurrent.futures import ThreadPoolExecutor
    from fastapi.testclient import TestClient
    from app.main import app
    secret, _, _ = enroll(account)
    account.cookies.clear()
    assert login(account).status_code == 200
    flow_cookie = account.cookies.get(auth.FLOW_COOKIE)
    fresh = code(account, secret)
    first, second = TestClient(app), TestClient(app)
    def verify(other):
        try:
            return other.post('/api/auth/verify', headers={**ORIGIN, 'Cookie': f'{auth.FLOW_COOKIE}={flow_cookie}'}, json={'code': fresh}).status_code
        finally:
            other.close()
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(verify, [first, second])) == [200, 401]


def test_authentication_events_do_not_log_secrets(account):
    from app.audit import events
    secret, recovery, _ = enroll(account)
    with account.factory() as session:
        text = json.dumps(events(session))
    assert PASSWORD not in text
    assert secret not in text
    assert account.cookies.get(auth.SESSION_COOKIE) not in text
    assert all(c not in text for c in recovery)

# Email setup and password lifecycle reuse the same real API/database boundary.
@pytest.fixture
def email_account(account, monkeypatch):
    from app import mailer
    for key, value in {'SMTP_HOST': 'smtp.example.test', 'SMTP_PORT': 465, 'SMTP_SECURITY': 'ssl',
                       'SMTP_USERNAME': 'sender@example.test', 'SMTP_PASSWORD': 'test-sender-password',
                       'SMTP_FROM': 'sender@example.test'}.items():
        monkeypatch.setattr(config, key, value)
    account.outbox = []
    def delivery(recipient, subject, body, **kwargs):
        account.outbox.append({'recipient': recipient, 'subject': subject, 'body': body})
    monkeypatch.setattr(mailer, 'send_message', delivery)
    return account


def request_mail(client, purpose='signup', email=EMAIL):
    return client.post('/api/auth/email/request', headers=ORIGIN, json={'email': email, 'purpose': purpose})


def mail_code(client):
    import re
    return re.search(r'\n([0-9]{6})\n', client.outbox[-1]['body']).group(1)


def email_password(client, path='/email/enroll', password='a different private passphrase', code_value=None, confirmation=None):
    return client.post('/api/auth' + path, headers=ORIGIN, json={
        'code': code_value or mail_code(client), 'password': password,
        'password_confirm': password if confirmation is None else confirmation})


def test_email_setup_sends_code_then_requires_confirmation_and_mfa(email_account):
    invite(email_account, role='ADMIN')
    requested = request_mail(email_account)
    assert requested.status_code == 200
    assert email_account.outbox[-1]['recipient'] == EMAIL
    assert '5 minutes' in email_account.outbox[-1]['body']
    raw = mail_code(email_account)
    assert raw not in requested.text
    assert email_account.get('/api/assets').status_code == 401
    mismatch = email_password(email_account, confirmation='does not match this password')
    assert mismatch.status_code == 422
    assert 'does not match this password' not in mismatch.text
    setup = email_password(email_account)
    assert setup.status_code == 200
    assert email_account.get('/api/assets').status_code == 401
    assert email_password(email_account).status_code == 401
    confirmed = email_account.post('/api/auth/enroll/confirm', headers=ORIGIN,
                                   json={'code': code(email_account, setup.json()['secret'])})
    assert confirmed.status_code == 200
    assert email_account.get('/api/session').json()['role'] == 'ADMIN'
    with email_account.factory() as session:
        assert session.scalar(select(AuthInvitation)) is None


def test_email_codes_are_keyed_and_not_in_database_or_audit(email_account):
    from app.audit import events
    invite(email_account)
    request_mail(email_account)
    raw = mail_code(email_account)
    with email_account.factory() as session:
        challenge = session.scalar(select(AuthChallenge))
        assert len(challenge.payload['code_hash']) == 64
        assert challenge.payload['code_hash'] != auth.hashed(raw)
        assert raw not in json.dumps(challenge.payload)
        assert raw not in json.dumps(events(session))


@pytest.mark.parametrize('situation', ['unknown', 'disabled', 'no_approval', 'expired_approval', 'already_enrolled'])
def test_only_approved_pending_accounts_receive_signup_email(email_account, situation):
    if situation != 'unknown':
        invite(email_account, seconds=-1 if situation == 'expired_approval' else 300)
        if situation == 'already_enrolled':
            enroll(email_account)
        elif situation in ('disabled', 'no_approval'):
            from sqlalchemy import delete
            with email_account.factory.begin() as session:
                if situation == 'disabled':
                    session.scalar(select(AuthUser)).enabled = False
                else:
                    session.execute(delete(AuthInvitation))
    response = request_mail(email_account)
    assert response.status_code == 200
    assert response.json()['message'].startswith('If this email')
    assert not email_account.outbox


def test_email_request_requires_trusted_origin_and_no_client_roles(email_account):
    invite(email_account)
    payload = {'email': EMAIL, 'purpose': 'signup'}
    assert email_account.post('/api/auth/email/request', json=payload).status_code == 403
    assert email_account.post('/api/auth/email/request', headers={**ORIGIN, 'Origin': 'https://evil.test'}, json=payload).status_code == 403
    assert email_account.post('/api/auth/email/request', headers=ORIGIN, json={**payload, 'role': 'ADMIN'}).status_code == 422
    assert not email_account.outbox


def test_resend_has_cooldown_and_invalidates_old_code_and_browser(email_account):
    invite(email_account)
    assert request_mail(email_account).status_code == 200
    old_cookie = email_account.cookies.get(auth.FLOW_COOKIE)
    old_code = mail_code(email_account)
    assert request_mail(email_account).status_code == 429
    email_account.clock['now'] += 61
    assert request_mail(email_account).status_code == 200
    new_cookie = email_account.cookies.get(auth.FLOW_COOKIE)
    assert old_cookie != new_cookie
    with email_account.factory() as session:
        assert session.get(AuthChallenge, auth.hashed(old_cookie)) is None
    fresh = email_account.cookies.get(auth.FLOW_COOKIE)
    email_account.cookies.clear()
    email_account.cookies.set(auth.FLOW_COOKIE, old_cookie)
    assert email_password(email_account, code_value=old_code).status_code == 401
    email_account.cookies.clear()
    email_account.cookies.set(auth.FLOW_COOKIE, fresh)
    assert email_password(email_account).status_code == 200


def test_five_bad_email_codes_exhaust_the_flow(email_account):
    invite(email_account)
    request_mail(email_account)
    wrong = f'{(int(mail_code(email_account)) + 1) % 1_000_000:06d}'
    for _ in range(5):
        assert email_password(email_account, code_value=wrong).status_code == 401
    assert email_password(email_account).status_code == 401


def test_email_code_expires_in_five_minutes(email_account):
    invite(email_account)
    request_mail(email_account)
    email_account.clock['now'] += 301
    assert email_password(email_account).status_code == 401


def test_email_code_is_bound_to_requesting_browser(email_account):
    invite(email_account)
    request_mail(email_account)
    email_account.cookies.clear()
    assert email_password(email_account).status_code == 401


def test_signup_code_cannot_reset_password(email_account):
    invite(email_account)
    request_mail(email_account)
    assert email_password(email_account, path='/password/reset').status_code == 401
    assert email_password(email_account).status_code == 200


def test_missing_email_configuration_is_honest_and_fail_closed(email_account, monkeypatch):
    invite(email_account)
    monkeypatch.setattr(config, 'SMTP_HOST', '')
    result = request_mail(email_account)
    assert result.status_code == 503
    assert 'not configured' in result.json()['detail']
    assert not email_account.outbox
    with email_account.factory() as session:
        assert session.scalar(select(AuthChallenge)) is None


def test_smtp_failure_does_not_issue_a_usable_code(email_account, monkeypatch):
    from app import mailer
    invite(email_account)
    def fail(*args, **kwargs):
        raise mailer.DeliveryUnavailable('secret credential must not be exposed')
    monkeypatch.setattr(mailer, 'send_code', fail)
    result = request_mail(email_account)
    assert result.status_code == 503
    assert 'secret credential' not in result.text
    with email_account.factory() as session:
        assert session.scalar(select(AuthChallenge)) is None


def test_reset_revokes_all_sessions_and_flows_preserves_mfa_and_requires_login(email_account):
    secret, recovery, _ = enroll(email_account)
    old_session = email_account.cookies.get(auth.SESSION_COOKIE)
    login(email_account)
    old_flow = email_account.cookies.get(auth.FLOW_COOKIE)
    with email_account.factory() as session:
        encrypted_secret = session.scalar(select(AuthUser)).totp_encrypted
    assert request_mail(email_account, 'reset').status_code == 200
    reset_cookie = email_account.cookies.get(auth.FLOW_COOKIE)
    new_password = 'my newly reset private passphrase'
    result = email_password(email_account, '/password/reset', new_password)
    assert result.status_code == 200
    assert result.json()['sign_in_required']
    assert auth.SESSION_COOKIE not in email_account.cookies
    assert email_account.get('/api/assets').status_code == 401
    with email_account.factory() as session:
        user = session.scalar(select(AuthUser))
        assert user.totp_encrypted == encrypted_secret
        assert len(user.recovery_hashes) == len(recovery)
        assert auth.passwords.verify(new_password, user.password_hash)
        assert session.scalar(select(AuthSession)) is None
        assert session.scalar(select(AuthChallenge)) is None
    email_account.cookies.set(auth.SESSION_COOKIE, old_session)
    assert email_account.get('/api/assets').status_code == 401
    email_account.cookies.clear()
    email_account.cookies.set(auth.FLOW_COOKIE, old_flow)
    assert email_account.post('/api/auth/verify', headers=ORIGIN, json={'code': code(email_account, secret)}).status_code == 401
    email_account.cookies.clear()
    email_account.cookies.set(auth.FLOW_COOKIE, reset_cookie)
    assert email_password(email_account, '/password/reset', new_password).status_code == 401
    email_account.cookies.clear()
    assert login(email_account).status_code == 401
    assert login(email_account, password=new_password).status_code == 200
    assert email_account.get('/api/assets').status_code == 401
    assert email_account.post('/api/auth/verify', headers=ORIGIN, json={'code': code(email_account, secret)}).status_code == 200


@pytest.mark.parametrize('kind', ['unknown', 'unenrolled', 'disabled'])
def test_reset_request_does_not_reveal_missing_or_disabled_accounts(email_account, kind):
    if kind == 'unenrolled':
        invite(email_account)
    elif kind == 'disabled':
        enroll(email_account)
        with email_account.factory.begin() as session:
            session.scalar(select(AuthUser)).enabled = False
    assert request_mail(email_account, 'reset').status_code == 200
    assert not email_account.outbox


def test_reset_code_cannot_survive_another_password_change(email_account):
    enroll(email_account)
    request_mail(email_account, 'reset')
    with email_account.factory.begin() as session:
        session.scalar(select(AuthUser)).password_hash = auth.passwords.hash('another newly chosen passphrase')
    assert email_password(email_account, '/password/reset').status_code == 401


def test_email_codes_are_limited_per_account_and_ip(email_account):
    invite(email_account)
    for _ in range(5):
        assert request_mail(email_account).status_code == 200
        email_account.clock['now'] += 61
    assert request_mail(email_account).status_code == 429
    assert len(email_account.outbox) == 5


def test_change_password_requires_session_csrf_origin_and_current_password(email_account):
    enroll(email_account)
    new = 'my changed long private passphrase'
    data = {'current_password': PASSWORD, 'password': new, 'password_confirm': new}
    assert email_account.post('/api/auth/password/change', headers=ORIGIN, json=data).status_code == 403
    assert email_account.post('/api/auth/password/change', headers={**csrf(email_account), 'Origin': 'https://evil.test'}, json=data).status_code == 403
    assert email_account.post('/api/auth/password/change', headers=csrf(email_account), json={**data, 'current_password': 'wrong'}).status_code == 400
    assert email_account.get('/api/session').status_code == 200
    email_account.cookies.clear()
    assert email_account.post('/api/auth/password/change', headers=ORIGIN, json=data).status_code == 401


def test_change_password_revokes_sessions_and_keeps_authenticator(email_account):
    secret, _, _ = enroll(email_account)
    old = email_account.cookies.get(auth.SESSION_COOKIE)
    new = 'my changed long private passphrase'
    data = {'current_password': PASSWORD, 'password': new, 'password_confirm': new}
    result = email_account.post('/api/auth/password/change', headers=csrf(email_account), json=data)
    assert result.status_code == 200
    assert email_account.get('/api/assets').status_code == 401
    email_account.cookies.set(auth.SESSION_COOKIE, old)
    assert email_account.get('/api/session').status_code == 401
    email_account.cookies.clear()
    assert login(email_account).status_code == 401
    assert login(email_account, password=new).status_code == 200
    assert email_account.post('/api/auth/verify', headers=ORIGIN, json={'code': code(email_account, secret)}).status_code == 200


def test_password_change_validation_never_echoes_credentials(email_account):
    enroll(email_account)
    new = 'my new long private passphrase'
    result = email_account.post('/api/auth/password/change', headers=csrf(email_account), json={
        'current_password': PASSWORD, 'password': new, 'password_confirm': 'mismatched private passphrase'})
    assert result.status_code == 422
    assert PASSWORD not in result.text and new not in result.text
    assert 'mismatched private passphrase' not in result.text


def test_reset_and_change_reject_reusing_current_password(email_account):
    enroll(email_account)
    data = {'current_password': PASSWORD, 'password': PASSWORD, 'password_confirm': PASSWORD}
    assert email_account.post('/api/auth/password/change', headers=csrf(email_account), json=data).status_code == 400
    request_mail(email_account, 'reset')
    assert email_password(email_account, '/password/reset', PASSWORD).status_code == 400
