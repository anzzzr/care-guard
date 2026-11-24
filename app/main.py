from typing import Annotated

import psycopg
from fastapi import Depends, FastAPI

from app.auth import get_current_member
from app.db import fetch_claims, get_conn
from app.models import Claim, Member

app = FastAPI(title="CareGuard", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/v1/claims")
def list_my_claims(
    member: Annotated[Member, Depends(get_current_member)],
    conn: Annotated[psycopg.Connection, Depends(get_conn)],
) -> list[Claim]:
    """List the calling member's claims. No LLM involved."""
    return [Claim(**row) for row in fetch_claims(conn, member.id)]
