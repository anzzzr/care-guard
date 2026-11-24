from collections.abc import Iterator
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

from app.config import settings

SCHEMA_FILE = Path(__file__).with_name("schema.sql")


def connect(url: str | None = None) -> psycopg.Connection:
    """Open a connection whose rows come back as dicts."""
    return psycopg.connect(url or settings.database_url, row_factory=dict_row)


def create_tables(conn: psycopg.Connection) -> None:
    conn.execute(SCHEMA_FILE.read_text())


def get_conn() -> Iterator[psycopg.Connection]:
    """FastAPI dependency: one connection per request, committed and closed afterwards."""
    with connect() as conn:
        yield conn


def fetch_claims(conn: psycopg.Connection, member_id: str) -> list[dict]:
    return conn.execute(
        """
        SELECT id, hospital, procedure, amount_claimed, amount_approved,
               status, rejection_reason, submitted_on
        FROM claims
        WHERE member_id = %s
        ORDER BY submitted_on DESC, id
        """,
        (member_id,),
    ).fetchall()
