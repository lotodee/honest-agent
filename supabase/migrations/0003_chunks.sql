-- 0003_chunks.sql
-- The durable per-chunk content AND its embedding vector. Postgres is the source
-- of truth (locked decision 3): storing the vector here means Weaviate is a
-- rebuildable derived index, reindexable with no re-upload and no re-embedding.
-- pgvector ships with Supabase; the single committed column type is vector(768).
-- If the real embedding model's dimensionality differs, that is an explicit future
-- migration, never a silent runtime branch. Same forced-RLS shape as documents.
-- Idempotent so CI and local re-runs are safe.

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS chunks (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id    uuid NOT NULL,
    document_id  uuid NOT NULL,
    chunk_index  int NOT NULL,
    text         text NOT NULL,
    section      text,
    content_hash text NOT NULL,
    embedding    vector(768) NOT NULL,
    created_at   timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, document_id, chunk_index)
);
CREATE INDEX IF NOT EXISTS chunks_tenant_doc_idx ON chunks (tenant_id, document_id);

ALTER TABLE chunks ENABLE ROW LEVEL SECURITY;
ALTER TABLE chunks FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS tenant_isolation ON chunks;
CREATE POLICY tenant_isolation ON chunks
    FOR ALL TO app_user
    USING     (tenant_id = (SELECT current_setting('app.tenant_id')::uuid))
    WITH CHECK (tenant_id = (SELECT current_setting('app.tenant_id')::uuid));

GRANT SELECT, INSERT, UPDATE, DELETE ON chunks TO app_user;
