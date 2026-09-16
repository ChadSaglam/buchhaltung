"""B-24 — the database refuses cross-tenant rows (ADR-002).

Two halves, because they answer different questions.

The first half runs everywhere and asks *is the list still right*: every table
that grows a ``tenant_id`` has to be either covered by a policy or listed as a
documented exemption. A table added six months from now by somebody who has
never read ADR-002 fails this test, which is the only mechanism that keeps a
hand-maintained list honest.

The second half runs on Postgres only and asks *does it actually work*. Nothing
here can be proven on SQLite, which has no RLS — and worse, the whole feature has
a failure mode where it looks enabled and enforces nothing, so "the migration
ran" is not evidence. These tests connect as a role with NOBYPASSRLS and check
what the database really returns.
"""

from __future__ import annotations

import os
import subprocess
import sys
import uuid
from pathlib import Path

import pytest
import sqlalchemy as sa

from app.core.rls import POLICY_NAME, RLS_EXEMPT, RLS_TABLES
from app.models import Base
from tests.conftest import _IS_SQLITE, TEST_DATABASE_URL

BACKEND_DIR = Path(__file__).resolve().parents[1]


# --- the list, checked against the models (runs everywhere) ----------------


def tenant_scoped_tables() -> set[str]:
    return {t.name for t in Base.metadata.sorted_tables if "tenant_id" in t.c}


def test_every_tenant_scoped_table_is_covered_or_exempt():
    forgotten = tenant_scoped_tables() - set(RLS_TABLES) - set(RLS_EXEMPT)
    assert not forgotten, (
        f"these tables carry tenant_id but no RLS policy: {sorted(forgotten)}. "
        "Add them to RLS_TABLES with a migration, or to RLS_EXEMPT with a reason."
    )


def test_the_list_has_no_tables_that_no_longer_exist():
    stale = set(RLS_TABLES) - tenant_scoped_tables()
    assert not stale, f"RLS_TABLES names tables that are gone or lost tenant_id: {sorted(stale)}"


def test_every_exemption_has_a_reason():
    assert all(reason.strip() for reason in RLS_EXEMPT.values())


def test_the_exemptions_are_the_two_we_argued_for():
    # Not a tautology: this is the line that has to change — deliberately, with
    # ADR-002 open — before a third table can opt out of tenant isolation.
    assert set(RLS_EXEMPT) == {"users", "training_jobs"}


def test_the_predicate_survives_a_reset_guc():
    from app.core.rls import TENANT_PREDICATE

    # A GUC that was set and then RESET comes back as '', not NULL, and ''::int
    # raises. Without the nullif that is a 500 where an empty list belongs.
    assert "nullif(" in TENANT_PREDICATE


# --- the real thing (Postgres only) ---------------------------------------

pg_only = pytest.mark.skipif(_IS_SQLITE, reason="RLS can only be proven on Postgres.")

APP_ROLE = "rls_test_app"
APP_PASSWORD = "rls_test_pw"


def sync_url(url: str = "") -> str:
    return (url or TEST_DATABASE_URL).replace("+asyncpg", "")


@pytest.fixture(scope="module")
def pg():
    """A migrated database with an `app_rw`-shaped role to connect as."""
    if _IS_SQLITE:
        pytest.skip("Postgres only")
    owner = sa.create_engine(sync_url(), isolation_level="AUTOCOMMIT")
    with owner.connect() as conn:
        conn.execute(sa.text("DROP SCHEMA IF EXISTS public CASCADE"))
        conn.execute(sa.text("CREATE SCHEMA public"))

    env = {**os.environ, "DATABASE_URL": TEST_DATABASE_URL}
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=BACKEND_DIR, env=env, check=True)

    database = sync_url().rsplit("/", 1)[-1].split("?")[0]
    with owner.connect() as conn:
        conn.execute(
            sa.text(
                f"DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{APP_ROLE}') "
                f"THEN CREATE ROLE {APP_ROLE} LOGIN NOSUPERUSER NOBYPASSRLS "
                f"PASSWORD '{APP_PASSWORD}'; END IF; END $$"
            )
        )
        conn.execute(sa.text(f'GRANT CONNECT ON DATABASE "{database}" TO {APP_ROLE}'))
        conn.execute(sa.text(f"GRANT USAGE ON SCHEMA public TO {APP_ROLE}"))
        conn.execute(sa.text(f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {APP_ROLE}"))
        conn.execute(sa.text(f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {APP_ROLE}"))

    # Two tenants with one booking each, written as the owner (policies do not
    # apply to it, which is exactly the point of the next few tests).
    marker = uuid.uuid4().hex[:8]
    with owner.begin() as conn:
        ids = []
        for name in (f"Eins {marker}", f"Zwei {marker}"):
            ids.append(
                conn.execute(
                    sa.text("INSERT INTO tenants (name, slug, subscription_plan) VALUES (:n, :s, 'free') RETURNING id"),
                    {"n": name, "s": name.lower().replace(" ", "-")},
                ).scalar_one()
            )
        for tenant_id in ids:
            conn.execute(
                sa.text(
                    "INSERT INTO bookings (tenant_id, datum, beschreibung, betrag) VALUES (:t, '01.01.2026', :b, 10)"
                ),
                {"t": tenant_id, "b": f"Beleg {tenant_id}"},
            )

    # The test URL already carries the owner's credentials, so swap them out
    # rather than prepending a second set.
    head, _, tail = sync_url().partition("://")
    rest = tail.split("@", 1)[-1]
    app_url = f"{head}://{APP_ROLE}:{APP_PASSWORD}@{rest}"
    app = sa.create_engine(app_url)
    yield {"owner": owner, "app": app, "tenants": ids}
    app.dispose()
    owner.dispose()


def as_tenant(engine, tenant_id: int | None, statement: str, **params):
    with engine.begin() as conn:
        if tenant_id is not None:
            conn.execute(sa.text("SELECT set_config('app.tenant_id', :t, true)"), {"t": str(tenant_id)})
        return conn.execute(sa.text(statement), params).scalar()


@pg_only
def test_the_app_role_cannot_bypass_policies(pg):
    # The check that makes every other test in this file meaningful. A superuser
    # or a BYPASSRLS role passes them all while enforcing nothing.
    bypasses = as_tenant(pg["app"], None, "SELECT rolbypassrls OR rolsuper FROM pg_roles WHERE rolname = current_user")
    assert bypasses is False


@pg_only
def test_a_tenant_sees_only_its_own_rows(pg):
    first, second = pg["tenants"]
    assert as_tenant(pg["app"], first, "SELECT count(*) FROM bookings") == 1
    assert as_tenant(pg["app"], second, "SELECT count(*) FROM bookings") == 1
    assert as_tenant(pg["app"], first, "SELECT beschreibung FROM bookings") == f"Beleg {first}"


@pg_only
def test_without_a_context_it_sees_nothing(pg):
    # Fail closed: the failure mode of a forgotten context site is an empty page,
    # not somebody else's bookkeeping.
    assert as_tenant(pg["app"], None, "SELECT count(*) FROM bookings") == 0


@pg_only
def test_a_cleared_context_is_the_same_as_no_context(pg):
    # An empty string, not NULL, is what a RESET leaves behind. Without the
    # nullif in the policy this raises `invalid input syntax for type integer`
    # and the user gets a 500 where an empty list belongs.
    with pg["app"].begin() as conn:
        conn.execute(sa.text("SELECT set_config('app.tenant_id', '', true)"))
        assert conn.execute(sa.text("SELECT count(*) FROM bookings")).scalar() == 0


@pg_only
def test_writing_into_another_tenant_is_rejected(pg):
    first, second = pg["tenants"]
    with pytest.raises(sa.exc.ProgrammingError, match="row-level security"):
        as_tenant(
            pg["app"],
            first,
            "INSERT INTO bookings (tenant_id, datum, beschreibung, betrag) "
            "VALUES (:t, '01.01.2026', 'Einbruch', 99) RETURNING id",
            t=second,
        )


@pg_only
def test_a_tenant_cannot_update_another_tenants_row(pg):
    first, second = pg["tenants"]
    changed = as_tenant(
        pg["app"],
        first,
        "WITH u AS (UPDATE bookings SET beschreibung = 'gekapert' WHERE tenant_id = :t RETURNING 1) "
        "SELECT count(*) FROM u",
        t=second,
    )
    assert changed == 0


@pg_only
def test_a_tenant_cannot_delete_another_tenants_row(pg):
    first, second = pg["tenants"]
    deleted = as_tenant(
        pg["app"],
        first,
        "WITH d AS (DELETE FROM bookings WHERE tenant_id = :t RETURNING 1) SELECT count(*) FROM d",
        t=second,
    )
    assert deleted == 0
    assert as_tenant(pg["app"], second, "SELECT count(*) FROM bookings") == 1


@pg_only
def test_every_listed_table_is_forced_not_merely_enabled(pg):
    # ENABLE alone exempts the table owner, and in a careless deployment the app
    # *is* the owner. FORCE is what closes that.
    rows = as_tenant(
        pg["app"],
        None,
        "SELECT count(*) FROM pg_class WHERE relname = ANY(:names) AND relrowsecurity AND relforcerowsecurity",
        names=list(RLS_TABLES),
    )
    assert rows == len(RLS_TABLES)


@pg_only
def test_every_listed_table_has_the_policy(pg):
    found = as_tenant(
        pg["app"],
        None,
        "SELECT count(*) FROM pg_policies WHERE schemaname = 'public' AND policyname = :p AND tablename = ANY(:names)",
        p=POLICY_NAME,
        names=list(RLS_TABLES),
    )
    assert found == len(RLS_TABLES)


@pg_only
def test_the_exempt_tables_really_are_exempt(pg):
    # Not an oversight — `users` is read by e-mail before any tenant is known,
    # and the worker claims a job before it knows whose it is.
    enabled = as_tenant(
        pg["app"],
        None,
        "SELECT count(*) FROM pg_class WHERE relname = ANY(:names) AND relrowsecurity",
        names=list(RLS_EXEMPT),
    )
    assert enabled == 0


# --- the context sites (run everywhere) ------------------------------------
#
# RLS is only as good as the four places that establish the tenant. These run on
# SQLite too, because what they check is Python, not Postgres — and a regression
# in `get_current_user` would otherwise only show up as an empty page in prod.


@pytest.fixture
def recorded_context(monkeypatch):
    """What `get_current_user` established, captured from inside the request.

    A ContextVar set inside the ASGI task does not propagate back out to the
    test — which is the property that keeps two concurrent requests apart, so it
    is not something to work around. Record the call instead.
    """
    calls: list[tuple[str, int | None]] = []
    import app.core.deps as deps

    real_set, real_bind = deps.set_tenant, deps.bind_tenant

    def spy_set(tenant_id):
        calls.append(("set", tenant_id))
        return real_set(tenant_id)

    async def spy_bind(session, tenant_id):
        calls.append(("bind", tenant_id))
        return await real_bind(session, tenant_id)

    monkeypatch.setattr(deps, "set_tenant", spy_set)
    monkeypatch.setattr(deps, "bind_tenant", spy_bind)
    return calls


async def test_an_authenticated_request_establishes_the_tenant(client, db_session, recorded_context):
    from tests.factories import auth_headers, create_tenant, create_user

    tenant = await create_tenant(db_session, name="Kontext AG")
    user = await create_user(db_session, tenant, role="owner")
    res = await client.get("/api/kontenplan/", headers=auth_headers(user))
    assert res.status_code == 200
    # Both: the contextvar for every later transaction, the bind for the one the
    # user lookup already opened.
    assert ("set", tenant.id) in recorded_context
    assert ("bind", tenant.id) in recorded_context


async def test_each_request_establishes_its_own_tenant(client, db_session, recorded_context):
    from tests.factories import auth_headers, create_tenant, create_user

    first = await create_user(db_session, await create_tenant(db_session, name="Eins"), role="owner")
    second = await create_user(db_session, await create_tenant(db_session, name="Zwei"), role="owner")
    await client.get("/api/kontenplan/", headers=auth_headers(first))
    await client.get("/api/kontenplan/", headers=auth_headers(second))
    assert [tid for kind, tid in recorded_context if kind == "set"] == [
        first.tenant_id,
        second.tenant_id,
    ]


async def test_an_unauthenticated_request_establishes_nothing(client, recorded_context):
    await client.get("/api/health")
    assert recorded_context == []


def test_tenant_scope_puts_the_previous_value_back():
    from app.core.tenant_context import current_tenant, set_tenant, tenant_scope

    set_tenant(7)
    with tenant_scope(9):
        assert current_tenant() == 9
    assert current_tenant() == 7
    set_tenant(None)


def test_every_place_that_opens_its_own_session_is_accounted_for():
    """A fifth path that opens a session has to decide what tenant it is.

    ADR-002's "harder" list: every new code path that opens a session must set
    the context. This is the grep that makes "must" enforceable — a new call site
    fails here and whoever added it has to say which tenant it runs as.
    """
    import re

    reviewed = {
        # claims the next job across tenants by design (training_jobs is exempt)
        ("app/services/training_worker.py", "_claim_next"),
        # sets the context from job.tenant_id before doing any work
        ("app/services/training_worker.py", "_run"),
        # hands a job back to the queue; touches training_jobs only
        ("app/services/training_worker.py", "_release"),
        # reads alembic_version and probes connectivity; no tenant-scoped table
        ("app/routers/health.py", "_check_db"),
        ("app/routers/health.py", "_database_status"),
    }
    pattern = re.compile(r"async with (?:self\._session_factory|async_session)\(\)")
    found: set[tuple[str, str]] = set()
    for path in sorted((BACKEND_DIR / "app").rglob("*.py")):
        if path.name == "database.py":
            continue
        enclosing = ""
        for line in path.read_text().splitlines():
            match = re.match(r"\s*(?:async )?def (\w+)", line)
            if match:
                enclosing = match.group(1)
            if pattern.search(line):
                found.add((str(path.relative_to(BACKEND_DIR)), enclosing))

    new = found - reviewed
    assert not new, (
        f"these open a database session without a reviewed tenant decision: {sorted(new)}. "
        "Set the context (app.core.tenant_context) and add it to `reviewed` with a reason."
    )
