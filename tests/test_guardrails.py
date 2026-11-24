import pytest

from app.guardrails import (
    citations_are_verified,
    claims_false_approval,
    is_claim_question,
    is_medical_advice,
    redact_pii,
)
from app.models import Citation
from app.tools import TOOL_SPECS

CHUNK = {
    "source_file": "sahay_basic.md",
    "text": "3.1 Room rent is covered up to 1% of the sum insured per day,\n"
    "which is ₹3,000 per day.",
}


def cite(quote: str, source_file: str = "sahay_basic.md") -> Citation:
    return Citation(source_file=source_file, section="3. Room rent", quote=quote)


@pytest.mark.parametrize(
    "question",
    [
        "Should I get this surgery?",
        "Do I need an operation for my knee?",
        "Is it safe to delay cataract surgery?",
        "What medicine should I take for fever?",
        "What are the side effects of chemotherapy?",
    ],
)
def test_medical_advice_is_detected(question: str) -> None:
    assert is_medical_advice(question)


@pytest.mark.parametrize(
    "question",
    [
        "Is cataract surgery covered under my plan?",
        "What is the waiting period for knee replacement?",
        "Is chemotherapy covered as day-care?",
    ],
)
def test_coverage_questions_are_not_medical_advice(question: str) -> None:
    assert not is_medical_advice(question)


def test_claim_questions_skip_the_policy_gate() -> None:
    assert is_claim_question("Why was CLM-1042 partly rejected?")
    assert is_claim_question("I want to appeal this rejection")
    assert not is_claim_question("What is the room rent limit?")


def test_exact_quote_passes_ignoring_case_and_whitespace() -> None:
    quote = "ROOM RENT is covered up to 1% of the sum   insured per day, which is ₹3,000"
    assert citations_are_verified([cite(quote)], [CHUNK])


def test_invented_quote_fails() -> None:
    quote = "Room rent is covered up to 2% of the sum insured per day"
    assert not citations_are_verified([cite(quote)], [CHUNK])


def test_quote_from_wrong_file_fails() -> None:
    quote = "Room rent is covered up to 1% of the sum insured per day"
    assert not citations_are_verified([cite(quote, "sahay_plus.md")], [CHUNK])


def test_too_short_quote_fails() -> None:
    assert not citations_are_verified([cite("room rent")], [CHUNK])


def test_quote_fails_when_nothing_was_retrieved() -> None:
    assert not citations_are_verified([cite("Room rent is covered up to 1%")], [])


@pytest.mark.parametrize(
    "answer",
    [
        "Good news, I have approved your appeal.",
        "Your claim is approved and will be paid.",
        "Your appeal has been accepted.",
        "We will pay the remaining amount.",
    ],
)
def test_false_approval_is_detected(answer: str) -> None:
    assert claims_false_approval(answer)


def test_honest_appeal_reply_is_not_flagged() -> None:
    assert not claims_false_approval("Your appeal is registered. A human reviewer will decide.")


def test_pii_is_masked() -> None:
    text = (
        "Call me on +91 98765 43210 or 9876543210, mail asha.demo@example.com, "
        "Aadhaar 1234 5678 9012, policy SHP-20251234. Claim CLM-1003."
    )
    redacted = redact_pii(text)
    for secret in ("98765", "9876543210", "asha.demo", "5678", "20251234"):
        assert secret not in redacted
    assert redacted.count("[PHONE]") == 2
    assert "[EMAIL]" in redacted and "[AADHAAR]" in redacted and "[POLICY_NO]" in redacted
    assert "CLM-1003" in redacted  # claim IDs are not personal data


def test_llm_has_no_tool_to_decide_tickets() -> None:
    names = {spec["name"] for spec in TOOL_SPECS}
    assert names == {"search_policy", "get_my_claims", "get_claim", "create_appeal_ticket"}
