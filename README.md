# Co-Agent-Recruitment Hire

An executable recruiter-assistance project built from the Co-Agent-Recruitment Hire skill. It includes a FastAPI backend, durable workflow worker, Google ADK/Gemini adapters, authenticated A2A specialist service, PostgreSQL migrations, a Next.js recruiter workspace, synthetic fixtures, and automated tests.

**Release status:** local/integration MVP, not a deployed or production-approved recruitment system. The complete synthetic workflow is runnable without cloud credentials. Read `docs/VERIFICATION.md` for exactly what was tested and `docs/PRODUCTION_GATES.md` for remaining work. Production startup is deliberately blocked in configuration.

## The realistic example prompt

> We are hiring a Python API Engineer for a Bengaluru product team. Python, FastAPI, and PostgreSQL are required; GCP is preferred. Process the three supplied resumes, remove identity information before agent processing, and show the extracted job criteria for recruiter approval. Use approved weights of 30%, 30%, 30%, and 10%. Rank candidates using cited professional evidence, show missing evidence separately, and prepare an interview proposal for a candidate who meets the review policy. Do not reject applicants, contact anyone, or book an interview automatically.

The bundled resumes are fictional. Candidate A documents all four skills; B documents Python and PostgreSQL; C documents Java but none of the approved criteria. The deterministic demo produces **100 / 60 / 0 supported points**, with **100% / 60% / 0% evidence coverage**. Candidate C's zero means no supported evidence in this small rubric, not disqualification. All results require recruiter review.

## Windows quick start — no Docker, no uv

Install Python 3.12. Extract the ZIP and open PowerShell in the `cohire` folder containing `pyproject.toml`.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock.txt
.\.venv\Scripts\python.exe -m pip install --no-deps -e .
.\.venv\Scripts\python.exe scripts\configure.py
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m scripts.init_db
```

`configure.py` creates `.env` with new local secrets and refuses to overwrite an existing file. Keep the file private. The default SQLite setup is an isolated demo convenience; PostgreSQL is the intended authoritative deployment database. Dependencies were resolved on Python 3.12 Linux; the Windows instructions are supplied but were not executed on a Windows host.

Start the API in terminal 1:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.api.main:app --host 127.0.0.1 --port 8000
```

Start the durable worker in terminal 2, from the same folder:

```powershell
.\.venv\Scripts\python.exe -m app.workflows.worker
```

Run the full synthetic scenario in terminal 3:

```powershell
.\.venv\Scripts\python.exe scripts\demo.py
```

This calls the actual HTTP API, uploads four documents, explicitly approves the synthetic sanitized text, waits for parsing, approves the rubric, runs matching, reviews the top recommendation, records feedback, and prints ranked evidence and interview proposals. Every execution intentionally creates a new example cohort. The script's automated privacy approval is ONLY appropriate for these already-reviewed synthetic fixtures.

API documentation: http://127.0.0.1:8000/docs. Use the **Authorize** button with `DEV_TOKEN` from `.env`. Mutation endpoints that require retry protection also require an `Idempotency-Key` header; use a new UUID for each distinct action and reuse it only when retrying the same payload.

Run automated tests:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Tests use temporary databases and synthetic credentials, not your configured database.

## Recruiter interface

The backend, tests and demo require no JavaScript. The optional browser interface uses Next.js/TypeScript, as specified by the full-interface skill. Install Node.js 22 LTS if you want it.

```powershell
cd frontend
npm ci
npm run dev
```

Open http://127.0.0.1:3000, enter your local access token, and choose **Connect / refresh**. The token stays in page memory. The interface offers Intake, Jobs & rubric, Match review, Interviews, and Audit. Refresh progress after the separate worker processes a request. The API returns structured queued/completed/partial/failed/canceled states.

1. Upload a job and each resume in **Intake**.
2. Inspect and edit the sanitized text, then explicitly approve it. Names without labels and indirect identifiers need manual removal.
3. In **Jobs & rubric**, review the extracted requirements and citations, set weights, and approve.
4. In **Match review**, choose the approved job and ready candidates; run comparison and load results.
5. Inspect evidence and missing requirements, then record advance or hold.
6. In **Interviews**, prepare a future timezone-aware slot. It remains a draft awaiting candidate confirmation.

UI pages load the first 50 jobs/candidates. API pagination is available; large-corpus UI pagination is a release gate.

## PostgreSQL 16 setup

Install PostgreSQL locally using the Windows installer. Use SQL Shell (`psql`) or pgAdmin as an administrator to create a migration owner, a non-owner runtime role, and a separate identity database/role. Choose your own strong passwords; do not copy placeholders into a shared environment.

```sql
CREATE ROLE cohire_migrator LOGIN PASSWORD 'replace-migration-password';
CREATE ROLE cohire_runtime LOGIN PASSWORD 'replace-runtime-password' NOSUPERUSER NOBYPASSRLS;
CREATE ROLE cohire_identity LOGIN PASSWORD 'replace-identity-password' NOSUPERUSER NOBYPASSRLS;
CREATE DATABASE cohire OWNER cohire_migrator;
CREATE DATABASE cohire_identity OWNER cohire_identity;
```

Run domain migrations with migration credentials, never the runtime role:

```powershell
$env:DATABASE_URL = 'postgresql+asyncpg://cohire_migrator:YOUR_PASSWORD@localhost:5432/cohire'
.\.venv\Scripts\python.exe -m alembic upgrade head
Remove-Item Env:DATABASE_URL
```

Connect to the `cohire` database as administrator, then:

```sql
GRANT CONNECT ON DATABASE cohire TO cohire_runtime;
GRANT USAGE ON SCHEMA public TO cohire_runtime;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO cohire_runtime;
REVOKE ALL ON alembic_version FROM cohire_runtime;
```

Set `.env`:

```dotenv
DATABASE_URL=postgresql+asyncpg://cohire_runtime:YOUR_PASSWORD@localhost:5432/cohire
IDENTITY_DATABASE_URL=postgresql+asyncpg://cohire_identity:YOUR_OTHER_PASSWORD@localhost:5432/cohire_identity
```

URL-encode special password characters. Initialize the vault with `python -m scripts.init_db`. Never point the identity URL at the domain database. The API sets transaction-local tenant context from verified credentials; migrations apply forced RLS to all tenant domain tables. Run the PostgreSQL-specific verification in `docs/PRODUCTION_GATES.md` before shared use. SQLite tests do not establish PostgreSQL RLS correctness.

## Activate Gemini on Vertex AI

Install Google Cloud CLI. In your chosen project, configure Vertex AI access and the necessary IAM permissions with your cloud administrator. No resources are created by the supplied scripts.

```powershell
gcloud auth application-default login
```

Edit `.env` with a model ID actually available to your project and region:

```dotenv
AGENT_MODE=gemini
GOOGLE_GENAI_USE_VERTEXAI=true
GOOGLE_CLOUD_PROJECT=YOUR_PROJECT
GOOGLE_CLOUD_LOCATION=YOUR_REGION
GEMINI_PARSE_MODEL=YOUR_AVAILABLE_MODEL_ID
GEMINI_MATCH_MODEL=YOUR_AVAILABLE_MODEL_ID
```

Restart the API/worker. Model IDs are intentionally not guessed. Run only synthetic data for the first cloud smoke test. `app/agents/specialists.py` constructs schema-constrained ADK `LlmAgent` instances with no write tools. `Runner` uses isolated short-lived sessions; the database workflow owns durable recovery. The model performs extraction/assessment; Python validates citations and computes the final score.

The current MVP extracts professional **skill evidence**. Experience intervals, qualification verification, semantic retrieval, equivalence governance and multilingual/OCR extraction require expansion and evaluation before broad recruitment use. Gemini mode can interpret more skill language than the fixture parser but does not remove these scope limits.

## Run A2A specialists as a separate service

The locked pair is `google-adk==2.13.0` and `a2a-sdk==1.3.0`, using A2A 1.0 JSON-RPC and the explicit `A2A-Version: 1.0` header. Do not mix these v1 protobuf wire types with pre-v1 Pydantic examples.

Set `AGENT_TRANSPORT=a2a` in `.env`. Keep `A2A_URL=http://127.0.0.1:8001` and a generated `A2A_TOKEN`. Start a third service:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.a2a.server:app --host 127.0.0.1 --port 8001
```

Restart API and worker, then run `scripts\demo.py`. The single specialist service hosts three narrow capabilities and optional intent interpretation. Each service instance is bound to one configured tenant; its local bearer secret is not a multi-tenant production identity system. Agent card, RPC and management routes all require that credential. Do not expose it publicly.

Operation IDs persist before inference and map to deterministic task IDs. Retries first reconcile the operation. Completed results survive service restart; erased operations cannot be replayed. Pure model work can repeat after a crash before its result is committed, but domain result uniqueness and fencing prevent duplicate business effects. Streaming and push notifications are disabled.

## Pub/Sub and Calendar boundaries

`app/events/pubsub.py` provides an outbox publisher and OIDC-authenticated push ingress. Configure topic, audience and exact push service-account email. Run `python -m app.events.pubsub` to relay pending events. Push only records a durable inbox receipt; the separate database worker executes workflows. The local worker polls the same database even when Pub/Sub is enabled. This is not a claim of exactly-once delivery or cloud deployment parity.

`app/integrations/calendar.py` offers a credential-injected free/busy reader and deterministic calendar draft payload. **There is no booking/send endpoint in this release.** Candidate confirmation, scoped authorization expiry, provider reconciliation, cancellation and authorized messaging must be implemented and tested before enabling external actions. This keeps the example usable without creating real invitations.

## Project map

| Path | Responsibility |
|---|---|
| `app/api` | REST, verified authentication, tenant scope, recruiter actions |
| `app/domain` | Strict contracts and deterministic evidence scoring |
| `app/privacy` | Text/PDF/DOCX extraction, preview redaction, evidence hashes |
| `app/repositories` | Domain tables, vault, transaction-local tenant context |
| `app/agents` | ADK specialist factory, fixture adapter, FAQ draft fallback |
| `app/workflows` | Leases, fences, retries, partial results and cancellation |
| `app/a2a` | Authenticated SDK JSON-RPC, durable task/operation store, client |
| `app/events` | Outbox publishing and durable Pub/Sub inbox |
| `app/integrations` | Calendar read/draft boundary |
| `app/evaluation` | Held-out evaluation report; no automatic promotion |
| `migrations` | Alembic schema and PostgreSQL RLS policies |
| `frontend` | Next.js recruiter review interface |
| `tests` | Domain, API, privacy, recovery and A2A tests |
| `examples` | Fictional job and three resumes |
| `docs` | Architecture, OpenAPI, verification, production gaps and demo results |

## Troubleshooting

- **401:** ensure `.env` has `DEV_AUTH=true`, use its generated token, and restart processes after edits.
- **422:** inspect API validation. Missing `Idempotency-Key`, residual PII, malformed documents and unsupported weights fail closed.
- **409:** source/rubric already frozen, a key was reused with different data, or recruiter advance is missing. Create a new job for rubric changes.
- **Queued forever:** start the worker in the same folder with the same `.env`, database and tenant.
- **Failed model step:** inspect the safe workflow error, verify model IDs/ADC/region, then submit a new reviewed source/run. Inputs are not logged in error messages.
- **A2A error:** check both credentials, configured tenant, port and the pinned dependencies. Retry the same operation; do not invent a new operation after a timeout.
- **Scanned PDF:** provide a reviewed transcription; there is no OCR service in this release.
- **Port busy:** choose another `--port`, update API/frontend/A2A URLs consistently.

Do not use compatibility scores as hiring-success probabilities, infer demographic attributes, or treat missing evidence as a rejection. Employment decisions remain with authorized recruiters.
