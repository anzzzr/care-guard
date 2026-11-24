"""Request logging. Questions are PII-redacted before they are stored."""

import psycopg

from app.agent import AgentResult
from app.guardrails import redact_pii


def log_request(
    conn: psycopg.Connection,
    request_id: str,
    member_id: str,
    question: str,
    result: AgentResult,
    latency_ms: int,
) -> None:
    conn.execute(
        """
        INSERT INTO request_logs (request_id, member_id, question_redacted, tools_called,
                                  retrieval_top_score, refused, latency_ms, tokens_in, tokens_out)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            request_id,
            member_id,
            redact_pii(question),
            result.tools_used,
            result.retrieval_top_score,
            result.refused,
            latency_ms,
            result.tokens_in,
            result.tokens_out,
        ),
    )
