-- 0001_app_user.sql
-- The unprivileged role the running service connects as. RLS only holds if the
-- app cannot bypass it, so this role is non-owner, non-superuser, and NEVER gets
-- BYPASSRLS (it gets it by simply never being granted, and NOBYPASSRLS makes that
-- explicit). Table-level grants for documents/chunks live in their own migrations,
-- after the tables exist. Idempotent so CI and local re-runs are safe.
--
-- The password here is a LOCAL/CI development credential only; the hosted deploy
-- provisions app_user's password as a secret (Day 9).

-- CREATE ROLE defaults to NOSUPERUSER, NOBYPASSRLS, NOCREATEDB, NOCREATEROLE, so
-- app_user gets no bypass simply by never being granted one. (An explicit ALTER
-- of the SUPERUSER/BYPASSRLS attributes would require a true superuser, which the
-- Supabase-managed owner role is not.) The isolation test asserts these hold.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_user') THEN
        CREATE ROLE app_user LOGIN PASSWORD 'app_user_local_pw';  -- noqa
    END IF;
END $$;

GRANT CONNECT ON DATABASE postgres TO app_user;
GRANT USAGE ON SCHEMA public TO app_user;
