# MeetFlow — Backend

FastAPI backend for the MeetFlow video chat application.

## Requirements

- Python ≥ 3.11
- [uv](https://docs.astral.sh/uv/) package manager

## Running locally

```bash
cd backend
uv sync
uv run uvicorn app.main:app --reload --port 8000
```

Swagger UI: [http://localhost:8000/docs](http://localhost:8000/docs)

## Configuration

Environment variables (or `.env` file):

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `sqlite+aiosqlite:///test.db` | Async SQLAlchemy DB URL |
| `JWT_SECRET` | `CHANGE_IN_PRODUCTION` | JWT signing secret |
| `JWT_ALGORITHM` | `HS256` | JWT algorithm |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | `180` | Token TTL |
| `DEBUG` | `false` | Debug mode (resets DB on start) |