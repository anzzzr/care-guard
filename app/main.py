import logging
import uuid
from functools import lru_cache
from typing import Annotated

import psycopg
from fastapi import Depends, FastAPI, HTTPException, status

from app.agent import run_agent
from app.auth import get_current_member
from app.config import settings
from app.db import fetch_claims, get_conn
from app.llm import GeminiClient, LLMClient, LLMError
from app.models import AskRequest, AskResponse, Claim, Member

logger = logging.getLogger("careguard")
app = FastAPI(title="CareGuard", version="0.1.0")


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


@app.post("/v1/ask")
def ask(
    body: AskRequest,
    member: Annotated[Member, Depends(get_current_member)],
    conn: Annotated[psycopg.Connection, Depends(get_conn)],
    llm: Annotated[LLMClient, Depends(get_llm)],
) -> AskResponse:
    """Answer a member's question from their own policy and claims."""
    try:
        result = run_agent(conn, member, body.question, llm)
    except LLMError as exc:
        # Provider details go to the server log, not to the member.
        logger.error("LLM call failed: %s", exc)
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "The assistant is unavailable. Please try later."
        ) from exc
    return AskResponse(
        answer=result.answer,
        citations=result.citations,
        tools_used=result.tools_used,
        refused=result.refused,
        ticket_id=result.ticket_id,
        request_id=uuid.uuid4().hex,
    )
