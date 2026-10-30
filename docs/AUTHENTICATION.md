# Account login and two-factor verification

The website requires email + password, followed by an authenticator-app code. Email is an account identifier; no email-delivery or mailbox-verification service is configured. Account creation is invite-only and controlled by an administrator with local database access.

## Upgrade your existing Windows checkout

Stop the running server, preserve any local source edits, then run from the project root:

```powershell
git pull --ff-only origin main
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
.\.venv\Scripts\python.exe scripts\bootstrap.py
.\.venv\Scripts\python.exe scripts\manage_users.py invite --email your-email@example.com --role ADMIN
npm.cmd run build --prefix frontend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

Replace the example email with your account identifier. The invitation command displays a private one-use code locally; it does not send email. Existing registry records are preserved. New authentication tables are additive; they do not replace the governance tables.

1. Open `http://localhost:8000` and choose **Set up invited account**.
2. Enter the email and invitation code. Choose a unique password/passphrase of at least 15 characters.
3. Scan the QR code in an authenticator app, or enter the setup key manually.
4. Enter the app's six-digit code. Setup is confirmed only after a valid code.
5. Save the ten recovery codes privately. They are displayed once; each can be used once with your password.
6. Later sign-ins use email, password and an authenticator code. A code already accepted cannot be reused; wait for the next code when signing in again immediately.

Invitation codes expire after 24 hours. Once setup starts, the invitation is consumed and enrollment must finish within 5 minutes. If abandoned or expired, issue a new invitation for the unenrolled account.

Create separate AI_OWNER and COMPLIANCE_REVIEWER accounts to exercise independent review. Do not share one account between submitter and reviewer.

## Docker Compose

Run bootstrap locally, then rebuild/start Compose. Create accounts inside the app container so invitations use the PostgreSQL database:

```powershell
py -3.12 scripts\bootstrap.py
docker compose up --build -d
docker compose exec app python scripts/manage_users.py invite --email your-email@example.com --role ADMIN
```

A plain local invitation command would use the local database; use the container command for Compose. The encryption key is passed through Compose environment configuration, never built into the image.

## Session and secret handling

- Argon2id password hashing uses `pwdlib` and its maintained Argon2 implementation.
- PyOTP verifies six-digit TOTP with a 30-second step and a one-step clock-skew allowance. Accepted time steps are recorded per account to reject replay.
- TOTP secrets must be recoverable for verification, so they are encrypted using Fernet from `cryptography`. The encryption key stays in server configuration, separate from the database.
- Password verification grants only a limited five-minute flow. A full session is created after the second factor succeeds.
- Session tokens, invitations and verification-flow tokens are random; the database holds SHA-256 digests, not the raw tokens.
- Full sessions have an eight-hour absolute lifetime and an HttpOnly, SameSite=Strict cookie. A separate CSRF cookie is readable by the frontend; its hash is bound to the server session.
- Mutating cookie-authenticated requests require an allowed Origin and matching CSRF header. Logout revokes the server-side session, rather than only hiding the UI.
- Login attempts have database-backed 15-minute account and IP budgets. Each verification flow permits five failed codes. This is a single-worker MVP; add ingress abuse protection and validate trusted-proxy/IP handling before scaling.
- Authentication events are recorded without passwords, codes, raw session tokens, invitations, recovery codes or authenticator secrets. Validation responses omit submitted input values.
- The default configuration rejects old bearer tokens. Set `GOVERNSIM_ALLOW_LEGACY_API_KEYS=true` only for intentional legacy automation: that opt-in bypasses MFA and should remain disabled for account-only access.

## Lost phone, disabled account or reset

A saved recovery code can replace the authenticator code after a correct password. It is consumed on successful use. If all factors are lost, an administrator with local database access can run:

```powershell
.\.venv\Scripts\python.exe scripts\manage_users.py reset --email your-email@example.com
```

The command requires typing `RESET`. It revokes sessions, pending flows and old credentials, preserves the principal identifier and role, and issues a new setup invitation. Invite-code possession must be protected and the person's identity verified through your own administrative process.

To disable access and revoke sessions:

```powershell
.\.venv\Scripts\python.exe scripts\manage_users.py revoke --email your-email@example.com
```

Use `docker compose exec app python scripts/manage_users.py ...` for the Compose database.

## Before hosting publicly

Require HTTPS, set `GOVERNSIM_AUTH_COOKIE_SECURE=true`, set exact trusted HTTPS origins, disable legacy bearer access and use managed secret storage. The API and frontend must use the same origin (the Vite development proxy is supported). Back up `GOVERNSIM_AUTH_KEY` securely with a recoverable database backup; do not rotate or discard it blindly. Losing it makes existing encrypted authenticator secrets unreadable and requires account recovery/reset.

There is no public signup, email verification, email/SMS OTP, social login, self-service password reset, passkey support or enterprise SSO in this change. TOTP is not phishing-resistant. Enterprise identity lifecycle, phishing-resistant factors, organization isolation and operational monitoring remain further work.
