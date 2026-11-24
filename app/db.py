from collections.abc import Iterator
from pathlib import Path

import psycopg
from psycopg.conninfo import conninfo_to_dict, make_conninfo
from psycopg.rows import dict_row

from app.config import settings

SCHEMA_FILE = Path(__file__).with_name("schema.sql")


def connect(url: str | None = None) -> psycopg.Connection:
    """Open a connection whose rows come back as dicts."""
    return psycopg.connect(url or settings.database_url, row_factory=dict_row)


def create_database_if_missing(url: str) -> None:
    """Used for the separate test and eval databases, so they never touch dev data."""
    dbname = conninfo_to_dict(url)["dbname"]
    with psycopg.connect(make_conninfo(url, dbname="postgres"), autocommit=True) as conn:
        exists = conn.execute("SELECT 1 FROM pg_database WHERE datname = %s", (dbname,)).fetchone()
        if not exists:
            conn.execute(f'CREATE DATABASE "{dbname}"')


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


TICKET_COLUMNS = """id, member_id, claim_id, reason, status, created_at,
                    decided_by, decided_at, decision_note"""


def fetch_pending_tickets(conn: psycopg.Connection) -> list[dict]:
    return conn.execute(
        f"SELECT {TICKET_COLUMNS} FROM review_tickets WHERE status = 'pending' ORDER BY id"
    ).fetchall()


def decide_ticket(
    conn: psycopg.Connection, ticket_id: int, new_status: str, decided_by: str, note: str
) -> dict | None:
    """Decide a pending ticket. Returns None if it does not exist or was already decided.
    The `status = 'pending'` condition makes two simultaneous decisions safe: only one wins."""
    return conn.execute(
        f"""
        UPDATE review_tickets
        SET status = %s, decided_by = %s, decided_at = now(), decision_note = %s
        WHERE id = %s AND status = 'pending'
        RETURNING {TICKET_COLUMNS}
        """,
        (new_status, decided_by, note, ticket_id),
    ).fetchone()


def fetch_ticket_status(conn: psycopg.Connection, ticket_id: int) -> str | None:
    row = conn.execute("SELECT status FROM review_tickets WHERE id = %s", (ticket_id,)).fetchone()
    return row["status"] if row else None


def fetch_metrics(conn: psycopg.Connection) -> dict:
    return conn.execute(
        """
        SELECT count(*) AS requests,
               coalesce(avg(refused::int), 0) AS refusal_rate,
               coalesce(avg(latency_ms), 0) AS avg_latency_ms,
               coalesce(avg(coalesce(tokens_in, 0) + coalesce(tokens_out, 0)), 0) AS avg_tokens,
               (SELECT count(*) FROM review_tickets WHERE status = 'pending') AS pending_tickets
        FROM request_logs
        """
    ).fetchone()
