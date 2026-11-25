# How the 13-skill pack maps to this project

The primary skill and all 12 specialist SKILL.md instructions were read to select architecture and implementation boundaries. This matrix makes clear which parts are working in this release and which remain beyond the local MVP.

| Skill area | Delivered | Remaining production scope |
|---|---|---|
| Co-Agent-Recruitment Hire | Working upload-to-review/draft vertical slice and documentation | Production acceptance across every specialist |
| Orchestration | Typed dispatch, durable workflows, leases, fences, retry budget; optional ADK intent agent | Multi-tenant scheduling, backoff/DLQ, broader route tools |
| Resume parsing | TXT/PDF/DOCX extraction, privacy review, strict skills/evidence profiles, ADK adapter | OCR, extraction isolation, experience/qualification completeness |
| Job parsing | Draft skill requirements, citations, ambiguity rejection and approved weights | Rich job constraints, criterion correction/version lineage |
| Matching | Evidence assessments, deterministic score/coverage/bound, stable ranking | Retrieval/embeddings, approved equivalents, semantic evidence evaluation |
| Privacy | Encrypted separate source vault, manual sanitization gate, scoped reads, deletion tombstones | KMS/service segregation, retention automation, broader PII detection |
| A2A and events | SDK v1 transport, authentication, durable operations/tasks, outbox/inbox, Pub/Sub adapter | Workload identity, separate stores, deployed failure/load tests |
| API/PostgreSQL/UI | FastAPI endpoints, SQLAlchemy, Alembic/RLS SQL, Next.js workspace | Live PostgreSQL validation, composite FKs, full revisions and UI pagination |
| Scheduling | Threshold proposal, recruiter review, timezone-aware draft, Calendar read/draft adapter | Candidate confirmation, booking, cancellation and reconciliation |
| Engagement | Approved deterministic FAQ fallback and interview message draft | Candidate authentication, delivery ledger and messaging provider |
| Feedback learning | Feedback/exposure records, held-out report, no automatic promotion | Complete governed release workflow, quality/fairness/causal evaluation |
| Company analytics | Tenant aggregates with small-cohort suppression | Time windows, funnel definitions, richer versioned analytics |
| Evaluation/operations | Tests, compatibility lock, verification evidence, run instructions, release gates | Cloud deployment, monitoring, load/cost/restore evidence |

## Example interpretation

The realistic prompt in `README.md` uses professional skill evidence and explicit rubric approval. It does not infer sensitive candidate attributes, equate a score with a hiring probability, or authorize outreach. The demo's exact numbers illustrate the mechanics of supported evidence, not the validity of a recruitment model.
