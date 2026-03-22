# MeetFlow — Frontend

React + Material UI frontend for the MeetFlow video chat application.

## Requirements

- Node.js ≥ 18

## Running locally

```bash
cd frontend
npm install
npm run dev
```

## Backend URL configuration

Backend URLs are set via environment variables in a `.env` file in the `frontend/` directory:

```env
VITE_API_BASE_URL=http://localhost:8000
VITE_WS_BASE_URL=ws://localhost:8000/ws
```

| Variable | Default | File |
|----------|---------|------|
| `VITE_API_BASE_URL` | `http://localhost:8000/api` | `src/api/axiosInstance.ts` |
| `VITE_WS_BASE_URL` | `ws://localhost:8000/ws` | `src/api/ws/websocketService.ts` |

> **Note:** The backend routes have no `/api` prefix, so for local development set `VITE_API_BASE_URL=http://localhost:8000`.
> In Docker, this is handled automatically in `docker-compose.yml`.
