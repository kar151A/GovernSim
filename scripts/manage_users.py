"""Local administrator account invitations, revocation and lost-factor recovery.

Run from the project root. Invitations are displayed locally, never sent by email.
The website does not provide public registration or let callers choose a role.
"""
import argparse
from pathlib import Path
import re
import secrets
import sys
import time
root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / 'backend' if (root / 'backend').exists() else root))
from sqlalchemy import delete, select
from app import config
from app.auth import ROLES, hashed
from app.audit import append_event, uid
from app.db import (init_db, SessionLocal, AuthUser, AuthInvitation, AuthSession, AuthChallenge)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['invite', 'revoke', 'reset'])
    parser.add_argument('--email', required=True)
    parser.add_argument('--role', choices=sorted(ROLES), default='AI_OWNER', help='Only used when inviting a new account.')
    args = parser.parse_args()
    email = args.email.strip().casefold()
    if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email) or len(email) > 254:
        parser.error('Provide a valid email identifier.')
    if not config.AUTH_KEY:
        parser.error('Run scripts/bootstrap.py before creating accounts.')
    init_db()
    invitation = None
    with SessionLocal.begin() as session:
        user = session.scalar(select(AuthUser).where(AuthUser.email == email).with_for_update())
        if args.action == 'invite':
            if user and user.password_hash:
                parser.error('Account already enrolled. Use reset for lost factors or revoke to disable access.')
            if not user:
                user = AuthUser(id=uid('USR'), email=email, role=args.role, enabled=True,
                                last_totp_step=-1, recovery_hashes=[])
                session.add(user)
                session.flush()
            elif not user.enabled:
                parser.error('Account is disabled. Use reset to re-enable it deliberately.')
        elif not user:
            parser.error('Account not found.')
        elif args.action == 'reset':
            # Local database access is the administrative authority; no remote reset endpoint.
            answer = input(f'Revoke all sessions and reset password/2FA for {email}? Type RESET: ')
            if answer != 'RESET':
                parser.error('Reset cancelled.')
            user.enabled = True
            user.password_hash = user.totp_encrypted = None
            user.last_totp_step, user.recovery_hashes = -1, []
        else:
            user.enabled = False
        for model in (AuthSession, AuthChallenge, AuthInvitation):
            session.execute(delete(model).where(model.user_id == user.id))
        if args.action in ('invite', 'reset'):
            invitation = secrets.token_urlsafe(32)
            session.add(AuthInvitation(token_hash=hashed(invitation), user_id=user.id, expires_at=time.time() + 86400))
        append_event(session, 'ACCOUNT_' + args.action.upper(), 'local-administrator', {'user_id': user.id, 'email': email, 'role': user.role})
    if invitation:
        print('Account invitation created. Open GovernSim, choose Set up invited account, and enter:')
        print(f'Email: {email}\nInvitation code: {invitation}\nRole: {user.role}\nExpires in 24 hours. Keep the code private.')
    else:
        print('Account disabled; existing sessions, challenges and invitations were revoked.')


if __name__ == '__main__':
    main()
