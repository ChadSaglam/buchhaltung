"""Alembic environment configuration."""

import asyncio
from logging.config import fileConfig

from sqlalchemy import pool, text
from sqlalchemy.ext.asyncio import async_engine_from_config

# Import the package, not a hand-maintained subset: five models were missing
# here, so autogenerate would have proposed dropping their tables.
import app.models  # noqa: F401
from alembic import context
from app.core.config import settings
from app.models.base import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


# B-24: migrations run as the table *owner*, the app as a NOBYPASSRLS role.
# `migration_database_url` falls back to DATABASE_URL outside production, so a
# dev machine and the test suite carry on with one user.
def run_migrations_offline() -> None:
    url = settings.migration_database_url
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        if connection.dialect.name == "postgresql":
            # Two API replicas starting at once must not both run `upgrade head`;
            # the lock is released with the transaction (B-41).
            connection.execute(text("SELECT pg_advisory_xact_lock(724_411)"))
        context.run_migrations()


async def run_async_migrations() -> None:
    cfg = config.get_section(config.config_ini_section, {})
    cfg["sqlalchemy.url"] = settings.migration_database_url
    connectable = async_engine_from_config(cfg, prefix="sqlalchemy.", poolclass=pool.NullPool)
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
