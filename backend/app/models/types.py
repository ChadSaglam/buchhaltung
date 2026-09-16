"""Column types with a domain (B-51).

``Chf`` is the money column of this app. Three jobs:

* **store exactly** — ``Numeric(12, 2)`` on PostgreSQL, so a franc is a franc and
  not ``0.6000000000000001`` after three additions;
* **round on the way in** — every value goes through ``round_chf`` (half-up on
  the decimal text) before it reaches the database, so nobody can store
  ``12.345`` and have the export decide what it means;
* **stay float in Python** — the services, schemas and exports all work in
  float and convert at the edges. Handing them ``Decimal`` from one dialect and
  ``float`` from another is how you get ``unsupported operand type`` in
  production and nowhere else.

SQLite keeps ``Float``: it has no native decimal, and SQLAlchemy would warn on
every read. Dev and tests run there, money is decided on PostgreSQL.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import Float, Numeric
from sqlalchemy.types import TypeDecorator

MONEY_PRECISION = 12
MONEY_SCALE = 2


class Chf(TypeDecorator):
    """A CHF amount: exact in the database, rounded on insert, float in Python."""

    impl = Numeric(MONEY_PRECISION, MONEY_SCALE, asdecimal=False)
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(Numeric(MONEY_PRECISION, MONEY_SCALE, asdecimal=True))
        return dialect.type_descriptor(Float())

    def process_bind_param(self, value: Any, dialect) -> Any:
        if value is None or value == "":
            return None
        from app.services.export import round_chf  # local: models must not import services at module level

        rounded = round_chf(value)
        return rounded if dialect.name == "postgresql" else float(rounded)

    def process_result_value(self, value: Any, dialect) -> float | None:
        return None if value is None else float(value)
