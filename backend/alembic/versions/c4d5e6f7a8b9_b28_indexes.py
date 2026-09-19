"""B-28: the indexes the list queries actually need

Revision ID: c4d5e6f7a8b9
Revises: b3c4d5e6f7a8
Create Date: 2026-09-16

Every one of these was chosen from an `EXPLAIN (ANALYZE, BUFFERS)` against a
seeded database, not from reading the code. Measurements, before → after:

* `bookings` list for one tenant, newest first — 800k rows over 200 tenants:
  438 buffers with 23'053 rows thrown away by a filter → 90 buffers, an Index
  Cond, and flat instead of linear in the number of tenants;
* the same list filtered by `source`: 327 buffers, 16'715 discarded → 88, none;
* the review queue (`tenant`, still pending, least confident first) over 60k
  rows: 1'603 buffers, 5'379 discarded → 521, none;
* the worker claiming the oldest pending job: 263 buffers and a 3'926-row sort
  → an **Index Only Scan**, 4 buffers, `Heap Fetches: 0`.

That last one is why `training_jobs` gets two indexes rather than the one the
roadmap named. `(tenant_id, status)` answers `enqueue_training`'s "does this
tenant already have one queued?", but the worker's claim is cross-tenant by
design (B-24 exempts the table for exactly that reason) and needs
`(status, requested_at, id)`.

Three indexes are dropped, all of them a second B-tree on a column the primary
key already indexes uniquely: `ix_bookings_id`, `ix_kontenplan_id` and
`ix_konto_defaults_id`. Every insert maintained two identical structures for
nothing. Re-measured after dropping the bookings one — no query got slower.

The first was in the roadmap; the other two were found by writing the general
version of the test ("no model indexes its own primary key") instead of the
specific one.

Concurrently is deliberately *not* used: these tables are small enough today
that the lock is measured in milliseconds, and `CREATE INDEX CONCURRENTLY`
cannot run inside Alembic's transaction.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "c4d5e6f7a8b9"
down_revision: str | None = "b3c4d5e6f7a8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NEW_INDEXES = (
    ("ix_bookings_tenant_id_id", "bookings", ["tenant_id", "id"]),
    ("ix_bookings_tenant_source_id", "bookings", ["tenant_id", "source", "id"]),
    (
        "ix_review_queue_tenant_status_confidence",
        "review_queue_items",
        ["tenant_id", "status", "confidence", "created_at"],
    ),
    ("ix_training_jobs_tenant_status", "training_jobs", ["tenant_id", "status"]),
    ("ix_training_jobs_status_requested", "training_jobs", ["status", "requested_at", "id"]),
)


#: Each of these indexes exactly one column that its table's primary key already
#: indexes uniquely.
DUPLICATE_PK_INDEXES = (
    ("ix_bookings_id", "bookings"),
    ("ix_kontenplan_id", "kontenplan"),
    ("ix_konto_defaults_id", "konto_defaults"),
)


def upgrade() -> None:
    for name, table, columns in NEW_INDEXES:
        op.create_index(name, table, columns, unique=False)
    for name, table in DUPLICATE_PK_INDEXES:
        op.drop_index(name, table_name=table, if_exists=True)


def downgrade() -> None:
    for name, table in DUPLICATE_PK_INDEXES:
        op.create_index(name, table, ["id"], unique=False)
    for name, table, _columns in reversed(NEW_INDEXES):
        op.drop_index(name, table_name=table, if_exists=True)
