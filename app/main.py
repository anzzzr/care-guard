import logging
import time
import uuid
from functools import lru_cache
from pathlib import Path
from typing import Annotated

import psycopg
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app import db
from app.agent import run_agent
from app.auth import get_current_member, require_admin
from app.config import settings
from app.db import get_conn
from app.llm import GeminiClient, LLMClient, LLMError
from app.logging_utils import log_request
from app.models import AskRequest, AskResponse, Claim, DecideRequest, Member, Metrics, Ticket

logger = logging.getLogger("careguard")
app = FastAPI(title="CareGuard", version="0.1.0")

# The web UI is plain static files that call the API below from the same origin.
STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

Conn = Annotated[psycopg.Connection, Depends(get_conn)]
CurrentMember = Annotated[Member, Depends(get_current_member)]
admin_only = [Depends(require_admin)]


@lru_cache(maxsize=1)
def _gemini_client() -> GeminiClient:
    return GeminiClient(api_key=settings.gemini_api_key, model=settings.gemini_model)


def get_llm() -> LLMClient:
    """FastAPI dependency; tests replace it with a FakeLLMClient."""
    if not (settings.gemini_api_key and settings.gemini_model):
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "GEMINI_API_KEY and GEMINI_MODEL must be set"
        )
    return _gemini_client()


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/v1/me")
def who_am_i(member: CurrentMember) -> Member:
    """The member the API key belongs to (name, plan, age). No LLM involved."""
    return member


@app.get("/v1/claims")
def list_my_claims(member: CurrentMember, conn: Conn) -> list[Claim]:
    """List the calling member's claims. No LLM involved."""
    return [Claim(**row) for row in db.fetch_claims(conn, member.id)]


@app.post("/v1/ask")
def ask(
    body: AskRequest,
    member: CurrentMember,
    conn: Conn,
    llm: Annotated[LLMClient, Depends(get_llm)],
) -> AskResponse:
    """Answer a member's question from their own policy and claims."""
    request_id = uuid.uuid4().hex
    started = time.perf_counter()
    try:
        result = run_agent(conn, member, body.question, llm)
    except LLMError as exc:
        # Provider details go to the server log, not to the member.
        logger.error("LLM call failed (request %s): %s", request_id, exc)
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "The assistant is unavailable. Please try later."
        ) from exc
    latency_ms = round((time.perf_counter() - started) * 1000)
    log_request(conn, request_id, member.id, body.question, result, latency_ms)
    return AskResponse(
        answer=result.answer,
        citations=result.citations,
        tools_used=result.tools_used,
        refused=result.refused,
        ticket_id=result.ticket_id,
        request_id=request_id,
    )


@app.get("/admin/tickets", dependencies=admin_only)
def list_pending_tickets(conn: Conn) -> list[Ticket]:
    return [Ticket(**row) for row in db.fetch_pending_tickets(conn)]


@app.post("/admin/tickets/{ticket_id}/decide", dependencies=admin_only)
def decide_ticket(ticket_id: int, body: DecideRequest, conn: Conn) -> Ticket:
    """A human approves or rejects a ticket. The LLM has no tool that reaches this."""
    new_status = "approved" if body.decision == "approve" else "rejected"
    row = db.decide_ticket(conn, ticket_id, new_status, decided_by="admin", note=body.note)
    if row is None:
        current = db.fetch_ticket_status(conn, ticket_id)
        if current is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Ticket not found")
        raise HTTPException(status.HTTP_409_CONFLICT, f"Ticket already {current}")
    return Ticket(**row)


@app.get("/admin/metrics", dependencies=admin_only)
def metrics(conn: Conn) -> Metrics:
    return Metrics(**db.fetch_metrics(conn))
