"""Checks that run in code, before or after the LLM. Each one has its own tests."""

import re

from app.models import Citation

# Fixed replies (written by us, never by the LLM)

MEDICAL_REPLY = (
    "I can't give medical advice. Please talk to your doctor about what treatment is right "
    "for you. I can help you check what your policy covers for a treatment your doctor suggests."
)
NOT_FOUND_REPLY = (
    "I couldn't find this in your policy documents, so I've raised it with our team. "
    "Someone will get back to you."
)


def appeal_registered_reply(ticket_id: int) -> str:
    return (
        f"Your appeal has been registered as ticket #{ticket_id}. A human claims officer will "
        "review it and decide within 15 days. It is not approved yet."
    )


# Medical advice (checked on the question, before the LLM)

_MEDICAL_PATTERNS = [
    r"\bshould i (get|have|go for|undergo|take|do|start|stop|try)\b",
    r"\bdo i (really )?need (a |an |the )?(surgery|operation|treatment|medicine|test)\b",
    r"\bis it (safe|risky|dangerous|necessary)\b",
    r"\bwhat (medicine|medication|treatment|drug|tablet)s? should\b",
    r"\b(recommend|suggest) (a |an |any |some )?(medicine|medication|treatment|drug|doctor)",
    r"\b(dosage|dose) of\b",
    r"\bside effects?\b",
    r"\bdiagnose\b",
    r"\bwhich is better for me\b",
]
_MEDICAL_RE = re.compile("|".join(_MEDICAL_PATTERNS), re.IGNORECASE)


def is_medical_advice(question: str) -> bool:
    return bool(_MEDICAL_RE.search(question))


# Which questions go through the retrieval gate

_CLAIM_RE = re.compile(r"\bCLM-?\d+|\bclaims?\b|\bappeal", re.IGNORECASE)


def is_claim_question(question: str) -> bool:
    """Claim/appeal questions are answered from claims data, so a weak policy match is fine."""
    return bool(_CLAIM_RE.search(question))


# Verified quotes (checked on the LLM's answer)

MIN_QUOTE_WORDS = 5


def normalize(text: str) -> str:
    """Lower-case, and turn all runs of whitespace (including newlines) into one space."""
    return " ".join(text.split()).lower()


def citations_are_verified(citations: list[Citation], retrieved_chunks: list[dict]) -> bool:
    """True only if every quote appears word for word in a chunk retrieved in this request,
    from the same source file. A quote that is too short to prove anything fails."""
    for citation in citations:
        quote = normalize(citation.quote.strip().strip("\"'“”"))
        if len(quote.split()) < MIN_QUOTE_WORDS:
            return False
        if not any(
            chunk["source_file"] == citation.source_file and quote in normalize(chunk["text"])
            for chunk in retrieved_chunks
        ):
            return False
    return True


# False approvals (checked on answers about appeals)

_APPROVAL_RE = re.compile(
    r"approved your (appeal|claim)"
    r"|(appeal|claim) (is|has been|was|will be) (now )?(approved|accepted|granted|paid|settled)"
    r"|we (have|will) (approve|pay|settle)"
    r"|i (have|will|can) (approve|accept|pay|settle)",
    re.IGNORECASE,
)


def claims_false_approval(answer: str) -> bool:
    return bool(_APPROVAL_RE.search(answer))


# PII redaction (applied before anything is logged)

_PII_PATTERNS = [
    # Order matters: the 12-digit Aadhaar check runs before the 10-digit phone check.
    ("[EMAIL]", r"[\w.+-]+@[\w-]+(\.[\w-]+)+"),
    ("[POLICY_NO]", r"\bSHP[-/ ]?\d{6,10}\b"),
    ("[AADHAAR]", r"(?<!\d)\d{4}[ -]?\d{4}[ -]?\d{4}(?!\d)"),
    ("[PHONE]", r"(?<!\d)(\+91[ -]?|0)?[6-9]\d{4}[ -]?\d{5}(?!\d)"),
]


def redact_pii(text: str) -> str:
    for mask, pattern in _PII_PATTERNS:
        text = re.sub(pattern, mask, text, flags=re.IGNORECASE)
    return text
