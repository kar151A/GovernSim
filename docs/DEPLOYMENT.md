# Local deployment and later hosting

The multi-stage Dockerfile builds the React UI, installs Python dependencies and runs FastAPI as a non-root user. Compose supplies PostgreSQL with pgvector and a persistent volume. Only the app is exposed, bound to loopback at `127.0.0.1:8000`; PostgreSQL is private to the Compose network. The application filesystem is read-only with temporary `/tmp`, no added capabilities and no privilege escalation.

## Before a hosted deployment

This MVP is prepared for local deployment. A hosted enterprise deployment requires additional engineering:

- Integrate enterprise SSO/OIDC as needed. The current invite-only local accounts require password + TOTP, support email verification, password reset/change and revocation/recovery, and use expiring cookie sessions. Configure a TLS SMTP sender and monitor deliveries. Add an organization-aware authorization model. Current roles share a single estate; there is no tenant isolation.
- Serve behind TLS, bind only the intended ingress, configure allowed origins and preserve server-side authorization. Set `GOVERNSIM_AUTH_COOKIE_SECURE=true`, configure exact HTTPS `GOVERNSIM_AUTH_ORIGINS`, and keep legacy bearer opt-in disabled. Back up the MFA encryption key separately from the database; never publish it.
- Move schema creation to reviewed migrations and give runtime a least-privilege database role. The prototype initializes tables, append-only triggers and the pgvector extension at startup, so its database identity has schema privileges.
- Configure backups, restore testing, operational monitoring and independently retained signed audit head anchors. Hash chaining is not immutable external storage.
- Review legal applicability and effective dates with qualified counsel; replace illustrative policy thresholds and synthetic evidence with validated organizational controls and records.
- Replace synchronous bounded workflows with durable jobs for large ingestion; add pagination/indexing and load tests for large estates.
- Add request rate limits/body limits at ingress, access logging/alerting, model spend budgets and secret management. The current application bounds text payloads and declared content length, but the ingress should also limit streamed requests.
- Scan dependencies and container images, pin deployment image digests, and run PostgreSQL integration tests and browser QA in the actual deployment environment.

## Persistence and scale

SQLite is a single-worker local convenience. The application serializes transactions in one process; do not run multiple SQLite workers. PostgreSQL appends also take a database advisory lock, but this release remains configured as one application worker. Scale only after concurrency/load validation.

Database startup uses SQLAlchemy `create_all` for a new MVP schema, not an ongoing migration system. An incompatible schema change requires a planned migration rather than assuming `create_all` will alter existing tables.

`docker compose down` preserves the database volume. `docker compose down -v` deletes it and should be used only for an intentional reset. `.env`, `.local-keys.txt`, local SQLite databases, dependency directories and build outputs are ignored by Git and excluded from the source archive.

## Online LLM summaries

Offline mode is the default. Optional providers use fixed OpenAI/Anthropic HTTPS endpoints through a bounded HTTP client. Unknown provider names are rejected. Provider credentials are server-only and never shipped to React.

The optional online path is not exercised without real credentials. Record and evaluate grounding, prompt-injection resilience, policy-relevant hallucinations, latency and actual cost before turning it on for enterprise evidence. Source-ID validation alone cannot establish that each generated sentence is entailed by the cited records.
