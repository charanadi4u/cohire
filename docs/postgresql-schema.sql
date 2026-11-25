BEGIN;

CREATE TABLE alembic_version (
    version_num VARCHAR(32) NOT NULL, 
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);

-- Running upgrade  -> 001

CREATE TABLE candidates (
    status VARCHAR(32) NOT NULL, 
    revision INTEGER NOT NULL, 
    document JSON NOT NULL, 
    profile JSON NOT NULL, 
    consent BOOLEAN NOT NULL, 
    id VARCHAR(36) NOT NULL, 
    tenant VARCHAR(36) NOT NULL, 
    created VARCHAR(40) NOT NULL, 
    PRIMARY KEY (id)
);

CREATE INDEX ix_candidates_tenant ON candidates (tenant);

CREATE TABLE jobs (
    status VARCHAR(32) NOT NULL, 
    revision INTEGER NOT NULL, 
    document JSON NOT NULL, 
    profile JSON NOT NULL, 
    rubric JSON NOT NULL, 
    id VARCHAR(36) NOT NULL, 
    tenant VARCHAR(36) NOT NULL, 
    created VARCHAR(40) NOT NULL, 
    PRIMARY KEY (id)
);

CREATE INDEX ix_jobs_tenant ON jobs (tenant);

CREATE TABLE workflows (
    kind VARCHAR(40) NOT NULL, 
    subject VARCHAR(36) NOT NULL, 
    state VARCHAR(30) NOT NULL, 
    payload JSON NOT NULL, 
    result JSON NOT NULL, 
    attempts INTEGER NOT NULL, 
    lease_until FLOAT NOT NULL, 
    fence VARCHAR(36) NOT NULL, 
    error VARCHAR(80) NOT NULL, 
    id VARCHAR(36) NOT NULL, 
    tenant VARCHAR(36) NOT NULL, 
    created VARCHAR(40) NOT NULL, 
    PRIMARY KEY (id)
);

CREATE INDEX ix_workflows_tenant ON workflows (tenant);

CREATE TABLE matches (
    run_id VARCHAR(36) NOT NULL, 
    candidate_id VARCHAR(36) NOT NULL, 
    job_id VARCHAR(36) NOT NULL, 
    result JSON NOT NULL, 
    id VARCHAR(36) NOT NULL, 
    tenant VARCHAR(36) NOT NULL, 
    created VARCHAR(40) NOT NULL, 
    PRIMARY KEY (id), 
    UNIQUE (tenant, run_id, candidate_id)
);

CREATE INDEX ix_matches_candidate_id ON matches (candidate_id);

CREATE INDEX ix_matches_run_id ON matches (run_id);

CREATE INDEX ix_matches_tenant ON matches (tenant);

CREATE TABLE decisions (
    match_id VARCHAR(36) NOT NULL, 
    actor VARCHAR(200) NOT NULL, 
    action VARCHAR(40) NOT NULL, 
    reason TEXT NOT NULL, 
    id VARCHAR(36) NOT NULL, 
    tenant VARCHAR(36) NOT NULL, 
    created VARCHAR(40) NOT NULL, 
    PRIMARY KEY (id)
);

CREATE INDEX ix_decisions_tenant ON decisions (tenant);

CREATE TABLE proposals (
    match_id VARCHAR(36) NOT NULL, 
    candidate_id VARCHAR(36) NOT NULL, 
    status VARCHAR(40) NOT NULL, 
    details JSON NOT NULL, 
    id VARCHAR(36) NOT NULL, 
    tenant VARCHAR(36) NOT NULL, 
    created VARCHAR(40) NOT NULL, 
    PRIMARY KEY (id), 
    UNIQUE (tenant, match_id)
);

CREATE INDEX ix_proposals_tenant ON proposals (tenant);

CREATE TABLE outbox (
    workflow_id VARCHAR(36) NOT NULL, 
    published BOOLEAN NOT NULL, 
    id VARCHAR(36) NOT NULL, 
    tenant VARCHAR(36) NOT NULL, 
    created VARCHAR(40) NOT NULL, 
    PRIMARY KEY (id), 
    UNIQUE (workflow_id)
);

CREATE INDEX ix_outbox_tenant ON outbox (tenant);

CREATE TABLE inbox (
    event_id VARCHAR(100) NOT NULL, 
    id VARCHAR(36) NOT NULL, 
    tenant VARCHAR(36) NOT NULL, 
    created VARCHAR(40) NOT NULL, 
    PRIMARY KEY (id), 
    UNIQUE (tenant, event_id)
);

CREATE INDEX ix_inbox_tenant ON inbox (tenant);

CREATE TABLE audit (
    actor VARCHAR(200) NOT NULL, 
    action VARCHAR(60) NOT NULL, 
    subject VARCHAR(36) NOT NULL, 
    id VARCHAR(36) NOT NULL, 
    tenant VARCHAR(36) NOT NULL, 
    created VARCHAR(40) NOT NULL, 
    PRIMARY KEY (id)
);

CREATE INDEX ix_audit_tenant ON audit (tenant);

CREATE TABLE feedback (
    match_id VARCHAR(36) NOT NULL, 
    actor VARCHAR(200) NOT NULL, 
    data JSON NOT NULL, 
    id VARCHAR(36) NOT NULL, 
    tenant VARCHAR(36) NOT NULL, 
    created VARCHAR(40) NOT NULL, 
    PRIMARY KEY (id)
);

CREATE INDEX ix_feedback_tenant ON feedback (tenant);

CREATE TABLE idempotency (
    actor VARCHAR(200) NOT NULL, 
    route VARCHAR(150) NOT NULL, 
    key VARCHAR(128) NOT NULL, 
    digest VARCHAR(64) NOT NULL, 
    response JSON NOT NULL, 
    id VARCHAR(36) NOT NULL, 
    tenant VARCHAR(36) NOT NULL, 
    created VARCHAR(40) NOT NULL, 
    PRIMARY KEY (id), 
    UNIQUE (tenant, actor, route, key)
);

CREATE INDEX ix_idempotency_tenant ON idempotency (tenant);

CREATE TABLE agent_operations (
    digest VARCHAR(64) NOT NULL, 
    state VARCHAR(30) NOT NULL, 
    payload JSON NOT NULL, 
    result JSON NOT NULL, 
    task JSON NOT NULL, 
    lease_until FLOAT NOT NULL, 
    fence VARCHAR(36) NOT NULL, 
    id VARCHAR(36) NOT NULL, 
    tenant VARCHAR(36) NOT NULL, 
    created VARCHAR(40) NOT NULL, 
    PRIMARY KEY (id)
);

CREATE INDEX ix_agent_operations_tenant ON agent_operations (tenant);

ALTER TABLE "candidates" ENABLE ROW LEVEL SECURITY;

ALTER TABLE "candidates" FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_scope ON "candidates" USING (tenant = nullif(current_setting('app.tenant_id', true), '')) WITH CHECK (tenant = nullif(current_setting('app.tenant_id', true), ''));

ALTER TABLE "jobs" ENABLE ROW LEVEL SECURITY;

ALTER TABLE "jobs" FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_scope ON "jobs" USING (tenant = nullif(current_setting('app.tenant_id', true), '')) WITH CHECK (tenant = nullif(current_setting('app.tenant_id', true), ''));

ALTER TABLE "workflows" ENABLE ROW LEVEL SECURITY;

ALTER TABLE "workflows" FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_scope ON "workflows" USING (tenant = nullif(current_setting('app.tenant_id', true), '')) WITH CHECK (tenant = nullif(current_setting('app.tenant_id', true), ''));

ALTER TABLE "matches" ENABLE ROW LEVEL SECURITY;

ALTER TABLE "matches" FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_scope ON "matches" USING (tenant = nullif(current_setting('app.tenant_id', true), '')) WITH CHECK (tenant = nullif(current_setting('app.tenant_id', true), ''));

ALTER TABLE "decisions" ENABLE ROW LEVEL SECURITY;

ALTER TABLE "decisions" FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_scope ON "decisions" USING (tenant = nullif(current_setting('app.tenant_id', true), '')) WITH CHECK (tenant = nullif(current_setting('app.tenant_id', true), ''));

ALTER TABLE "proposals" ENABLE ROW LEVEL SECURITY;

ALTER TABLE "proposals" FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_scope ON "proposals" USING (tenant = nullif(current_setting('app.tenant_id', true), '')) WITH CHECK (tenant = nullif(current_setting('app.tenant_id', true), ''));

ALTER TABLE "outbox" ENABLE ROW LEVEL SECURITY;

ALTER TABLE "outbox" FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_scope ON "outbox" USING (tenant = nullif(current_setting('app.tenant_id', true), '')) WITH CHECK (tenant = nullif(current_setting('app.tenant_id', true), ''));

ALTER TABLE "inbox" ENABLE ROW LEVEL SECURITY;

ALTER TABLE "inbox" FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_scope ON "inbox" USING (tenant = nullif(current_setting('app.tenant_id', true), '')) WITH CHECK (tenant = nullif(current_setting('app.tenant_id', true), ''));

ALTER TABLE "audit" ENABLE ROW LEVEL SECURITY;

ALTER TABLE "audit" FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_scope ON "audit" USING (tenant = nullif(current_setting('app.tenant_id', true), '')) WITH CHECK (tenant = nullif(current_setting('app.tenant_id', true), ''));

ALTER TABLE "feedback" ENABLE ROW LEVEL SECURITY;

ALTER TABLE "feedback" FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_scope ON "feedback" USING (tenant = nullif(current_setting('app.tenant_id', true), '')) WITH CHECK (tenant = nullif(current_setting('app.tenant_id', true), ''));

ALTER TABLE "idempotency" ENABLE ROW LEVEL SECURITY;

ALTER TABLE "idempotency" FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_scope ON "idempotency" USING (tenant = nullif(current_setting('app.tenant_id', true), '')) WITH CHECK (tenant = nullif(current_setting('app.tenant_id', true), ''));

ALTER TABLE "agent_operations" ENABLE ROW LEVEL SECURITY;

ALTER TABLE "agent_operations" FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_scope ON "agent_operations" USING (tenant = nullif(current_setting('app.tenant_id', true), '')) WITH CHECK (tenant = nullif(current_setting('app.tenant_id', true), ''));

INSERT INTO alembic_version (version_num) VALUES ('001') RETURNING alembic_version.version_num;

COMMIT;

