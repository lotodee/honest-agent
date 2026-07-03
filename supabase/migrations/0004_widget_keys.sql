-- 0004_widget_keys.sql
-- The Day-1 widget-key lookup, now versioned. This is a GLOBAL public-identifier
-- table (a key maps to its tenant + allowed hosts); reading it crosses no tenant
-- boundary, so it carries NO row-level security and is explicitly allowlisted out
-- of the Day-2 isolation sweep. app_user only needs to read it (the visitor gate),
-- never write it (seeding runs as the owner). Idempotent.

CREATE TABLE IF NOT EXISTS widget_keys (
    key           text PRIMARY KEY,
    tenant_id     text NOT NULL,
    allowed_hosts text[] NOT NULL DEFAULT '{}'
);

GRANT SELECT ON widget_keys TO app_user;
