"""Tools the LLM may call. None of them takes a member_id: it comes from ToolContext,
which is built from the X-API-Key, so the LLM cannot ask about another member."""

from dataclasses import dataclass, field
from typing import Any

import psycopg
from fastapi.encoders import jsonable_encoder

from app import db, retrieval
from app.llm import ToolCall
from app.models import Member


@dataclass
class ToolContext:
    conn: psycopg.Connection
    member: Member
    # Everything search_policy returned in this request, by chunk id (used to verify quotes).
    retrieved_chunks: dict[int, dict] = field(default_factory=dict)
    ticket_id: int | None = None


def search_policy(ctx: ToolContext, query: str) -> dict:
    chunks = retrieval.search_policy(ctx.conn, ctx.member.plan_id, query)
    for chunk in chunks:
        ctx.retrieved_chunks[chunk["id"]] = chunk
    return {
        "results": [
            {
                "source_file": c["source_file"],
                "section": c["section_title"],
                "text": c["text"],
                "score": round(c["score"], 3),
            }
            for c in chunks
        ]
    }


def get_my_claims(ctx: ToolContext) -> dict:
    return {"claims": db.fetch_claims(ctx.conn, ctx.member.id)}


def get_claim(ctx: ToolContext, claim_id: str) -> dict:
    claim = db.fetch_claim(ctx.conn, ctx.member.id, claim_id.strip().upper())
    return {"claim": claim} if claim else {"error": "Claim not found."}


def create_appeal_ticket(ctx: ToolContext, claim_id: str, reason: str) -> dict:
    claim = db.fetch_claim(ctx.conn, ctx.member.id, claim_id.strip().upper())
    if claim is None:
        return {"error": "Claim not found."}
    ctx.ticket_id = db.create_ticket(ctx.conn, ctx.member.id, claim["id"], reason)
    return {
        "ticket_id": ctx.ticket_id,
        "status": "pending",
        "note": "A human claims officer will review this appeal. It is not approved yet.",
    }


def _string_param(description: str) -> dict:
    return {"type": "string", "description": description}


TOOL_SPECS: list[dict] = [
    {
        "name": "search_policy",
        "description": "Search the member's own policy wording and the common claims-process "
        "guide. Use for any question about cover, exclusions, limits, waiting periods, "
        "co-payment, network hospitals or how claims and appeals work.",
        "parameters": {
            "type": "object",
            "properties": {"query": _string_param("What to look for, in plain words.")},
            "required": ["query"],
        },
    },
    {
        "name": "get_my_claims",
        "description": "List all claims of the member who is asking.",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "get_claim",
        "description": "Get one of the member's claims by its ID, e.g. CLM-1001.",
        "parameters": {
            "type": "object",
            "properties": {"claim_id": _string_param("The claim ID, e.g. CLM-1001.")},
            "required": ["claim_id"],
        },
    },
    {
        "name": "create_appeal_ticket",
        "description": "Register the member's appeal against a claim decision. It creates a "
        "pending ticket for a human reviewer; it does not approve anything.",
        "parameters": {
            "type": "object",
            "properties": {
                "claim_id": _string_param("The claim being appealed, e.g. CLM-1001."),
                "reason": _string_param("Why the member disagrees, in their words."),
            },
            "required": ["claim_id", "reason"],
        },
    },
]

TOOL_FUNCTIONS = {
    "search_policy": search_policy,
    "get_my_claims": get_my_claims,
    "get_claim": get_claim,
    "create_appeal_ticket": create_appeal_ticket,
}
_SPEC_BY_NAME = {spec["name"]: spec for spec in TOOL_SPECS}


def run_tool(ctx: ToolContext, call: ToolCall) -> dict[str, Any]:
    """Run one tool call from the LLM. Bad calls become an error result, never an exception."""
    spec = _SPEC_BY_NAME.get(call.name)
    if spec is None:
        return {"error": f"Unknown tool: {call.name}"}
    allowed = set(spec["parameters"]["properties"])
    required = set(spec["parameters"].get("required", []))
    given = set(call.args)
    # An extra argument such as member_id is refused, not silently ignored.
    if not given <= allowed or not required <= given:
        return {"error": f"Invalid arguments for {call.name}. Expected: {sorted(allowed)}"}
    if not all(isinstance(v, str) and v.strip() for v in call.args.values()):
        return {"error": f"Arguments for {call.name} must be non-empty strings."}
    return jsonable_encoder(TOOL_FUNCTIONS[call.name](ctx, **call.args))
