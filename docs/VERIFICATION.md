# Verification record

Development date: 29 October 2026.

## Confirmed in the authoring environment

- **46 passed, 1 skipped**: Python 3.12 backend regression suite using FastAPI TestClient and fresh SQLite databases. The skipped case requires disposable PostgreSQL. See `evaluation/test-results.xml` for the measured count and individual tests.
- API → database → kernel → response workflows: registry/fixtures, evidence ingestion and independent verification, compatible mapping proposal/review, isolated simulations, actual changes and transitive dependents, policy profiles, conditional reviews, stale decisions/scenarios, concurrent audit appends, complete provenance, graph relations and all export formats.
- Append-only triggers reject mutation; an intentionally bypassed trigger and tampered hash is detected by integrity verification.
- TypeScript compilation and Vite production build succeed. Built HTML/JavaScript/CSS delivery, local policy source delivery, and API documentation security headers are covered by integration tests. The generated UI uses same-origin `/api` requests when served by FastAPI.
- Python critical-error linting, dependency consistency checks, and Compose YAML parsing pass.
- Synthetic evaluation script measures the artifact-gap cases, type-compatibility golden set, scenario changes, review escalations, provenance and local audit package time. See `evaluation/REPORT.md`.

## Not yet confirmed

- Docker/PostgreSQL/pgvector execution: Docker is unavailable here. Compose, its healthchecks and an opt-in PostgreSQL integration test are included. The GitHub CI PostgreSQL job must run after you push the repository.
- Browser interaction and visual QA: the managed preview attempted to launch, but its separate runtime could not find `uvicorn`/the local Python virtual environment (`No module named uvicorn`). No alternate browser infrastructure was used. This does not invalidate the backend integration tests or compiled frontend, but browser behavior remains unverified until you run it locally.
- Actual Windows PowerShell execution: launchers and explicit commands are provided, but the authoring environment is Linux.
- Paid OpenAI/Anthropic requests: no provider credentials were used. Offline retrieval and the separation from kernel decisions are tested.
- GitHub remote creation/push: no authenticated GitHub connection or CLI session was available. The intended destination is `kar151A/GovernSim`; repository creation instructions are included.
- Public hosting: not attempted, as requested.

Do not interpret passing synthetic tests as validated legal compliance, security certification, production scale or production model accuracy.
