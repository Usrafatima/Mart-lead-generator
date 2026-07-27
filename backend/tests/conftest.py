"""
Shared test fixtures for the Database & Google Sheets module.

Tests run against in-memory SQLite rather than Postgres so `pytest` works with
no services running. The module's Postgres-specific pieces (pg_trgm, the
lead_ref sequence) degrade gracefully by design, and the fixtures below patch
over the two type differences.
"""

import os
import sys
import uuid
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Make `app` importable when pytest is run from the repo root as well as backend/.
BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

# Must be set before app.core.config is imported, or Settings() picks up a
# Postgres URL and the engine tries to connect at import time.
os.environ.setdefault("DATABASE_URL", "sqlite://")

from sqlalchemy.dialects.postgresql import UUID as PG_UUID  # noqa: E402
from sqlalchemy.types import CHAR, TypeDecorator  # noqa: E402


class _SqliteUUID(TypeDecorator):
    """Store UUIDs as 36-char strings; SQLite has no native UUID type."""

    impl = CHAR(36)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        return str(value) if value is not None else None

    def process_result_value(self, value, dialect):
        return uuid.UUID(value) if value is not None else None


@pytest.fixture(scope="session", autouse=True)
def _patch_uuid_for_sqlite():
    """Teach the PG UUID column type to render on SQLite for the test run."""
    PG_UUID.load_dialect_impl = lambda self, dialect: (
        dialect.type_descriptor(_SqliteUUID())
        if dialect.name == "sqlite"
        else dialect.type_descriptor(self)
    )
    yield


@pytest.fixture()
def db(_patch_uuid_for_sqlite):
    """A fresh, empty database per test."""
    from app.core.database import Base
    from app.models import business, lead, sync_run, user  # noqa: F401

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)

    session = sessionmaker(bind=engine, autoflush=False, autocommit=False)()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)


@pytest.fixture()
def make_business():
    """Build an unsaved Business with sensible defaults."""
    from app.models.business import Business

    def _make(name: str, city: str = "Bristol", **kwargs) -> Business:
        return Business(name=name, city=city, **kwargs)

    return _make
