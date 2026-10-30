# Email verification, login and password recovery

GovernSim supports email-code account setup, password confirmation, authenticator-app two-factor sign-in, signed-in password changes and email-based password reset. An administrator approves account email addresses and roles locally. Entering an arbitrary email does not grant access to the shared company workspace.

## Upgrade and connect email on Windows

Stop the server and run from the project root. Preserve local source edits before pulling.

```powershell
git pull --ff-only origin main
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
.\.venv\Scripts\python.exe scripts\bootstrap.py
.\.venv\Scripts\python.exe scripts\configure_email.py --admin-email your-email@example.com
npm.cmd run build --prefix frontend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

Replace the example email with yours. `git pull --ff-only` downloads the published changes without silently creating a merge commit. Bootstrap preserves existing settings and adds a persistent encryption key if missing. The email configuration command prompts locally for the SMTP host, TLS mode, username, sender and a hidden SMTP/App Password. It sends a delivery test before saving settings; it never prints the password. It also approves this email for the first administrator setup. Existing account roles are preserved, and disabled accounts remain disabled. The website account password is chosen separately in the browser.

A Gmail sender uses `smtp.gmail.com`, SSL port `465` (or STARTTLS port `587`), the sender's email, and its App Password when supported by that account. Other SMTP providers work with their own connection settings. Enter credentials only in your local terminal. Never paste them into chat, source code, a command argument, or a `VITE_*` variable.

**No SMTP credentials are bundled.** Until configured, the Send code button reports that email delivery is unavailable. SMTP acceptance does not guarantee inbox placement; check spam and your provider's delivery records. Restart the server after changing configuration.

## If the delivery test fails

The setup command now reports a fixed, credential-safe reason and, when available, a numeric SMTP status. It never prints the provider's raw response or your password. Settings are saved only after the test succeeds.

| Diagnostic | Next step |
| --- | --- |
| Sender login rejected, often SMTP 535 | Confirm that the SMTP username and App Password belong to the same sending account. Gmail display spaces are removed automatically. |
| Connection timeout or refusal | Check internet/firewall access to the configured port. For Gmail, try `starttls` with port `587` if SSL `465` is blocked. |
| Hostname cannot be resolved | Check the SMTP host spelling and DNS connection. |
| TLS/certificate failure | Check the chosen TLS mode, provider port, computer clock and trusted certificates. Certificate checks stay enabled. |
| Sender or recipient rejected | Check the From/admin email and the provider's sender/recipient restrictions. |

On Windows, `Test-NetConnection smtp.gmail.com -Port 465` checks basic reachability without sending credentials. A successful TCP check does not establish that SMTP authentication or email delivery will work. Share only the short diagnostic text when troubleshooting, never your `.env` file or App Password.

## First account setup

1. Open `http://localhost:8000` and choose **Set up your account**.
2. Enter your approved email and click **Send verification code**.
3. Enter the six-digit code from the email. Choose a unique passphrase of at least 15 characters and enter it again.
4. Click **Verify email and create password**. Connect your authenticator by scanning the QR code or entering the setup key manually.
5. Enter the authenticator's six-digit code, save the ten one-use recovery codes privately, and open the workspace.

The email code expires after five minutes, permits five attempts and works only in the browser where it was requested. Resend becomes available after 60 seconds and invalidates older email codes. There is a five-email budget per account and twenty per IP in fifteen minutes. Unknown, disabled, enrolled-for-signup and unapproved addresses receive the same generic request response without an email code. SMTP configuration/delivery failures are reported separately; this is not a guarantee against all timing-based account enumeration.

Account approval expires after 24 hours. Interrupted email setup can be restarted while that approval remains valid. Once enrollment succeeds, its approval is consumed. An administrator can approve or renew an unenrolled email:

```powershell
.\.venv\Scripts\python.exe scripts\manage_users.py invite --email teammate@example.com --role AI_OWNER
```

There is no invitation field in the website. The CLI still prints a private invitation token for compatibility with the original offline API enrollment endpoint. Never invent an invitation token. Use separate AI_OWNER and COMPLIANCE_REVIEWER accounts for independent review.

## Later visits and password changes

Sign in with email, password and an authenticator code (or one-use recovery code). Previously accepted authenticator time steps cannot be reused; wait for the next code when signing in immediately again.

- **Know your password:** after signing in, click the key icon **Change password** in the top bar. Enter your current password, new password and the new password again. Every session and pending login/reset flow is revoked; sign in again.
- **Forgot your password:** click **Forgot password?**, enter your account email and request a reset code. Enter the emailed code plus a new password twice. The code is consumed and all sessions are revoked. Sign in using the new password and your existing authenticator or recovery code.

Email reset changes only the password. It never disables two-factor verification, changes the email/role, re-enables a disabled account or creates a logged-in session. Password confirmation is checked on both client and server. The old password stops working after a successful reset/change.

## Docker Compose

Configure SMTP locally first. The configuration command approves the local SQLite account; Compose uses a separate PostgreSQL database, so approve that email inside the running app container:

```powershell
docker compose up --build -d
docker compose exec app python scripts/manage_users.py invite --email your-email@example.com --role ADMIN
```

Compose passes the SMTP settings and encryption key from the root `.env` to the server. They are excluded from Git and the Docker image. Recreate the app with `docker compose up -d --force-recreate app` after changing environment settings. Do not run the interactive email configuration command inside the read-only container.

## Session and secret handling

- Passwords use Argon2id through `pwdlib`; plaintext account passwords are never stored.
- Short-lived email codes use a server-keyed HMAC bound to their challenge, purpose and account. Raw email codes are not stored, returned by the API or written to audit events.
- Verification flows are limited, expiring and single-use. Neither mailbox verification nor password verification alone grants workspace access.
- TOTP uses PyOTP with a 30-second step, one-step clock-skew allowance and per-account replay prevention. Recoverable TOTP secrets are encrypted with Fernet.
- Session, invitation and challenge tokens are random; only SHA-256 digests are stored. Sessions have an eight-hour absolute expiry, HttpOnly and SameSite=Strict cookies, and server-side revocation.
- Mutating cookie-authenticated requests require a trusted Origin and a session-bound CSRF header. Auth flows require a trusted Origin. Validation responses omit submitted input values.
- SMTP uses verified TLS (SSL or STARTTLS) and has a network timeout. No plaintext SMTP transport or console-code fallback is provided. SMTP acceptance followed by a database failure requires requesting a fresh code.
- The default configuration rejects legacy bearer tokens. `GOVERNSIM_ALLOW_LEGACY_API_KEYS=true` deliberately bypasses MFA for old automation and should remain disabled for account-only access.
- This remains a single-worker application. SMTP sends occur synchronously under the auth transaction lock; use a durable email queue and distributed abuse controls before scaling.

## Lost authenticator or disabling access

Use a saved recovery code with your password. If all second-factor options are lost, a local administrator verifies the person's identity through the organization's own process and runs:

```powershell
.\.venv\Scripts\python.exe scripts\manage_users.py reset --email your-email@example.com
```

This requires typing `RESET`, revokes all credentials/sessions, preserves the principal identifier and role, and re-approves setup. It is distinct from the email-only password reset, which preserves the authenticator.

Disable an account and revoke access:

```powershell
.\.venv\Scripts\python.exe scripts\manage_users.py revoke --email your-email@example.com
```

Use `docker compose exec app python scripts/manage_users.py ...` for the Compose database.

## Before public hosting

Require HTTPS, set `GOVERNSIM_AUTH_COOKIE_SECURE=true`, set exact trusted HTTPS origins, keep frontend/API on the same origin, disable legacy bearer access and use managed secret storage. Back up `GOVERNSIM_AUTH_KEY` securely alongside a recoverable database backup. Losing this key makes encrypted authenticator secrets unreadable. Do not rotate it blindly.

There is no public self-registration, SMS login, social login, passkey support, enterprise SSO or organization isolation. Account roles share one workspace. TOTP and email codes are not phishing-resistant factors. Enterprise identity lifecycle and monitoring remain further work.
