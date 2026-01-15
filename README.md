# Personal Finance AI

Personal Finance AI is an open-source full-stack application to help users track, categorize, and forecast their personal finances using modern LLMs and embeddings. It combines a FastAPI backend (Python) with a React + Vite TypeScript frontend, and uses Supabase (Postgres + pgvector) as the primary data store.

Key highlights
- Automatic transaction categorization (LLM-assisted)
- CSV import for bank statements
- Spending alerts (SMS / email integration optional)
- Time-series forecasting for budgets and spending
- Hybrid search with category embeddings (pgvector + Supabase)

Language composition (repo)
- TypeScript: ~45%
- Python: ~45%
- PLpgSQL: ~5%
- JavaScript, CSS, Dockerfile, HTML: < 3%

Contents
- backend/ — FastAPI backend, business logic, LLM integration
- frontend/ — React + Vite UI (TypeScript)
- supabase/schema.sql — Database schema and default categories
- DEPLOY.md — Detailed deployment and operational guide

Why this project
- Make it easy to import financial data and get actionable insights (categorization, forecasting, alerts).
- Hybrid approach: embeddings for search + LLMs for categorization and explanations.
- Simple modern stack that can be deployed to Railway (backend) + Vercel (frontend) with Supabase as the database.

Quick demo / screenshots
- The frontend routes include Dashboard, Upload, Transactions, and Budgets (see `frontend/src/App.tsx`).
- The backend exposes a health endpoint and CSV upload + alert APIs (see `backend/app/main.py`).

Architecture (high-level)
- Frontend (React + Vite) served on Vercel (or run locally)
- Backend (FastAPI, async) served on Railway (or run locally with uvicorn)
- Supabase (managed Postgres) — stores users, transactions, categories, embeddings
- pgvector extension for storing category embeddings
- LLMs: either external (OpenAI GPT-4o-mini) or local runtimes via LiteLLM config
- Optional integrations: Twilio (SMS), Resend (email)

Getting started — Local development

Prerequisites
- Python 3.12+
- Node.js 20+
- Supabase project (cloud) — or a running Postgres with the same schema
- OpenAI API key (or local LiteLLM config if using local LLM)
- (Optional) Twilio / Resend accounts for alerts

1) Database / Supabase
- Create a Supabase project
- Note down SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_SERVICE_KEY
- Run the schema in the Supabase SQL editor:
  - `supabase/schema.sql` in this repository (creates users, categories, transactions, etc.)
  - Link: https://github.com/Aparnap2/personal_fin_ai/blob/main/supabase/schema.sql

2) Backend — run locally
```bash
cd backend
cp .env.example .env          # Edit .env with your keys
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -e .
uvicorn app.main:app --reload
```
- Default health check: GET http://localhost:8000/health
- CSV upload endpoint: POST http://localhost:8000/api/upload/csv
  - Example: requires header `X-User-ID: <user-uuid>` and form file `file`.
- Alerts/test: POST http://localhost:8000/api/alerts/check (see DEPLOY.md)

Important backend notes
- LiteLLM config: Backend loads LiteLLM settings from `LITELLM_CONFIG_PATH` (env default `litellm_config.yaml`) if present. See `backend/app/main.py`.
- CORS: adjust allowed origins in `backend/app/main.py` to your frontend URL(s).
- Uses async Supabase client; dependency injection via FastAPI `get_supabase`.

3) Frontend — run locally
```bash
cd frontend
cp .env.example .env.local    # Edit with FRONTEND-specific envs (e.g., VITE_API_URL)
npm ci
npm run dev
```
- The frontend mounts at `/` and routes: `/` (Dashboard), `/upload`, `/transactions`, `/budgets`.
- Entrypoint: `frontend/index.html`, main app `frontend/src/main.tsx` and `frontend/src/App.tsx`.

Environment variables (common, examples)
- SUPABASE_URL
- SUPABASE_ANON_KEY
- SUPABASE_SERVICE_KEY (server-side)
- OPENAI_API_KEY (if using OpenAI for categorization)
- LITELLM_CONFIG_PATH (optional, for local LiteLLM)
- TWILIO_ACCOUNT_SID (optional)
- TWILIO_AUTH_TOKEN (optional)
- TWILIO_FROM_NUMBER (optional)
- RESEND_API_KEY (optional)
- VITE_API_URL (frontend — points to deployed or local backend)

Deployment
- Backend: Railway (recommended in DEPLOY.md)
  - Start command example: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
  - See `DEPLOY.md` for Railway `railway.json` example and environment variables.
- Frontend: Vercel (or any static host supporting SPA)
- Supabase: managed cloud project (pgvector enabled)
- LLM options:
  - Hosted OpenAI models (GPT-4o-mini) — set OPENAI_API_KEY
  - Local model via LiteLLM — provide `litellm_config.yaml` and set `LITELLM_CONFIG_PATH`

API reference (high level)
- GET /health
  - Returns service status and timestamp
- POST /api/upload/csv
  - Upload and parse CSV transactions, categorize (LLM), store in Supabase
  - Headers: X-User-ID (UUID)
  - Body: multipart/form-data with `file`
- POST /api/alerts/check
  - Trigger alert checks for a user (used for testing)
  - Headers: X-User-ID
- Additional endpoints for categorization, forecasts, budgets, transactions exist in the backend code (see `backend/app/`).

Database and schema
- Main schema is in `supabase/schema.sql`
  - Uses `vector` (pgvector) extension for category embeddings
  - Tables include: public.users, public.categories, transactions, budgets, alerts, etc.
- Default categories are inserted in the schema (Groceries, Dining, Transport, ...)

Security & production notes
- Never commit API keys or service keys to git
- Ensure Supabase RLS (Row Level Security) policies are configured for multi-tenant data safety
- Restrict CORS to deployed frontend origins
- Rate-limit public endpoints in production
- Use service keys only on server side (backend). Expose only anon keys to the frontend where necessary.

Troubleshooting (collected from DEPLOY.md)
- Prophet/forecast: install `prophet[cmdstanpy]` and ensure build tools are available (Docker or system packages)
- Supabase connection errors: ensure the URL ends with `.supabase.co` and keys are correct
- CORS errors: confirm the backend `allow_origins` contains your frontend origin
- LLM issues: verify OPENAI_API_KEY or LiteLLM config is correct and accessible

Operational / monitoring
- Health check endpoint: `GET /health`
- Railway logs: `railway logs`
- Test alerts and endpoints with curl (examples in DEPLOY.md)

Contributing
- Issues and PRs welcome. Please:
  - Open an issue describing the problem or feature
  - Fork and submit PRs against `main`
  - Run linting and tests (if added) and include a clear description of changes

Useful files & links
- Deploy guide: DEPLOY.md — https://github.com/Aparnap2/personal_fin_ai/blob/main/DEPLOY.md
- DB schema: supabase/schema.sql — https://github.com/Aparnap2/personal_fin_ai/blob/main/supabase/schema.sql
- Backend entry: backend/app/main.py — https://github.com/Aparnap2/personal_fin_ai/blob/main/backend/app/main.py
- Frontend entry: frontend/src/App.tsx — https://github.com/Aparnap2/personal_fin_ai/blob/main/frontend/src/App.tsx

Roadmap / ideas
- Add user onboarding flow and sample demo data
- Improve categorization accuracy with supervised training / feedback loop
- Add tests and CI
- Add Docker Compose for fully local stack (Postgres + Supabase Emulator + backend + frontend)
- Provide a migration plan for large datasets and backup scripts

License
- Add a license file (e.g., MIT) if you want to make the project open-source permissive.

Contact / author
- Repository: Aparnap2/personal_fin_ai

