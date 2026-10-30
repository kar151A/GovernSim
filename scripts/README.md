# Local project commands

Run commands from the project root using the project's virtual-environment Python. On Windows, that executable is `.\.venv\Scripts\python.exe`; on Linux/macOS, it is `.venv/bin/python`.

| Command | Requirements and effect |
| --- | --- |
| `python scripts/bootstrap.py` | Standard library only. Creates local configuration and adds a missing account-encryption key on upgrades; preserves existing values. |
| `python scripts/configure_email.py --admin-email you@example.com` | Prompts privately for SMTP credentials, tests delivery, saves local settings and approves the first administrator email. |
| `python scripts/manage_users.py invite --email you@example.com --role ADMIN` | Approves a pending email for 24 hours. The user requests an email code, chooses and confirms a password, then enrolls an authenticator. |
| `python scripts/manage_users.py revoke --email you@example.com` | Disables the account and revokes sessions and pending flows. |
| `python scripts/manage_users.py reset --email you@example.com` | Requires typed local confirmation, revokes credentials/sessions and issues a new invitation while keeping the account identity. |
| `node scripts/dev.mjs` | Starts FastAPI with the local virtual environment when available. Does not compile the UI. |
| `scripts/start-local.ps1` or `bash scripts/start-local.sh` | Installs dependencies, builds the UI and starts the local API. |
| `python scripts/demo.py` | Legacy automation only: requires explicit bearer-token opt-in, a running API and generated owner/reviewer tokens. Creates demo records and exports to ignored `artifacts/`. |
| `python scripts/evaluate.py` | Uses a disposable SQLite database; rewrites the tracked synthetic evaluation outputs. |
| `python scripts/source_manifest.py --write` | Refreshes SHA-256 hashes for tracked source files, excluding the manifest itself. UTF-8 CRLF/LF line endings are normalized; binary bytes are preserved. |
| `python scripts/source_manifest.py --check` | Reports missing, extra or changed snapshot entries without rewriting the manifest. |

`npm run build` compiles the UI; `npm run dev:ui` starts Vite with a separate API; `npm run preview:ui` previews compiled assets. The FastAPI launch path is the supported full-workflow local entry point.

Never paste `.local-keys.txt` into issue reports or commit generated credentials. If startup fails, capture the error with credentials removed; see the root [README](../README.md) for explicit setup commands.
