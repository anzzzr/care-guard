from pathlib import Path

import psycopg

POLICY_DIR = Path(__file__).resolve().parent.parent / "data" / "policies"


def test_every_plan_has_its_policy_file_and_members(db: psycopg.Connection) -> None:
    plans = db.execute("SELECT id, policy_doc_file FROM plans").fetchall()
    assert {p["id"] for p in plans} == {"basic", "plus", "senior"}
    for plan in plans:
        assert (POLICY_DIR / plan["policy_doc_file"]).is_file()
        count = db.execute(
            "SELECT count(*) AS n FROM members WHERE plan_id = %s", (plan["id"],)
        ).fetchone()["n"]
        assert count >= 3
    assert (POLICY_DIR / "claims_process.md").is_file()


def test_claims_cover_every_status_with_consistent_amounts(db: psycopg.Connection) -> None:
    claims = db.execute("SELECT * FROM claims").fetchall()
    assert len(db.execute("SELECT id FROM members").fetchall()) == 10
    assert 25 <= len(claims) <= 35
    assert {c["status"] for c in claims} == {
        "approved",
        "partially_approved",
        "rejected",
        "pending",
    }
    for c in claims:
        if c["status"] == "pending":
            assert c["amount_approved"] is None
        else:
            assert 0 <= c["amount_approved"] <= c["amount_claimed"]
        # Every rejection or deduction must explain itself; nothing else should.
        needs_reason = c["status"] in ("rejected", "partially_approved")
        assert bool(c["rejection_reason"]) == needs_reason, c["id"]
