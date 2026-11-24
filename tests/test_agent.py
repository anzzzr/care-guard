import json
from collections.abc import Callable

import psycopg
import pytest
from fastapi.testclient import TestClient

from app.agent import FALLBACK_ANSWER, MAX_TOOL_CALLS, parse_final_answer
from app.llm import FakeLLMClient, LLMError, LLMResponse, ToolCall
from app.main import app, get_llm
from app.models import Member
from app.tools import ToolContext, run_tool

ASHA = "demo-key-m001"  # Basic plan, claims CLM-1001..1003


def tool(name: str, **args: str) -> LLMResponse:
    return LLMResponse(tool_calls=[ToolCall(name=name, args=args, id=f"call-{name}")])


def final(answer: str, citations: list[dict] | None = None) -> LLMResponse:
    return LLMResponse(text=json.dumps({"answer": answer, "citations": citations or []}))


AskFn = Callable[..., tuple[dict, FakeLLMClient]]


@pytest.fixture
def ask(client: TestClient) -> AskFn:
    def _ask(
        question: str, script: list[LLMResponse], key: str = ASHA
    ) -> tuple[dict, FakeLLMClient]:
        fake = FakeLLMClient(script)
        app.dependency_overrides[get_llm] = lambda: fake
        response = client.post("/v1/ask", json={"question": question}, headers={"X-API-Key": key})
        assert response.status_code == 200, response.text
        return response.json(), fake

    return _ask


def last_tool_result(fake: FakeLLMClient) -> dict:
    """What our code sent back to the LLM after its most recent tool call."""
    return fake.calls[-1][-1].tool_results[0].result


def test_policy_question_uses_only_own_plan_and_returns_citation(ask: AskFn) -> None:
    citation = {
        "source_file": "sahay_basic.md",
        "section": "3. Room rent and ICU limits",
        "quote": "Room rent is covered up to 1% of the sum insured per day",
    }
    body, fake = ask(
        "What is the room rent limit?",
        [tool("search_policy", query="room rent limit"), final("₹3,000 per day.", [citation])],
    )
    assert body["tools_used"] == ["search_policy"]
    assert body["refused"] is False
    assert body["citations"] == [citation]
    assert body["request_id"]
    files = {r["source_file"] for r in last_tool_result(fake)["results"]}
    assert files <= {"sahay_basic.md", "claims_process.md"}


def test_get_my_claims_returns_only_the_callers_claims(ask: AskFn) -> None:
    _, fake = ask("Show my claims", [tool("get_my_claims"), final("You have 3 claims.")])
    ids = {c["id"] for c in last_tool_result(fake)["claims"]}
    assert ids == {"CLM-1001", "CLM-1002", "CLM-1003"}


def test_another_members_claim_is_not_found(ask: AskFn) -> None:
    # CLM-1017 exists but belongs to M006.
    _, fake = ask("Tell me about CLM-1017", [tool("get_claim", claim_id="CLM-1017"), final("x")])
    assert last_tool_result(fake) == {"error": "Claim not found."}


def test_llm_cannot_pass_a_member_id(ask: AskFn) -> None:
    _, fake = ask(
        "Show claims of M006", [tool("get_my_claims", member_id="M006"), final("Not possible.")]
    )
    result = last_tool_result(fake)
    assert "error" in result and "claims" not in result


def test_appeal_creates_a_pending_ticket(ask: AskFn, db: psycopg.Connection) -> None:
    body, _ = ask(
        "I want to appeal CLM-1002",
        [
            tool("create_appeal_ticket", claim_id="CLM-1002", reason="I had cataract earlier"),
            final("Your appeal is registered. A human reviewer will decide."),
        ],
    )
    assert body["ticket_id"] is not None
    row = db.execute(
        "SELECT member_id, claim_id, status FROM review_tickets WHERE id = %s",
        (body["ticket_id"],),
    ).fetchone()
    assert row == {"member_id": "M001", "claim_id": "CLM-1002", "status": "pending"}


def test_appeal_on_another_members_claim_creates_nothing(
    ask: AskFn, db: psycopg.Connection
) -> None:
    count_sql = "SELECT count(*) AS n FROM review_tickets WHERE claim_id = 'CLM-1017'"
    before = db.execute(count_sql).fetchone()["n"]
    body, fake = ask(
        "Appeal CLM-1017",
        [tool("create_appeal_ticket", claim_id="CLM-1017", reason="x"), final("Not found.")],
    )
    assert body["ticket_id"] is None
    assert last_tool_result(fake) == {"error": "Claim not found."}
    assert db.execute(count_sql).fetchone()["n"] == before


def test_tool_calls_are_capped(ask: AskFn) -> None:
    script = [tool("search_policy", query="anything")] * (MAX_TOOL_CALLS + 1)
    body, fake = ask("Loop forever", script)
    assert len(body["tools_used"]) == MAX_TOOL_CALLS
    assert len(fake.calls) == MAX_TOOL_CALLS + 1
    assert body["refused"] is True
    assert body["answer"] == FALLBACK_ANSWER


def test_answer_that_is_not_json_falls_back(ask: AskFn) -> None:
    body, _ = ask("Hi", [LLMResponse(text="Sure, your claim is approved!")])
    assert body["refused"] is True
    assert body["answer"] == FALLBACK_ANSWER


def test_ask_without_api_key_never_calls_the_llm(client: TestClient) -> None:
    fake = FakeLLMClient([])
    app.dependency_overrides[get_llm] = lambda: fake
    assert client.post("/v1/ask", json={"question": "hi"}).status_code == 401
    assert fake.calls == []


def test_unknown_tool_is_an_error_not_a_crash(db: psycopg.Connection) -> None:
    member = Member(id="M001", name="x", plan_id="basic", policy_start_date="2025-04-01", age=34)
    result = run_tool(ToolContext(conn=db, member=member), ToolCall(name="delete_claims", args={}))
    assert result == {"error": "Unknown tool: delete_claims"}


def test_fenced_json_is_accepted() -> None:
    parsed = parse_final_answer('```json\n{"answer": "ok", "citations": []}\n```')
    assert parsed is not None and parsed.answer == "ok"


class FailingLLM:
    def generate(self, system: str, messages: list, tools: list) -> LLMResponse:
        raise LLMError("Gemini error 403: free tier not available")


def test_llm_provider_error_becomes_clean_503(client: TestClient) -> None:
    app.dependency_overrides[get_llm] = FailingLLM
    response = client.post("/v1/ask", json={"question": "hi"}, headers={"X-API-Key": ASHA})
    assert response.status_code == 503
    assert "403" not in response.text  # provider details are not shown to members
