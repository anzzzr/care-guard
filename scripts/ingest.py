"""Split policy markdown files into one chunk per '## ' section, embed them, store them.

Run from the project root (after scripts.seed):  uv run python -m scripts.ingest

Re-running replaces all chunks, so the table always matches the files on disk.
"""

import hashlib
from pathlib import Path

import psycopg

from app.db import connect
from app.retrieval import COMMON_PLAN_ID, embed, to_pgvector

POLICY_DIR = Path(__file__).resolve().parent.parent / "data" / "policies"
COMMON_FILES = {"claims_process.md"}  # shown to members of every plan


def split_sections(markdown: str) -> tuple[str, list[tuple[str, str]]]:
    """Return (document title, [(section title, section body), ...]).

    Text before the first '## ' heading (title and disclaimer) is not a chunk.
    """
    doc_title = ""
    sections: list[tuple[str, list[str]]] = []
    for line in markdown.splitlines():
        if line.startswith("# "):
            doc_title = line[2:].strip()
        elif line.startswith("## "):
            sections.append((line[3:].strip(), []))
        elif sections:
            sections[-1][1].append(line)
    return doc_title, [(title, "\n".join(body).strip()) for title, body in sections]


def plan_for_file(file_name: str, plan_by_file: dict[str, str]) -> str:
    """Fail loudly for an unknown file instead of showing it to every member."""
    if file_name in COMMON_FILES:
        return COMMON_PLAN_ID
    if file_name in plan_by_file:
        return plan_by_file[file_name]
    raise ValueError(f"{file_name} is not a plan document or a common document")


def ingest(conn: psycopg.Connection, policy_dir: Path = POLICY_DIR) -> int:
    plan_by_file = {
        row["policy_doc_file"]: row["id"]
        for row in conn.execute("SELECT id, policy_doc_file FROM plans").fetchall()
    }
    rows = []
    for path in sorted(policy_dir.glob("*.md")):
        plan_id = plan_for_file(path.name, plan_by_file)
        doc_title, sections = split_sections(path.read_text(encoding="utf-8"))
        for section_title, text in sections:
            sha256 = hashlib.sha256(text.encode("utf-8")).hexdigest()
            # The document title is embedded too, so "Basic Plan" in a question helps match.
            rows.append((plan_id, section_title, text, path.name, sha256, doc_title))

    vectors = embed([f"{r[5]}\n{r[1]}\n{r[2]}" for r in rows])
    conn.execute("DELETE FROM policy_chunks")
    with conn.cursor() as cur:
        cur.executemany(
            """
            INSERT INTO policy_chunks (plan_id, section_title, text, source_file, sha256, embedding)
            VALUES (%s, %s, %s, %s, %s, %s::vector)
            """,
            [(*r[:5], to_pgvector(v)) for r, v in zip(rows, vectors, strict=True)],
        )
    return len(rows)


def main() -> None:
    with connect() as conn:
        count = ingest(conn)
    print(f"Stored {count} policy chunks.")


if __name__ == "__main__":
    main()
