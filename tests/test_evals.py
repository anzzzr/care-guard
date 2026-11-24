from collections import Counter
from pathlib import Path

import yaml

from evals.run_evals import check_scenario

SCENARIOS = yaml.safe_load((Path(__file__).parent.parent / "evals" / "scenarios.yaml").read_text())
POLICY = {"sahay_basic.md": "room rent is covered up to 1% of the sum insured per day"}


def body(answer: str, **extra: object) -> dict:
    return {"answer": answer, "refused": False, "tools_used": [], "citations": [], **extra}


def test_scenario_mix_matches_the_plan() -> None:
    assert len(SCENARIOS) == 30
    assert len({s["id"] for s in SCENARIOS}) == 30
    assert Counter(s["category"] for s in SCENARIOS) == {
        "coverage": 10,
        "claim": 8,
        "out_of_policy": 4,
        "attack": 4,
        "medical": 4,
    }


def test_contains_check_ignores_commas_and_case() -> None:
    scenario = {"answer_must_contain": ["192000", ["two years", "2 years"]]}
    assert check_scenario(scenario, body("Approved ₹1,92,000 after 2 YEARS"), POLICY) == []


def test_forbidden_text_fails() -> None:
    scenario = {"answer_must_not_contain": ["CLM-1017"]}
    assert check_scenario(scenario, body("See clm-1017"), POLICY)


def test_citation_must_really_be_in_the_file() -> None:
    scenario = {"must_cite_file": "sahay_basic.md"}
    real = {
        "source_file": "sahay_basic.md",
        "section": "3",
        "quote": "Room rent is covered up to 1%",
    }
    fake = {**real, "quote": "Room rent is unlimited"}
    assert check_scenario(scenario, body("x", citations=[real]), POLICY) == []
    assert check_scenario(scenario, body("x", citations=[fake]), POLICY)
