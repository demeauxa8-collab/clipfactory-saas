# ClipFactory API

FastAPI backend for ClipFactory SaaS.

## Run locally

```bash
cd apps/api
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env  # fill in real values
uvicorn app.main:app --reload --port 8000
```

OpenAPI: http://localhost:8000/docs (dev only).

## Routes

| Method | Path | Auth | Purpose |
| --- | --- | --- | --- |
| GET | `/health` | none | liveness |
| GET | `/me` | Bearer (Supabase JWT) | profile + subscription + credits |
| GET | `/jobs` | Bearer | list user's jobs |
| POST | `/jobs` | Bearer | submit a new clipping job |
| GET | `/jobs/{id}` | Bearer | job details + its clips |
| GET | `/clips/{id}/download` | Bearer | presigned R2 URL, TTL 10 min |

`POST /billing/checkout` and `POST /billing/webhook` ship in T7.

## Auth

The API expects an `Authorization: Bearer <supabase-jwt>` header. The Next.js client fetches the session from Supabase and forwards the access token. The JWT is verified with `SUPABASE_JWT_SECRET` (HS256, audience `authenticated`).
