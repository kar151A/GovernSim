# Verification record

Development date: 30 October 2026.

## Confirmed in the authoring environment

- **120 passed, 1 skipped**: Python 3.12 backend regression suite using FastAPI TestClient and fresh SQLite databases. The skipped case requires disposable PostgreSQL. The earlier `evaluation/test-results.xml` records the pre-authentication evaluation; the count here includes 55 account-authentication cases and nineteen SMTP/configuration cases.
- API → database → kernel → response workflows: registry/fixtures, evidence ingestion and independent verification, compatible mapping proposal/review, isolated simulations, actual changes and transitive dependents, policy profiles, conditional reviews, stale decisions/scenarios, concurrent audit appends, complete provenance, graph relations and all export formats.
- Append-only triggers reject mutation; an intentionally bypassed trigger and tampered hash is detected by integrity verification.
- TypeScript compilation and Vite production build succeed. Built HTML/JavaScript/CSS delivery, local policy source delivery, and API documentation security headers are covered by integration tests. The generated UI uses same-origin `/api` requests when served by FastAPI.
- Python critical-error linting, dependency consistency checks, and Compose YAML parsing pass.
- Synthetic evaluation script measures the artifact-gap cases, type-compatibility golden set, scenario changes, review escalations, provenance and local audit package time. See `evaluation/REPORT.md`.

## Console redesign validation

- All seven workspaces support light/dark appearances, saved user choice, cross-tab preference synchronization, responsive layouts, command navigation, labeled keyboard tabs and a focus-managed mobile drawer.
- Desktop layouts, capture dialogs, simulation output and a 390px viewport were visually inspected using a separate harness with actual synthetic API response snapshots. The harness is not part of the shipped application.
- The production frontend build and the 46-test backend regression suite pass after the redesign. One PostgreSQL test remains skipped locally.
- The original GitHub main tree matched the pre-redesign snapshot before publishing; updates preserve its existing history.

## Account authentication validation

- Account authentication cases cover invite-only enrollment, password plus TOTP, encrypted secrets, digest-only tokens, single-use recovery codes, code replay, concurrent verification, session expiry/revocation, role enforcement, CSRF/origin checks, attempt limits, administrative reset and credential redaction.
- Password verification alone cannot access protected APIs. Legacy bearer access is disabled by default. Account setup creates a full session only after a valid second factor.
- The optional PostgreSQL integration test also exercises account enrollment, TOTP sign-in, cookie-authenticated mutation, logout, email password reset and authenticated password change against PostgreSQL. It remains skipped locally until the published CI job runs.
- Bootstrap upgrade was checked in disposable project copies: existing configuration is preserved and one persistent encryption key is added without printing it.
- The previous empty sign-in and invitation forms were visually inspected in light/dark appearances and at 390px using the separate synthetic-response harness. No real credentials were entered in that browser. Authentication behavior was tested through the real FastAPI handlers and databases using TestClient.

## Email verification and password lifecycle validation

- Twenty-five additional API cases exercise approved-email setup, server-side password confirmation, code storage, expiry, five-attempt limits, resend cooldown, old-code/browser invalidation, purpose binding, SMTP failure, disabled/unknown accounts, password changes/resets and revocation of prior sessions/flows.
- Nineteen SMTP/setup cases verify certificate-checked SSL/STARTTLS, login after TLS, recipient addressing, rejected plaintext/header injection, safe provider errors, private credential persistence and saving nothing after failed delivery. Additional cases classify authentication, DNS, timeout, connection, certificate, TLS and sender/recipient failures without exposing provider responses, and verify Gmail App Password spacing cleanup. Tests use a controlled in-memory mailbox/transport; no real email is sent.
- A full local run passes 120 tests with one PostgreSQL-only case skipped. The TypeScript/Vite build and critical Python lint pass.
- The email-setup button, Forgot password screen and signed-in Change password dialog are visually checked using a separate synthetic-response harness. Passwords and OTPs are not entered through browser automation.
- Real delivery to an external mailbox remains unverified until an administrator supplies working SMTP credentials and checks the delivery test. A provider accepting SMTP is not proof that an email reached the inbox.

## Not yet confirmed

- Docker/PostgreSQL/pgvector execution: Docker is unavailable here. Compose, its healthchecks and an opt-in PostgreSQL integration test are included. The GitHub CI PostgreSQL job must run after you push the repository.
- Live browser-to-API integration: the managed live preview cannot find `uvicorn`. Visual checks used the separate synthetic-response harness described above; backend integration is covered by TestClient tests.
- Actual Windows PowerShell execution: launchers and explicit commands are provided, but the authoring environment is Linux.
- Paid OpenAI/Anthropic requests: no provider credentials were used. Offline retrieval and the separation from kernel decisions are tested.
- GitHub Actions results must be checked on the published commit; local checks do not establish remote CI success.
- Public hosting: not attempted, as requested.

Do not interpret passing synthetic tests as validated legal compliance, security certification, production scale or production model accuracy.
