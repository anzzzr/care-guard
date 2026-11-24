import hashlib

import psycopg
import pytest

from app.retrieval import search_policy
from scripts.ingest import plan_for_file, split_sections

PLUS_ONLY_QUESTIONS = [
    "Is maternity covered? How much for a caesarean delivery?",
    "Is there no room rent limit so I can take a single private room?",
    "Do I get a free annual health check-up?",
    "Harbourview Heart Institute Mumbai cashless",
]


def test_split_sections_one_chunk_per_h2_and_skips_preamble() -> None:
    md = "# Doc\n\n> disclaimer\n\n## 1. First\n\nalpha\n\n## 2. Second\n\nbeta\n"
    title, sections = split_sections(md)
    assert title == "Doc"
    assert sections == [("1. First", "alpha"), ("2. Second", "beta")]


def test_unknown_policy_file_is_refused() -> None:
    with pytest.raises(ValueError):
        plan_for_file("sahay_gold.md", {"sahay_basic.md": "basic"})


def test_chunks_stored_with_plan_and_sha256(db: psycopg.Connection) -> None:
    chunks = db.execute("SELECT plan_id, source_file, text, sha256 FROM policy_chunks").fetchall()
    by_file: dict[str, set[str]] = {}
    for c in chunks:
        by_file.setdefault(c["source_file"], set()).add(c["plan_id"])
        assert c["sha256"] == hashlib.sha256(c["text"].encode("utf-8")).hexdigest()
    assert by_file == {
        "sahay_basic.md": {"basic"},
        "sahay_plus.md": {"plus"},
        "sahay_senior.md": {"senior"},
        "claims_process.md": {"common"},
    }


@pytest.mark.parametrize("question", PLUS_ONLY_QUESTIONS)
def test_basic_member_never_gets_plus_chunks(db: psycopg.Connection, question: str) -> None:
    # k=100 is more than the total number of chunks, so this checks everything reachable.
    results = search_policy(db, "basic", question, k=100)
    assert results
    assert {r["plan_id"] for r in results} <= {"basic", "common"}
    assert "sahay_plus.md" not in {r["source_file"] for r in results}


def test_each_plan_only_sees_its_own_document(db: psycopg.Connection) -> None:
    for plan_id in ("basic", "plus", "senior"):
        files = {r["source_file"] for r in search_policy(db, plan_id, "waiting period", k=100)}
        assert files == {f"sahay_{plan_id}.md", "claims_process.md"}


def test_top_result_is_the_relevant_section(db: psycopg.Connection) -> None:
    top = search_policy(db, "basic", "What is the room rent limit on my policy?")[0]
    assert top["section_title"] == "3. Room rent and ICU limits"
    assert 0 < top["score"] <= 1
