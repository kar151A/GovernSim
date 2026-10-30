"""Configure a TLS SMTP sender locally, test delivery, and approve your admin email.

Run bootstrap first. Sender passwords are prompted privately, never command arguments.
"""
import argparse
import getpass
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend' if (ROOT / 'backend').exists() else ROOT))

from dotenv import set_key
from sqlalchemy import select
from app import config, db, mailer


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--admin-email', required=True, help='Your account email; receives the delivery test.')
    args = parser.parse_args()
    email = args.admin_email.strip().casefold()
    if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email) or len(email) > 254:
        parser.error('Enter a valid admin email.')
    if not config.AUTH_KEY:
        parser.error('Run scripts/bootstrap.py first.')
    print('Configure a transactional SMTP sender. Gmail requires an App Password, not your normal password.')
    host = (input('SMTP host [smtp.gmail.com]: ').strip() or 'smtp.gmail.com').casefold()
    security = (input('TLS mode [ssl] (ssl/starttls): ').strip() or 'ssl').casefold()
    try:
        port = int(input(f'Port [{465 if security == "ssl" else 587}]: ').strip() or ('465' if security == 'ssl' else '587'))
    except ValueError:
        parser.error('Port must be a number.')
    username = input(f'Sender SMTP username [{email}]: ').strip() or email
    password = getpass.getpass('Sender SMTP/App Password (hidden): ')
    if host == 'smtp.gmail.com':
        # Google displays App Passwords in groups; copied display spaces are not part of the key.
        password = password.replace(' ', '').strip()
    sender = input(f'From email [{username}]: ').strip() or username
    connection = mailer.Settings(host, port, security, username, password, sender)
    try:
        mailer.send_message(email, 'GovernSim email delivery test',
                            'Your GovernSim email sender is connected. You can now request account verification and password reset codes from the website.\n',
                            connection=connection)
    except mailer.DeliveryUnavailable as error:
        parser.error(f'{error.diagnostic} No settings were saved.')
    path = ROOT / '.env'
    path.touch(mode=0o600, exist_ok=True)
    values = {'HOST': host, 'PORT': str(port), 'SECURITY': security, 'USERNAME': username,
              'PASSWORD': password, 'FROM': sender}
    for key, value in values.items():
        set_key(path, 'GOVERNSIM_SMTP_' + key, value)
    path.chmod(0o600)
    db.init_db()
    with db.SessionLocal() as session:
        user = session.scalar(select(db.AuthUser).where(db.AuthUser.email == email))
        needs_approval = not user or (user.enabled and not user.password_hash)
    if needs_approval:
        result = subprocess.run([sys.executable, str(ROOT / 'scripts/manage_users.py'), 'invite',
                                 '--email', email, '--role', 'ADMIN'], cwd=ROOT, capture_output=True, text=True)
        if result.returncode:
            parser.error('SMTP settings saved, but account approval failed. Run scripts/manage_users.py invite locally.')
        print('Your account email is approved for setup. Existing roles are preserved.')
    elif not user.enabled:
        print('This account is disabled. Ask its administrator to restore access deliberately.')
    print('Delivery test accepted by the SMTP server. Check your inbox, restart GovernSim, then use Send verification code or Forgot password.')


if __name__ == '__main__':
    main()
