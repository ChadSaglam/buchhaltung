"""B-28 — the indexes the list queries need, and the one that was a duplicate.

Index changes are the easiest thing in a codebase to get wrong quietly: nothing
fails, a query just walks more of the table every month. These tests pin the two
things that *can* be checked without a loaded database — that the indexes the
queries were measured against still exist, and that the primary key has not
grown a second copy of itself again.

The measurements themselves are in the migration's docstring, taken from
`EXPLAIN (ANALYZE, BUFFERS)` on 800k bookings across 200 tenants. They are not
reproduced here: a timing assertion in a test suite is a flaky test, not a
performance guarantee.
"""

from __future__ import annotations

from app.models.booking import Booking
from app.models.review_queue import ReviewQueueItem
from app.models.training_job import TrainingJob


def index_columns(model, name: str) -> list[str] | None:
    for index in model.__table__.indexes:
        if index.name == name:
            return [c.name for c in index.columns]
    return None


def test_the_bookings_list_has_its_index():
    """`WHERE tenant_id = ? ORDER BY id DESC` — without this the planner walks
    the primary key backwards and discards every other tenant's rows, which gets
    worse with every tenant that signs up."""
    assert index_columns(Booking, "ix_bookings_tenant_id_id") == ["tenant_id", "id"]


def test_the_filtered_bookings_list_has_its_index():
    assert index_columns(Booking, "ix_bookings_tenant_source_id") == ["tenant_id", "source", "id"]


def test_the_review_queue_has_its_index():
    """The queue is always "this tenant, still pending, least confident first"."""
    assert index_columns(ReviewQueueItem, "ix_review_queue_tenant_status_confidence") == [
        "tenant_id",
        "status",
        "confidence",
        "created_at",
    ]


def test_the_worker_claim_has_an_index_that_matches_it():
    """Cross-tenant by design, so `(tenant_id, status)` does nothing for it.

    This is the one the roadmap got wrong: it named the index that serves
    `enqueue_training` and not the one the worker's own query needs.
    """
    assert index_columns(TrainingJob, "ix_training_jobs_status_requested") == [
        "status",
        "requested_at",
        "id",
    ]


def test_enqueue_still_has_its_own_index():
    assert index_columns(TrainingJob, "ix_training_jobs_tenant_status") == ["tenant_id", "status"]


def test_the_primary_key_has_no_second_copy_of_itself():
    """`bookings.id` had `index=True` next to `primary_key=True`.

    The primary key is already a unique B-tree on that column, so every insert
    maintained two identical indexes. Re-measured after dropping it: nothing got
    slower.
    """
    assert Booking.__table__.c["id"].primary_key
    duplicates = [index.name for index in Booking.__table__.indexes if [c.name for c in index.columns] == ["id"]]
    assert not duplicates, f"these duplicate the primary key: {duplicates}"


def test_no_model_indexes_its_own_primary_key():
    """The same mistake, anywhere else it might already exist."""
    import app.models  # noqa: F401  (registers every model)
    from app.models import Base

    offenders = []
    for table in Base.metadata.sorted_tables:
        pk = [c.name for c in table.primary_key.columns]
        for index in table.indexes:
            if [c.name for c in index.columns] == pk:
                offenders.append(f"{table.name}.{index.name}")
    assert not offenders, f"these duplicate their table's primary key: {offenders}"
