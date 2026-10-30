"""Generate local-only named credentials without any third-party dependency."""
from pathlib import Path
import hashlib
import json
import os
import secrets

root = Path(__file__).resolve().parents[1]
env = root / '.env'
keys_file = root / '.local-keys.txt'
if env.exists():
    print('.env already exists; existing configuration is preserved.')
else:
    principals = [('admin-local','ADMIN'),('owner-local','AI_OWNER'),('reviewer-local','COMPLIANCE_REVIEWER'),('risk-officer-local','RISK_OFFICER'),('auditor-local','AUDITOR')]
    mapping = {}
    key_lines = ['GovernSim local access tokens. Keep private; never commit or share this file.', '']
    for name, role in principals:
        token = secrets.token_urlsafe(36)
        mapping[hashlib.sha256(token.encode()).hexdigest()] = {'name':name,'role':role}
        key_lines.extend([f'{role} ({name})', token, ''])
    password = secrets.token_hex(24)
    with env.open('x', encoding='utf-8') as handle:
        handle.write(f'# Generated locally. Do not commit.\nGOVERNSIM_API_KEYS=\'{json.dumps(mapping, separators=(",", ":"))}\'\nPOSTGRES_PASSWORD={password}\nSEED_DEMO=true\nLLM_PROVIDER=offline\n# DATABASE_URL is set by Docker Compose; omitted for local SQLite.\n')
    with keys_file.open('x', encoding='utf-8') as handle:
        handle.write('\n'.join(key_lines))
    for path in (env, keys_file):
        os.chmod(path, 0o600)
    print('Local configuration created. Website accounts use password + authenticator verification.')

# Add the MFA encryption key on upgrades without replacing any existing values.
# secrets.token_bytes + URL-safe base64 is a Fernet key; no dependency is required here.
import base64
contents = env.read_text(encoding='utf-8')
if not any(line.strip().startswith('GOVERNSIM_AUTH_KEY=') for line in contents.splitlines()):
    auth_key = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode('ascii')
    with env.open('a', encoding='utf-8') as handle:
        handle.write(f'\n# Persistent account MFA encryption key. Back up with the database.\nGOVERNSIM_AUTH_KEY={auth_key}\n')
    os.chmod(env, 0o600)
    print('Account encryption key added. Existing configuration and registry records were preserved.')
print('Website access: create an invitation with scripts/manage_users.py, then enroll password + authenticator 2FA.')
print('Legacy API tokens are disabled by default and are not a website sign-in method.')
