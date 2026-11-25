# Production release gates and honest scope

This project is an end-to-end **local integration MVP**. It is not the full production implementation of every acceptance criterion in the 13-skill pack. `ENVIRONMENT` values other than `local` fail startup so that unimplemented boundaries cannot be mistaken for production controls.

## Before real candidate documents

1. Replace in-process extraction with a constrained document worker, malware checks, OCR and page-level provenance; test scanned, multilingual, multi-column and malformed documents.
2. Expand privacy detection beyond regex, validate manual review operations, segregate service roles and keys, implement retention and orphan-vault cleanup. Source encryption uses Fernet with a local environment key, not KMS envelope encryption.
3. Redaction plus pseudonyms does not guarantee anonymity or unbiased matching. Conduct role-specific privacy and fairness evaluation without inferring sensitive traits.
4. Add complete experience/qualification schemas, overlapping-date normalization, approved equivalences and model-quality evaluation. Current scoring covers approved skill criteria only.
5. Add schema-constrained output provenance and exact semantic citation checks beyond the existing reference/offset/hash checks. An existing citation can still be semantically irrelevant; recruiters must inspect it.
6. Add full candidate/job/rubric version history and correction workflows. This build freezes records at v1 and creates new records for edits.

## Database and distributed gates

- Apply migrations on PostgreSQL 16 using a migration owner. Test runtime access as a non-owner, NOSUPERUSER, NOBYPASSRLS role.
- Verify read/write isolation for every table with valid, missing and mismatched transaction tenant context. SQLite does not exercise RLS.
- Add tenant-aware relational foreign keys and immutable revision tables. Current application queries enforce relationships but the initial schema does not yet encode all composite reference invariants.
- Run concurrent worker/deletion/approval tests on PostgreSQL, fault injection and restore rehearsal. SQLite uses a single worker; never scale SQLite workers.
- Separate A2A task storage and identity services by credentials/database roles. Replace shared local A2A tokens with workload identity and scoped tenant delegation. Do not expose the local service externally.
- Exercise restart after reservation, crash during inference, timeout after completion, duplicate submissions, cancellation and delayed erasure on the deployed transport. Pure model inference may repeat after an uncommitted crash; business effects must remain idempotent.
- Erasure blocks access and clears persisted operation/task data. In-flight model calls cannot be retracted from the provider. Complete a provider/session retention and deletion design before using personal data.
- Add scheduled retention, retry backoff/jitter, dead-letter reconciliation, connection budgets, rate limits and multi-tenant worker scheduling.
- Validate Pub/Sub IAM, signed push identity, redelivery and monitoring in a real test project. The code supplies an adapter, not cloud-parity certification.

## Candidate communications and scheduling

The current scope is **draft-only**, including a Calendar free/busy adapter. Before external communication add:

- Candidate portal authentication and scoped exact-slot confirmation tokens.
- Purpose-bound communication preferences and opt-out enforcement.
- Recorded recruiter authorization bound to candidate, action, content and expiry.
- Calendar free/busy recheck, deterministic event IDs, provider reconciliation after timeout, cancellation and rescheduling.
- Delivery ledger, provider integration and explicit approved test recipients.
- Privacy-safe engagement FAQs, versioned publication scopes, rate limits and human escalation.

There is intentionally no endpoint that can send mail, hire, reject or book.

## Evaluation and operational gates

- Freeze representative consented or synthetic held-out datasets; separate candidate/job-family and temporal splits.
- Measure evidence precision/recall, false supporting citations, parser quality, retrieval recall if added, latency, cost, availability and subgroup disparities under an approved audit design.
- Feedback is selected and potentially confounded; unobserved candidates are not negative labels. The evaluation helper does not establish causal hiring impact.
- Extend release reports with privacy/reliability/load evidence, approval and rollback. The current evaluator never updates live configuration.
- Add safe OpenTelemetry spans, dashboards, alert thresholds, backups, key rotation and restore/deletion replay.
- Validate Windows setup on a Windows host and browser interactions across keyboard/mobile/error states.
- Recheck dependency security before every deployment. Do not deploy solely because a build/test suite passes.

## PostgreSQL RLS verification procedure

On a disposable migrated database, log in as `cohire_runtime`:

```sql
BEGIN;
SELECT set_config('app.tenant_id', '11111111-1111-4111-8111-111111111111', true);
-- Insert/select a synthetic row under tenant A through the API or table-specific fixture.
COMMIT;
BEGIN;
SELECT set_config('app.tenant_id', '22222222-2222-4222-8222-222222222222', true);
-- SELECT must not return tenant A rows; UPDATE/DELETE must affect zero rows.
-- INSERT with tenant A must fail its WITH CHECK policy.
ROLLBACK;
```

Repeat for every table; test missing context and role properties. Do not run this as the table owner or postgres superuser and interpret the result as runtime isolation.
