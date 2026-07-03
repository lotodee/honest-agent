-- 0002_documents.sql
-- The durable record of each ingested document, tenant-isolated at the database.
-- FORCE RLS because table owners bypass plain RLS. WITH CHECK spelled out so
-- cross-tenant WRITES are sealed too, not just reads. The (SELECT current_setting)
-- wrapper is evaluated once per query, not once per row (Supabase's top RLS perf
-- rule). Idempotent so CI and local re-runs are safe.

CREATE TABLE IF NOT EXISTS documents (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id      uuid NOT NULL,
    object_key     text NOT NULL,
    content_hash   text NOT NULL,
    status         text NOT NULL DEFAULT 'queued',
    failure_reason text,
    created_at     timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, content_hash)          -- idempotent re-upload
);
CREATE INDEX IF NOT EXISTS documents_tenant_idx ON documents (tenant_id, created_at);

ALTER TABLE documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE documents FORCE ROW LEVEL SECURITY;   -- owner does not bypass

DROP POLICY IF EXISTS tenant_isolation ON documents;
CREATE POLICY tenant_isolation ON documents
    FOR ALL TO app_user
    USING     (tenant_id = (SELECT current_setting('app.tenant_id')::uuid))
    WITH CHECK (tenant_id = (SELECT current_setting('app.tenant_id')::uuid));

GRANT SELECT, INSERT, UPDATE, DELETE ON documents TO app_user;
