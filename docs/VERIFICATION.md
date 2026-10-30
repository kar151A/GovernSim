# Verification record

Development date: 30 October 2026.

## Confirmed in the authoring environment

- **76 passed, 1 skipped**: Python 3.12 backend regression suite using FastAPI TestClient and fresh SQLite databases. The skipped case requires disposable PostgreSQL. The earlier `evaluation/test-results.xml` records the pre-authentication evaluation; the count here includes 30 new account-authentication cases.
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

- Thirty new authentication cases cover invite-only enrollment, password plus TOTP, encrypted secrets, digest-only tokens, single-use recovery codes, code replay, concurrent verification, session expiry/revocation, role enforcement, CSRF/origin checks, attempt limits, administrative reset and credential redaction.
- Password verification alone cannot access protected APIs. Legacy bearer access is disabled by default. Account setup creates a full session only after a valid second factor.
- The optional PostgreSQL integration test also exercises account enrollment, TOTP sign-in, cookie-authenticated mutation and logout against PostgreSQL. It remains skipped locally until the published CI job runs.
- Bootstrap upgrade was checked in disposable project copies: existing configuration is preserved and one persistent encryption key is added without printing it.
- Empty sign-in and invitation forms were visually inspected in light/dark appearances and at 390px using the separate synthetic-response harness. No real credentials were entered in that browser. Authentication behavior was tested through the real FastAPI handlers and databases using TestClient.

## Not yet confirmed

- Docker/PostgreSQL/pgvector execution: Docker is unavailable here. Compose, its healthchecks and an opt-in PostgreSQL integration test are included. The GitHub CI PostgreSQL job must run after you push the repository.
- Live browser-to-API integration: the managed live preview cannot find `uvicorn`. Visual checks used the separate synthetic-response harness described above; backend integration is covered by TestClient tests.
- Actual Windows PowerShell execution: launchers and explicit commands are provided, but the authoring environment is Linux.
- Paid OpenAI/Anthropic requests: no provider credentials were used. Offline retrieval and the separation from kernel decisions are tested.
- GitHub Actions results must be checked on the published commit; local checks do not establish remote CI success.
- Public hosting: not attempted, as requested.

Do not interpret passing synthetic tests as validated legal compliance, security certification, production scale or production model accuracy.
