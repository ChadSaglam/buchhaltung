-- B-24 / ADR-002: the role the application connects as.
--
-- Postgres exempts a superuser from every RLS policy and a table's owner from
-- its own. `FORCE ROW LEVEL SECURITY` fixes the second; nothing fixes the first.
-- So Row-Level Security only means anything if the app connects as a role that
-- is neither — which is what this file creates.
--
-- The compose `db` service runs everything in /docker-entrypoint-initdb.d once,
-- on an empty data directory. An existing deployment therefore has to run this
-- by hand; see docs/ADR-002-rls.md.
--
-- `chadev` (POSTGRES_USER) stays the owner and is what Alembic connects as via
-- MIGRATION_DATABASE_URL. `app_rw` owns nothing and can bypass nothing.

\set app_password `echo "$APP_DB_PASSWORD"`

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_rw') THEN
    CREATE ROLE app_rw LOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE NOINHERIT;
  END IF;
END
$$;

ALTER ROLE app_rw PASSWORD :'app_password';

GRANT CONNECT ON DATABASE chadev_buchhaltung TO app_rw;
GRANT USAGE ON SCHEMA public TO app_rw;

-- DML only. The app never creates, alters or drops anything: Alembic owns the
-- schema (AGENTS.md rule 3), and a role that cannot DDL cannot accidentally
-- become a table's owner and exempt itself from that table's policy.
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO app_rw;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO app_rw;

-- Tables a future migration creates are covered without anybody remembering.
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO app_rw;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT USAGE, SELECT ON SEQUENCES TO app_rw;
