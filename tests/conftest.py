import os
from collections.abc import Iterator

import psycopg
import pytest
from fastapi.testclient import TestClient

from app.db import connect, create_database_if_missing, get_conn
from app.main import app
from scripts.ingest import ingest
from scripts.seed import seed

# Tests use their own database so they never wipe the dev data.
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql://careguard:careguard@localhost:5432/careguard_test"
)


@pytest.fixture(scope="session")
def seeded_db() -> str:
    create_database_if_missing(TEST_DATABASE_URL)
    with connect(TEST_DATABASE_URL) as conn:
        seed(conn)
        ingest(conn)
    return TEST_DATABASE_URL


@pytest.fixture
def db(seeded_db: str) -> Iterator[psycopg.Connection]:
    with connect(seeded_db) as conn:
        yield conn


@pytest.fixture
def client(seeded_db: str) -> Iterator[TestClient]:
    def _test_conn() -> Iterator[psycopg.Connection]:
        with connect(seeded_db) as conn:
            yield conn

    app.dependency_overrides[get_conn] = _test_conn
    yield TestClient(app)
    app.dependency_overrides.clear()
