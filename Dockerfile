FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.12.5 /uv /usr/local/bin/uv

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    HF_HOME=/app/.cache/huggingface \
    PATH="/app/.venv/bin:$PATH"

# Dependencies first, so code changes don't reinstall them (Linux gets CPU-only torch).
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

# Bake the embedding model into the image so containers never download it at start-up.
RUN python -c "from sentence_transformers import SentenceTransformer; \
SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')"
ENV HF_HUB_OFFLINE=1

COPY app ./app
COPY scripts ./scripts
COPY data ./data

RUN useradd --create-home careguard
USER careguard

EXPOSE 8000
# Create tables + demo data if the database is empty, sync policy chunks, then serve.
# PORT is set by hosts like Render and Cloud Run.
CMD ["sh", "-c", "python -m scripts.seed --if-empty && python -m scripts.ingest && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
