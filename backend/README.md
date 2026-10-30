# GovernSim backend

FastAPI serves authenticated `/api` workflows and the compiled console from `frontend/dist`. The request boundary verifies server-owned identities and roles before persistence or governance actions.

| Module | Responsibility |
| --- | --- |
| `app/main.py` | HTTP boundary, authorization, transactions and static delivery |
| `app/auth.py` | Invite-only password/TOTP enrollment, sessions, CSRF, recovery and throttling |
| `app/schemas.py` | Request shape and value validation |
| `app/kernel.py` | Deterministic assessments of scoped evidence |
| `app/service.py` | Saved assessments, isolated simulations and dependent reassessment |
| `app/agents.py` | Ingestion, retrieval, mapping proposals and optional summaries |
| `app/audit.py`, `app/db.py` | Hash chaining, persistence and append-only protections |
| `app/reports.py` | JSON, Markdown and PDF evidence packages |

## Run from the project root

Generate credentials with `python scripts/bootstrap.py`, install `backend/requirements.txt`, build the frontend, then run:

```sh
python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

Use your virtual environment's Python. `/health` reports readiness; `/docs` describes API requests. Account authentication requires the bootstrap encryption key; legacy bearer tokens are disabled by default. SQLite is the local default; Compose configures PostgreSQL and pgvector.

## Checks and invariants

Install `backend/requirements-dev.txt` and run `python -m pytest backend/tests -q`. `TEST_POSTGRES_URL` must name a disposable database for the PostgreSQL integration test. Simulations preserve registry state; evidence is bound to its scope; independent reviewers cannot approve missing evidence into compliance. LLM summaries never determine status. See [decision semantics](../docs/DECISION_MODEL.md) and [verification limits](../docs/VERIFICATION.md).
