import secrets
from typing import Annotated

import psycopg
from fastapi import Depends, HTTPException, status
from fastapi.security import APIKeyHeader

from app.config import settings
from app.db import get_conn
from app.models import Member

# APIKeyHeader also adds an "Authorize" button to the /docs page.
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def get_current_member(
    api_key: Annotated[str | None, Depends(api_key_header)],
    conn: Annotated[psycopg.Connection, Depends(get_conn)],
) -> Member:
    """Map the X-API-Key header to a member. The member is always decided here, in code."""
    if not api_key:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing X-API-Key header")
    row = conn.execute(
        "SELECT id, name, plan_id, policy_start_date, age FROM members WHERE api_key = %s",
        (api_key,),
    ).fetchone()
    if row is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid API key")
    return Member(**row)


admin_key_header = APIKeyHeader(name="X-Admin-Key", auto_error=False)


def require_admin(api_key: Annotated[str | None, Depends(admin_key_header)]) -> None:
    """Admin endpoints need X-Admin-Key. If no admin key is configured, nobody gets in."""
    expected = settings.admin_api_key
    if not expected or not api_key or not secrets.compare_digest(api_key, expected):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid admin key")
