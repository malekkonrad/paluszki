FROM python:3.12-slim AS base

# Runtime libs for OpenCV/MediaPipe (libGL, glib) and curl for the healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# ── Cache: install deps first ─────────────────────────────────
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# ── Copy source + inference artifacts ─────────────────────────
COPY src/ src/
COPY configs/ configs/
COPY artifacts/asl_citizen100/best_model.pt artifacts/asl_citizen100/label_map.json artifacts/asl_citizen100/

# Docker-specific serve config (Ollama reached at http://ollama:11434)
ENV PALUSZKI_SERVE_CONFIG=configs/serve.docker.yaml

EXPOSE 8001

# start-period is generous: the first session load pulls in torch + MediaPipe
HEALTHCHECK --interval=10s --timeout=3s --retries=3 --start-period=30s \
  CMD curl -f http://localhost:8001/healthz || exit 1

CMD ["uv", "run", "uvicorn", "src.serve.http_app:app", "--host", "0.0.0.0", "--port", "8001"]
