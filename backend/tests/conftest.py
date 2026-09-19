from __future__ import annotations

import os
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool, StaticPool

os.environ.setdefault("ENV", "test")
# B-34: model blobs refuse to sign with the default secret; tests need a real-looking one.
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-pytest-only-0123456789abcdef")
os.environ.setdefault(
    "JWT_SECRET", os.environ["SECRET_KEY"]
)  # JWT_SECRET (also from backend/.env) wins over SECRET_KEY

from app.core.config import settings
from app.core.database import get_db
from app.core.rate_limit import limiter
from app.main import app
from app.models.base import Base
from app.services.storage import reset_storage

TEST_DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://chadev:chadev@127.0.0.1:5432/buchhaltung_test",
)

_IS_SQLITE = TEST_DATABASE_URL.startswith("sqlite")


def _create_test_engine():
    if _IS_SQLITE:
        return create_async_engine(
            TEST_DATABASE_URL,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
    return create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)


@pytest.fixture(autouse=True)
def storage_dir(tmp_path, monkeypatch):
    """Every test gets a throw-away LocalStorage root — nothing is written under /app/data."""
    root = tmp_path / "storage"
    monkeypatch.setattr(settings, "STORAGE_BACKEND", "local")
    monkeypatch.setattr(settings, "STORAGE_LOCAL_DIR", str(root))
    reset_storage()
    yield root
    reset_storage()


@pytest_asyncio.fixture
async def engine():
    eng = _create_test_engine()
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await eng.dispose()


@pytest_asyncio.fixture
async def db_session(engine) -> AsyncIterator[AsyncSession]:
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncIterator[AsyncClient]:
    async def _override_get_db() -> AsyncIterator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    # The in-memory rate limiter is process-global; every test starts with a clean window.
    limiter.reset()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


class StatementCounter:
    """Counts the SQL an engine actually sends, by table."""

    def __init__(self) -> None:
        self.statements: list[str] = []

    def against(self, table: str) -> int:
        return sum(1 for s in self.statements if table in s.lower())

    def __len__(self) -> int:
        return len(self.statements)


@pytest.fixture
def counted(engine):
    counter = StatementCounter()

    def _record(conn, cursor, statement, parameters, context, executemany):
        counter.statements.append(statement)

    event.listen(engine.sync_engine, "before_cursor_execute", _record)
    yield counter
    event.remove(engine.sync_engine, "before_cursor_execute", _record)
