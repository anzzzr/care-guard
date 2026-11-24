"""Print the top policy chunks for a few sample questions.

Run from the project root (after scripts.ingest):  uv run python -m scripts.search_demo
"""

from app.db import connect
from app.retrieval import search_policy

SAMPLES = [
    ("basic", "Is cataract surgery covered? Is there a waiting period?"),
    ("basic", "What is the room rent limit on my policy?"),
    ("senior", "How do I appeal a rejected claim?"),
    ("plus", "Is maternity covered and how much will you pay?"),
]


def main() -> None:
    with connect() as conn:
        for plan_id, question in SAMPLES:
            print(f"\n[{plan_id}] {question}")
            for chunk in search_policy(conn, plan_id, question):
                print(
                    f"  {chunk['score']:.3f}  {chunk['source_file']:<20} {chunk['section_title']}"
                )


if __name__ == "__main__":
    main()
