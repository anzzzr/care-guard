"""Embed text locally and search policy chunks, limited to one plan plus common docs."""

from functools import lru_cache

import psycopg
from sentence_transformers import SentenceTransformer

EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"  # 384 dimensions
COMMON_PLAN_ID = "common"


@lru_cache(maxsize=1)
def _model() -> SentenceTransformer:
    # Loaded once per process; the first call downloads the model (~90 MB).
    return SentenceTransformer(EMBEDDING_MODEL)


def embed(texts: list[str]) -> list[list[float]]:
    """Unit-length vectors, so cosine similarity is just a dot product."""
    return _model().encode(texts, normalize_embeddings=True).tolist()


def to_pgvector(vector: list[float]) -> str:
    """pgvector accepts the text form '[0.1,0.2,...]', so no extra library is needed."""
    return "[" + ",".join(f"{x:.6f}" for x in vector) + "]"


def search_policy(conn: psycopg.Connection, plan_id: str, query: str, k: int = 4) -> list[dict]:
    """Top-k chunks from this plan's document and the common documents only.

    `plan_id` must come from the authenticated member, never from the LLM.
    `score` is cosine similarity (1 = same meaning); `<=>` is pgvector's cosine distance.
    """
    query_vector = to_pgvector(embed([query])[0])
    return conn.execute(
        """
        SELECT id, plan_id, section_title, text, source_file,
               1 - (embedding <=> %(q)s::vector) AS score
        FROM policy_chunks
        WHERE plan_id IN (%(plan)s, %(common)s)
        ORDER BY embedding <=> %(q)s::vector
        LIMIT %(k)s
        """,
        {"q": query_vector, "plan": plan_id, "common": COMMON_PLAN_ID, "k": k},
    ).fetchall()
