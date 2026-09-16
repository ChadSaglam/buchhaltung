"""Which tables the database enforces tenant isolation on (B-24, ADR-002).

The list lives here rather than only inside the migration so that a test can
hold it against the models: `test_rls.py` fails when a new table grows a
``tenant_id`` and nobody adds it here. A migration cannot introspect the models
without drifting from what it actually applied, and a list that only exists
inside one migration is a list nobody ever checks again.

Two tables carry ``tenant_id`` and deliberately have no policy:

* ``users`` — ``/login`` looks an account up by e-mail before any tenant is
  known, and the account-takeover guard in the SSO path is a cross-tenant read by
  design. Isolation there stays application-level.
* ``training_jobs`` — the worker claims the next pending job across all tenants
  and only then learns whose it is. The training itself runs inside that tenant's
  context (``training_worker._run``), so everything the job *touches* is covered.

Adding a table here is free; removing one needs a reason written down.
"""

from __future__ import annotations

#: Tables whose rows Postgres itself refuses to hand across a tenant boundary.
RLS_TABLES: tuple[str, ...] = (
    "accuracy_history",
    "audit_logs",
    "bank_transactions",
    "bookings",
    "classifier_models",
    "company_profiles",
    "corrections",
    "documents",
    "email_messages",
    "export_batches",
    "idempotency_keys",
    "invoice_positions",
    "kontenplan",
    "konto_defaults",
    "lohn_settings",
    "lohnabrechnungen",
    "mail_settings",
    "matches",
    "memory",
    "mitarbeiter",
    "review_queue_items",
    "scanner_configs",
    "training_data",
    "usage_events",
)

#: Tenant-scoped tables that are exempt, and why — see the module docstring.
RLS_EXEMPT: dict[str, str] = {
    "users": "login by e-mail and the takeover guard are cross-tenant reads by design",
    "training_jobs": "the worker claims the next job before it knows whose it is",
}

POLICY_NAME = "tenant_isolation"

#: NULL when no context is set, and `NULL = tenant_id` is never true — so a
#: missing context reads as zero rows and writes are rejected. Fail closed.
#:
#: The `nullif(…, '')` is not decoration. A GUC that was set and then RESET does
#: not come back as NULL, it comes back as the empty string, and `''::int` raises
#: `invalid input syntax for type integer` — a 500 instead of an empty list.
#: Both "never set" and "set and cleared" have to mean the same thing.
TENANT_PREDICATE = "tenant_id = nullif(current_setting('app.tenant_id', true), '')::int"


async def verify_rls_role() -> None:
    """Refuse to serve production as a role that Postgres exempts from RLS.

    This is the check that turns ADR-002 from a document into a guarantee. A
    superuser bypasses every policy, and `rolbypassrls` does the same without
    being a superuser; neither is affected by ``FORCE ROW LEVEL SECURITY``. A
    deployment that connects as one has RLS enabled, policies in place, and no
    isolation whatsoever — the worst of the three possible states, because it
    looks like the good one.

    Outside production this only warns: dev and the test suite run as one user on
    purpose, and a hard refusal there would mean nobody could run the app locally.
    """
    import logging as _logging

    from sqlalchemy import text as _text

    from app.core.config import settings
    from app.core.database import engine

    log = _logging.getLogger(__name__)
    if engine.dialect.name != "postgresql":
        return
    try:
        async with engine.connect() as conn:
            row = (
                await conn.execute(
                    _text("SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user")
                )
            ).first()
    except Exception as exc:  # a database that is not up yet is not this check's problem
        log.warning("[rls] could not verify the connected role: %s", exc)
        return

    if row is None:
        return
    is_super, bypasses = bool(row[0]), bool(row[1])
    if not (is_super or bypasses):
        return

    why = "a superuser" if is_super else "a role with BYPASSRLS"
    message = (
        f"[rls] the application connects as {why}; Row-Level Security is enabled but enforces "
        "nothing. Connect as a NOSUPERUSER NOBYPASSRLS role — see docs/ADR-002-rls.md."
    )
    if settings.is_production:
        raise RuntimeError(message)
    log.warning("%s (development: continuing anyway)", message)
