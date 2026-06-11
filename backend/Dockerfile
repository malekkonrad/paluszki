FROM python:3.12-alpine AS base

# Install build deps for bcrypt (needs gcc) and curl for healthcheck
RUN apk add --no-cache gcc musl-dev libffi-dev curl

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# ── Cache: install deps first ─────────────────────────────────
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# ── Copy source ───────────────────────────────────────────────
COPY app/ app/
COPY main.py ./

# DB lives in /app/data (a named volume in compose; SQLite must not sit on
# a Windows bind mount — host file shares break its locking)
RUN mkdir -p data
ENV DATABASE_URL=sqlite+aiosqlite:///data/test.db

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=3s --retries=3 \
  CMD curl -f http://localhost:8000/healthz || exit 1

CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
