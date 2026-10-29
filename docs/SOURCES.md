# Representative source library

The thirty requirements are authored summaries and **not** a complete legal corpus. The catalog links each finding to a document/clause or public principle. No LLM invents new requirements. Human reviewers must confirm applicability, effective dates, interpretation and control sufficiency.

| Framework | Primary source | Treatment in GovernSim |
| --- | --- | --- |
| NIST AI RMF | https://airc.nist.gov/airmf-resources/airmf/5-sec-core/ | Five representative outcomes across Govern, Map, Measure, Manage. Voluntary framework. |
| ISO/IEC 42001 | https://www.iso.org/standard/42001 | Five principles aligned to the public overview. No licensed clause text or exact clause-conformance/certification claim. |
| EU AI Act | https://eur-lex.europa.eu/eli/reg/2024/1689/oj/eng | One interaction-disclosure example and four high-risk examples. Legal classification is explicit and separate from internal risk. |
| EU AI Act transparency | https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-50 | Official explanatory service; consult authoritative law and current amendments. |
| EU AI Act classification | https://digital-strategy.ec.europa.eu/en/faqs/navigating-ai-act | Intended use matters; EU geography alone does not make customer support high risk. |
| GDPR | https://eur-lex.europa.eu/eli/reg/2016/679/oj/eng | Five representative privacy controls; DPIA trigger is conditional and intentionally simplified. |
| India DPDP | https://www.meity.gov.in/documents/act-and-policies/digital-personal-data-protection-rules-2025-gDOxUjMtQWa | Five readiness controls. Check the Gazette for phased commencement and applicability. |
| Internal policy | ../frontend/public/policies/internal-policy.md | Five authored demonstration gates plus explicit evidence freshness profiles. This file is shipped in the frontend's static source library. |

Public source pages were consulted during development on 29 October 2026. Source URLs are pointers, not locally captured authoritative legal snapshots. The EUR-Lex site presented an automated access challenge in this environment; this project does not claim to have ingested the entire consolidated regulations. Legal updates and new guidance are not automatically synchronized.

## Framework limits

The EU AI Act's general interaction disclosure requirement is not interchangeable with high-risk-system requirements. A customer-support chatbot's exact role and intended use need classification; the demo does not infer legal high-risk status solely from processing personal data or deployment in the EU.

DPDP commencement is phased. The catalog deliberately labels these controls as preparation/readiness, rather than declaring every provision immediately applicable. This MVP does not compute provision-by-provision effective dates.

The ISO text is not reproduced. Its entries explicitly use public principles rather than claiming exact clause mappings. NIST entries represent voluntary risk-management outcomes, not mandatory statutory duties.

## Technical references

- FastAPI container deployment: https://fastapi.tiangolo.com/deployment/docker/
- SQLAlchemy JSON persistence: https://docs.sqlalchemy.org/en/20/core/type_basics.html#sqlalchemy.types.JSON
- pgvector: https://github.com/pgvector/pgvector
- React: https://react.dev/

The vector representation is offline signed lexical hashing with 128 dimensions. pgvector stores and ranks those vectors on PostgreSQL; SQLite computes cosine similarity locally. This is not claimed to be a trained semantic embedding model.
