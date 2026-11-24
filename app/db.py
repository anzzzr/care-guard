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


CLAIM_COLUMNS = """id, hospital, procedure, amount_claimed, amount_approved,
                   status, rejection_reason, submitted_on"""


def fetch_claims(conn: psycopg.Connection, member_id: str) -> list[dict]:
    return conn.execute(
        f"SELECT {CLAIM_COLUMNS} FROM claims WHERE member_id = %s ORDER BY submitted_on DESC, id",
        (member_id,),
    ).fetchall()


def fetch_claim(conn: psycopg.Connection, member_id: str, claim_id: str) -> dict | None:
    """One claim, only if it belongs to this member. Someone else's claim looks the same
    as a claim that does not exist, so nobody can discover other members' claim IDs."""
    return conn.execute(
        f"SELECT {CLAIM_COLUMNS} FROM claims WHERE id = %s AND member_id = %s",
        (claim_id, member_id),
    ).fetchone()


def create_ticket(
    conn: psycopg.Connection, member_id: str, claim_id: str | None, reason: str
) -> int:
    """New review ticket, always 'pending'. Only an admin endpoint may change its status."""
    return conn.execute(
        "INSERT INTO review_tickets (member_id, claim_id, reason) VALUES (%s, %s, %s) RETURNING id",
        (member_id, claim_id, reason),
    ).fetchone()["id"]
