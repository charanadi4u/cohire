# Verification report

Prepared 2026-11-01. This report distinguishes executed checks from implementation that still needs an integration environment.

## Executed and passed

| Check | Evidence |
|---|---|
| Automated backend/security/workflow suite | `test-results.txt`: 25 passed |
| Real HTTP API + independent durable worker | `demo-result.json`: 100, 60, 0 supported points |
| Real HTTP API + worker + separate A2A service | `demo-a2a-result.json`: same rankings; review, feedback and interview draft |
| A2A operation survives service process restart | `a2a-restart-result.json`: same completed result recovered |
| A2A 1.0 SDK wire exchange | Structured data in, structured artifact/task out; explicit version header |
| Duplicate A2A request | Same persisted task/result; no second business result |
| A2A authorization and erasure replay | Invalid bearer denied; erased logical operation blocked |
| SQLAlchemy/Alembic migration | Applied to fresh local SQLite database |
| PostgreSQL dialect generation | `postgresql-schema.sql` generated successfully, including forced RLS |
| ADK factory/API compatibility | Four LlmAgent instances constructed with output schemas and no tools |
| Python dependency resolution | `pip check`: no broken requirements |
| Next.js 16.4.3 build | Compilation, TypeScript checking and static page generation succeeded |
| Frontend production dependency audit | `npm audit --omit=dev`: zero known vulnerabilities at check time |

The automated suite covers cross-tenant reads/writes, missing credentials, privacy gating, encrypted raw source, idempotency conflict/replay, no resurrection through old upload keys, immutable job approval, human advance before interview draft, missing evidence and score bounds, malformed model output, invalid citations/offset hashes, invalid weights, missing assessments, schema rejection of identity fields, identity-only fixture edits, deletion during matching, expired leases, cancellation, candidate erasure, FAQ-independent held-out evaluation checks, and mocked Pub/Sub duplicate ingress/authentication.

## Not executed / not claimed

- Live Gemini or Vertex AI inference: no project/model credentials configured. Deterministic synthetic mode was used for both end-to-end runs. Constructing an ADK agent does not establish extraction quality.
- Live PostgreSQL 16 and runtime-role RLS/concurrency tests: no runnable PostgreSQL service was available. Offline SQL generation does not prove execution/isolation.
- Live Pub/Sub delivery: ingress identity validation was mocked in tests; publisher/provider calls were not exercised.
- Google Calendar API calls, invitations or external messages: not invoked. Calendar adapter supports reading availability and constructing a draft only.
- Windows execution: instructions supplied, but tests ran on Python 3.12.14 Linux.
- Browser interaction/accessibility tests: frontend build passed; no browser E2E run was performed.
- OCR, malware detection, model fairness/quality, load, recovery under network partitions, costs or production SLA: not validated.

## Reproduce locally

From the project root after setup:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pip check
```

Start the API and worker using README commands, then run `python scripts\demo.py`. For A2A, set `AGENT_TRANSPORT=a2a`, start the specialist service and restart the worker before running the same demo. The demos use synthetic professional profiles only.

The initial source contains approximately a small application worth of code, not a production certification. Review `PRODUCTION_GATES.md` before expanding access or connecting real candidates.
