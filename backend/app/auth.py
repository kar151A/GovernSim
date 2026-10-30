"""Invite-only password + TOTP accounts, opaque sessions and revocable recovery codes.

No application session is issued until both factors have been verified. Session,
invitation and challenge tokens are random and stored only as SHA-256 digests.
"""
import base64
import hashlib
import hmac
import io
import math
import re
import secrets
import time
from typing import Annotated, Literal

from cryptography.fernet import Fernet
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import ConfigDict, Field, field_validator
from pwdlib import PasswordHash
import pyotp
import qrcode
from qrcode.image.svg import SvgPathImage
from sqlalchemy import delete, select

from . import config, db, mailer
from .audit import append_event, uid
from .locking import transaction_lock
from .schemas import StrictModel

router = APIRouter(prefix='/api/auth', tags=['Account authentication'])
passwords = PasswordHash.recommended()
DUMMY_HASH = passwords.hash(secrets.token_urlsafe(32))
SESSION_COOKIE = 'governsim_session'
CSRF_COOKIE = 'governsim_csrf'
FLOW_COOKIE = 'governsim_flow'
SESSION_SECONDS = 8 * 3600
FLOW_SECONDS = 300
ROLES = {'AI_OWNER', 'RISK_OFFICER', 'COMPLIANCE_REVIEWER', 'AUDITOR', 'ADMIN'}


def hashed(value: str) -> str:
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def cipher() -> Fernet:
    if not config.AUTH_KEY:
        raise HTTPException(503, 'Account setup is unavailable. Run scripts/bootstrap.py and restart the server.')
    return Fernet(config.AUTH_KEY.encode('ascii'))


class LoginInput(StrictModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=False)
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=128)

    @field_validator('email')
    @classmethod
    def email_identifier(cls, value):
        value = value.strip().casefold()
        if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', value):
            raise ValueError('Enter a valid email address')
        return value

    @field_validator('password', mode='before')
    @classmethod
    def preserve_password(cls, value):
        return value


class EnrollmentInput(LoginInput):
    invitation: str = Field(min_length=32, max_length=128)

    @field_validator('password')
    @classmethod
    def strong_password(cls, value):
        if len(value.strip()) < 15:
            raise ValueError('Use a password or passphrase with at least 15 characters')
        return value


class CodeInput(StrictModel):
    code: str = Field(min_length=6, max_length=32)
    recovery: bool = False


class EmailRequest(StrictModel):
    email: str = Field(min_length=3, max_length=254)
    purpose: Literal['signup', 'reset']

    @field_validator('email')
    @classmethod
    def email_identifier(cls, value):
        return LoginInput.email_identifier(value)


class NewPassword(StrictModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=False)
    password: str = Field(min_length=15, max_length=128)
    password_confirm: str = Field(min_length=1, max_length=128)

    @field_validator('password')
    @classmethod
    def strong_password(cls, value):
        return EnrollmentInput.strong_password(value)

    @field_validator('password_confirm')
    @classmethod
    def matching_password(cls, value, info):
        if value != info.data.get('password'):
            raise ValueError('Passwords do not match')
        return value


class EmailPassword(NewPassword):
    code: str = Field(min_length=6, max_length=6, pattern=r'^[0-9]{6}$')


class ChangePassword(NewPassword):
    current_password: str = Field(min_length=1, max_length=128)


def auth_db():
    # Expected authentication failures must retain attempt counters and consumed flows.
    with transaction_lock:
        with db.SessionLocal() as session:
            try:
                yield session
                session.commit()
            except HTTPException:
                session.commit()
                raise
            except Exception:
                session.rollback()
                raise


DB = Annotated[object, Depends(auth_db)]


def require_origin(request: Request):
    if request.headers.get('origin') not in config.AUTH_ALLOWED_ORIGINS:
        raise HTTPException(403, 'Request origin is not allowed')


def limit(session, key: str, maximum: int, window: int = 900):
    current = time.time()
    record = session.scalar(select(db.AuthThrottle).where(db.AuthThrottle.key == key).with_for_update())
    if not record:
        record = db.AuthThrottle(key=key, count=0, resets_at=current + window)
        session.add(record)
    if record.resets_at <= current:
        record.count, record.resets_at = 0, current + window
    if record.count >= maximum:
        retry = max(1, math.ceil(record.resets_at - current))
        raise HTTPException(429, f'Too many attempts. Try again in {retry} seconds.', headers={'Retry-After': str(retry)})
    record.count += 1
    session.flush()


def attempt_budget(session, request, identifier: str):
    # Do not trust caller-supplied X-Forwarded-For. Configure a trusted proxy separately.
    address = request.client.host if request.client else 'unknown'
    limit(session, 'ip:' + hashed(address), 60)
    limit(session, 'account:' + hashed(identifier), 10)


def cookie(response, name, value, *, path='/', seconds=SESSION_SECONDS, http_only=True):
    response.set_cookie(name, value, httponly=http_only, secure=config.AUTH_COOKIE_SECURE,
                        samesite='strict', path=path, max_age=seconds)


def clear_flow(response):
    response.delete_cookie(FLOW_COOKIE, path='/api/auth', secure=config.AUTH_COOKIE_SECURE,
                           httponly=True, samesite='strict')


def create_flow(session, response, user_id, purpose, payload=None):
    session.execute(delete(db.AuthChallenge).where(db.AuthChallenge.expires_at <= time.time()))
    token = secrets.token_urlsafe(32)
    record = db.AuthChallenge(token_hash=hashed(token), user_id=user_id, purpose=purpose,
                              expires_at=time.time() + FLOW_SECONDS, attempts=0, payload=payload or {})
    session.add(record)
    cookie(response, FLOW_COOKIE, token, path='/api/auth', seconds=FLOW_SECONDS)
    return record


def flow(session, request, purpose):
    token = request.cookies.get(FLOW_COOKIE, '')
    record = session.scalar(select(db.AuthChallenge).where(db.AuthChallenge.token_hash == hashed(token)).with_for_update())
    if not record or record.purpose != purpose or record.expires_at <= time.time() or record.attempts >= 5:
        raise HTTPException(401, 'Verification expired or unavailable. Start again.')
    record.attempts += 1
    user = session.scalar(select(db.AuthUser).where(db.AuthUser.id == record.user_id).with_for_update())
    if not user or not user.enabled:
        raise HTTPException(401, 'Verification expired or unavailable. Start again.')
    return record, user


def consume_totp(user, secret, code):
    if not re.fullmatch(r'[0-9]{6}', code):
        return False
    totp = pyotp.TOTP(secret)
    current = int(time.time()) // 30
    # Small clock-skew allowance. An accepted time-step can never be used again.
    for step in (current, current - 1, current + 1):
        if step > user.last_totp_step and hmac.compare_digest(totp.at(step * 30), code):
            user.last_totp_step = step
            return True
    return False


def identity(user):
    # The immutable email identifier is also the named principal in governance records.
    return {'name': user.email, 'email': user.email, 'role': user.role}


def issue_session(session, response, user):
    session.execute(delete(db.AuthSession).where(db.AuthSession.expires_at <= time.time()))
    token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    session.add(db.AuthSession(token_hash=hashed(token), user_id=user.id, csrf_hash=hashed(csrf),
                              expires_at=time.time() + SESSION_SECONDS))
    cookie(response, SESSION_COOKIE, token)
    cookie(response, CSRF_COOKIE, csrf, http_only=False)
    clear_flow(response)


def account_principal(request: Request):
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return None
    with db.SessionLocal() as session:
        saved = session.get(db.AuthSession, hashed(token))
        if not saved or saved.expires_at <= time.time():
            raise HTTPException(401, 'Your session expired. Sign in again.')
        user = session.get(db.AuthUser, saved.user_id)
        if not user or not user.enabled or not user.password_hash or not user.totp_encrypted:
            raise HTTPException(401, 'Your session is no longer available. Sign in again.')
        if request.method not in ('GET', 'HEAD', 'OPTIONS'):
            require_origin(request)
            csrf = request.headers.get('x-csrf-token', '')
            if not csrf or not hmac.compare_digest(hashed(csrf), saved.csrf_hash):
                raise HTTPException(403, 'Request verification failed. Refresh the page and try again.')
        return identity(user)


def email_digest(challenge, code):
    # Six-digit codes need a server-keyed verifier, not a brute-forceable plain hash.
    context = f'{challenge.token_hash}:{challenge.user_id}:{challenge.purpose}:{code}'
    return hmac.new(config.AUTH_KEY.encode(), context.encode(), hashlib.sha256).hexdigest()


def clear_session_cookies(response):
    response.delete_cookie(SESSION_COOKIE, path='/', secure=config.AUTH_COOKIE_SECURE,
                           httponly=True, samesite='strict')
    response.delete_cookie(CSRF_COOKIE, path='/', secure=config.AUTH_COOKIE_SECURE, samesite='strict')
    clear_flow(response)


def revoke_credentials_sessions(session, user):
    for model in (db.AuthSession, db.AuthChallenge, db.AuthInvitation):
        session.execute(delete(model).where(model.user_id == user.id))


def enrollment_result(session, response, user, password):
    secret = pyotp.random_base32()
    encryption = cipher()
    create_flow(session, response, user.id, 'enroll', {'password_hash': passwords.hash(password),
                'totp_encrypted': encryption.encrypt(secret.encode()).decode()})
    uri = pyotp.TOTP(secret).provisioning_uri(name=user.email, issuer_name='GovernSim')
    image = qrcode.make(uri, image_factory=SvgPathImage)
    output = io.BytesIO()
    image.save(output)
    return {'secret': secret, 'qr_image': 'data:image/svg+xml;base64,' + base64.b64encode(output.getvalue()).decode(),
            'expires_in': FLOW_SECONDS}


@router.post('/email/request')
def request_email(value: EmailRequest, request: Request, response: Response, session: DB):
    require_origin(request)
    cipher()
    try:
        mailer.settings()
    except mailer.DeliveryUnavailable:
        raise HTTPException(503, 'Email delivery is not configured. Ask your administrator to run scripts/configure_email.py.') from None
    address = request.client.host if request.client else 'unknown'
    limit(session, 'mail-ip:' + hashed(address), 20)
    limit(session, 'mail-account:' + hashed(value.email), 5)
    limit(session, 'mail-cooldown:' + hashed(value.email), 1, window=60)
    clear_flow(response)
    user = session.scalar(select(db.AuthUser).where(db.AuthUser.email == value.email).with_for_update())
    invitation = session.scalar(select(db.AuthInvitation).where(
        db.AuthInvitation.user_id == user.id, db.AuthInvitation.expires_at > time.time())) if user else None
    eligible = user and user.enabled and ((value.purpose == 'signup' and not user.password_hash and invitation)
                or (value.purpose == 'reset' and user.password_hash and user.totp_encrypted))
    if eligible:
        purpose = 'mail-' + value.purpose
        # Resends invalidate every older code for this account and purpose.
        session.execute(delete(db.AuthChallenge).where(db.AuthChallenge.user_id == user.id,
                                                      db.AuthChallenge.purpose == purpose))
        challenge = create_flow(session, response, user.id, purpose)
        code = f'{secrets.randbelow(1_000_000):06d}'
        challenge.payload = {'code_hash': email_digest(challenge, code),
                             'credential_hash': hashed(user.password_hash or ''),
                             'approval_hash': invitation.token_hash if value.purpose == 'signup' else ''}
        session.flush()
        try:
            mailer.send_code(user.email, code, value.purpose)
        except mailer.DeliveryUnavailable:
            session.delete(challenge)
            raise HTTPException(503, 'The email could not be sent. Ask your administrator to check the email sender configuration.') from None
    return {'message': 'If this email is approved for this action, a code has been sent. Check your inbox and spam folder.',
            'expires_in': FLOW_SECONDS, 'resend_after': 60}


def verified_email_flow(session, request, purpose, code):
    challenge, user = flow(session, request, 'mail-' + purpose)
    expected = challenge.payload.get('code_hash', '')
    if (not hmac.compare_digest(email_digest(challenge, code), expected)
            or challenge.payload.get('credential_hash') != hashed(user.password_hash or '')):
        raise HTTPException(401, 'The email code is invalid, expired or already used. Request a new code.')
    return challenge, user


@router.post('/email/enroll')
def enroll_from_email(value: EmailPassword, request: Request, response: Response, session: DB):
    require_origin(request)
    challenge, user = verified_email_flow(session, request, 'signup', value.code)
    invitation = session.get(db.AuthInvitation, challenge.payload.get('approval_hash', ''))
    if user.password_hash or not invitation or invitation.expires_at <= time.time() or invitation.user_id != user.id:
        raise HTTPException(401, 'Account approval expired. Ask your administrator to approve your email again.')
    session.delete(challenge)
    result = enrollment_result(session, response, user, value.password)
    append_event(session, 'ACCOUNT_EMAIL_VERIFIED', user.email, {'user_id': user.id})
    return result


@router.post('/password/reset')
def reset_password(value: EmailPassword, request: Request, response: Response, session: DB):
    require_origin(request)
    _, user = verified_email_flow(session, request, 'reset', value.code)
    if not user.password_hash or not user.totp_encrypted:
        raise HTTPException(401, 'Request a new password reset code.')
    if passwords.verify(value.password, user.password_hash):
        raise HTTPException(400, 'Choose a different password from your current password.')
    user.password_hash = passwords.hash(value.password)
    revoke_credentials_sessions(session, user)
    clear_session_cookies(response)
    append_event(session, 'ACCOUNT_PASSWORD_RESET', user.email, {'user_id': user.id})
    # Email recovery changes the password only; it cannot remove or bypass MFA.
    return {'password_changed': True, 'sign_in_required': True}


@router.post('/password/change')
def change_password(value: ChangePassword, request: Request, response: Response, session: DB):
    require_origin(request)
    principal = account_principal(request)
    if not principal:
        raise HTTPException(401, 'Sign in before changing your password.')
    attempt_budget(session, request, principal['email'])
    user = session.scalar(select(db.AuthUser).where(db.AuthUser.email == principal['email']).with_for_update())
    if not user or not user.enabled or not user.password_hash or not user.totp_encrypted:
        raise HTTPException(401, 'Your account is no longer available. Sign in again.')
    if not passwords.verify(value.current_password, user.password_hash):
        raise HTTPException(400, 'Your current password is incorrect.')
    if passwords.verify(value.password, user.password_hash):
        raise HTTPException(400, 'Choose a different password from your current password.')
    user.password_hash = passwords.hash(value.password)
    revoke_credentials_sessions(session, user)
    clear_session_cookies(response)
    append_event(session, 'ACCOUNT_PASSWORD_CHANGED', user.email, {'user_id': user.id})
    return {'password_changed': True, 'sign_in_required': True}


@router.post('/enroll/start')
def enroll_start(value: EnrollmentInput, request: Request, response: Response, session: DB):
    require_origin(request)
    attempt_budget(session, request, value.email)
    invitation = session.scalar(select(db.AuthInvitation).where(db.AuthInvitation.token_hash == hashed(value.invitation)).with_for_update())
    user = session.get(db.AuthUser, invitation.user_id) if invitation else None
    if not invitation or invitation.expires_at <= time.time() or not user or not user.enabled or user.email != value.email or user.password_hash:
        raise HTTPException(401, 'Invitation is invalid or expired. Ask your administrator for a new one.')
    result = enrollment_result(session, response, user, value.password)
    session.delete(invitation)
    return result


@router.post('/enroll/confirm')
def enroll_confirm(value: CodeInput, request: Request, response: Response, session: DB):
    require_origin(request)
    challenge, user = flow(session, request, 'enroll')
    if user.password_hash or value.recovery:
        raise HTTPException(401, 'Start account setup again.')
    secret = cipher().decrypt(challenge.payload['totp_encrypted'].encode()).decode()
    if not consume_totp(user, secret, value.code):
        raise HTTPException(401, 'The code is invalid. Check your authenticator and device time.')
    recovery = [secrets.token_hex(8) for _ in range(10)]
    recovery = ['-'.join(code[i:i+4] for i in range(0,16,4)) for code in recovery]
    user.password_hash = challenge.payload['password_hash']
    user.totp_encrypted = challenge.payload['totp_encrypted']
    user.recovery_hashes = [hashed(code.replace('-', '')) for code in recovery]
    session.execute(delete(db.AuthInvitation).where(db.AuthInvitation.user_id == user.id))
    session.delete(challenge)
    issue_session(session, response, user)
    append_event(session, 'ACCOUNT_ENROLLED', user.email, {'user_id': user.id, 'role': user.role})
    return {'identity': identity(user), 'recovery_codes': recovery}


@router.post('/login')
def login(value: LoginInput, request: Request, response: Response, session: DB):
    require_origin(request)
    attempt_budget(session, request, value.email)
    user = session.scalar(select(db.AuthUser).where(db.AuthUser.email == value.email))
    valid = passwords.verify(value.password, user.password_hash if user and user.password_hash else DUMMY_HASH)
    if not valid or not user or not user.enabled or not user.totp_encrypted:
        raise HTTPException(401, 'Email or password is incorrect.')
    create_flow(session, response, user.id, 'login', {'credential_hash': hashed(user.password_hash)})
    return {'requires_two_factor': True, 'expires_in': FLOW_SECONDS}


@router.post('/verify')
def verify(value: CodeInput, request: Request, response: Response, session: DB):
    require_origin(request)
    challenge, user = flow(session, request, 'login')
    if not user.password_hash or not user.totp_encrypted or challenge.payload.get('credential_hash') != hashed(user.password_hash):
        raise HTTPException(401, 'Start sign-in again.')
    if value.recovery:
        code_hash = hashed(value.code.replace('-', '').replace(' ', '').lower())
        matches = [code for code in user.recovery_hashes if hmac.compare_digest(code, code_hash)]
        valid = bool(matches)
        if valid:
            user.recovery_hashes = [code for code in user.recovery_hashes if code != code_hash]
    else:
        secret = cipher().decrypt(user.totp_encrypted.encode()).decode()
        valid = consume_totp(user, secret, value.code)
    if not valid:
        raise HTTPException(401, 'The verification code is invalid or has already been used.')
    session.delete(challenge)
    issue_session(session, response, user)
    append_event(session, 'ACCOUNT_SIGNED_IN', user.email, {'user_id': user.id, 'recovery_code': value.recovery})
    return {'identity': identity(user)}


@router.post('/logout')
def logout(request: Request, response: Response, session: DB):
    require_origin(request)
    principal = account_principal(request)
    if not principal:
        raise HTTPException(401, 'Sign in first.')
    session.execute(delete(db.AuthSession).where(db.AuthSession.token_hash == hashed(request.cookies.get(SESSION_COOKIE, ''))))
    response.delete_cookie(SESSION_COOKIE, path='/', secure=config.AUTH_COOKIE_SECURE, httponly=True, samesite='strict')
    response.delete_cookie(CSRF_COOKIE, path='/', secure=config.AUTH_COOKIE_SECURE, samesite='strict')
    clear_flow(response)
    append_event(session, 'ACCOUNT_SIGNED_OUT', principal['name'], {})
    return {'signed_out': True}
