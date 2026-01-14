# Personal Finance AI - Deployment Guide

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Supabase (Cloud)                      │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │  Postgres   │  │   Auth      │  │    pgvector         │ │
│  │  + pgvector │  │  (Email/OTP)│  │  (embeddings)       │ │
│  └─────────────┘  └─────────────┘  └─────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                              │
           ┌──────────────────┼──────────────────┐
           │                  │                  │
           ▼                  ▼                  ▼
┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│   Railway        │  │    Vercel        │  │    OpenAI        │
│   (Backend)      │  │   (Frontend)     │  │   (LLM API)      │
│   FastAPI        │  │   React Vite     │  │   GPT-4o-mini    │
│   Port: 8000     │  │   Port: 80/443   │  │                  │
└──────────────────┘  └──────────────────┘  └──────────────────┘
           │                  │                  │
           └──────────────────┼──────────────────┘
                              ▼
                    ┌──────────────────────┐
                    │    External APIs     │
                    │  Twilio | Resend     │
                    └──────────────────────┘
```

## Prerequisites

1. **Supabase Account** - Create project at supabase.com
2. **OpenAI API Key** - For GPT-4o-mini categorization
3. **Twilio Account** (optional) - For SMS alerts
4. **Resend Account** (optional) - For email alerts

## Step 1: Setup Supabase

### Create Project
1. Go to supabase.com and create new project
2. Note down: `SUPABASE_URL` and `SUPABASE_ANON_KEY`

### Run Schema
1. Go to SQL Editor in Supabase dashboard
2. Copy contents of `supabase/schema.sql`
3. Run the SQL script

### Configure Auth
1. Go to Authentication > Providers
2. Enable Email provider
3. (Optional) Enable SMS with Twilio

## Step 2: Deploy Backend (Railway)

### Initial Setup
```bash
# Install Railway CLI
npm i -g @railway/cli

# Login
railway login

# Initialize project
railway init
```

### Configure Environment
Create `railway.json`:
```json
{
  "build": {
    "builder": "NIXPACKS"
  },
  "deploy": {
    "startCommand": "uvicorn app.main:app --host 0.0.0.0 --port $PORT"
  }
}
```

### Set Environment Variables
```bash
railway variables set SUPABASE_URL=your_url
railway variables set SUPABASE_ANON_KEY=your_key
railway variables set SUPABASE_SERVICE_KEY=your_service_key
railway variables set OPENAI_API_KEY=sk-...
railway variables set TWILIO_ACCOUNT_SID=...
railway variables set TWILIO_AUTH_TOKEN=...
railway variables set TWILIO_FROM_NUMBER=+1...
railway variables set RESEND_API_KEY=re_...
```

### Deploy
```bash
railway up
```

### Note Backend URL
After deployment, note your backend URL (e.g., `https://your-app.railway.app`)

## Step 3: Deploy Frontend (Vercel)

### Initial Setup
```bash
# Install Vercel CLI
npm i -g vercel

# Login
vercel login

# Initialize
cd frontend
vercel
```

### Configure Environment
In Vercel dashboard, set:
- `VITE_SUPABASE_URL`: Your Supabase URL
- `VITE_SUPABASE_ANON_KEY`: Your Supabase anon key

### Update API URL
Edit `frontend/src/lib/api.ts`:
```typescript
const API_BASE = "https://your-backend-url.railway.app/api"
```

### Deploy
```bash
vercel --prod
```

## Step 4: Configure CORS

Update backend CORS in `app/main.py`:
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://your-frontend.vercel.app",
        "http://localhost:5173",  # Local dev
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

Redeploy backend:
```bash
railway up
```

## Step 5: Local Development

### Prerequisites
- Python 3.12+
- Node.js 20+
- Supabase running (cloud)

### Backend
```bash
cd backend
cp .env.example .env
# Edit .env with your keys

# Create virtual environment
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows

# Install dependencies
pip install -e .

# Run
uvicorn app.main:app --reload
```

### Frontend
```bash
cd frontend
cp .env.example .env.local
# Edit .env.local with your keys

# Install dependencies
npm ci

# Run dev server
npm run dev
```

## Monitoring & Alerts

### Check Health
```bash
curl https://your-backend.railway.app/health
```

### View Logs (Railway)
```bash
railway logs
```

### Test Alerts
```bash
curl -X POST https://your-backend.railway.app/api/alerts/check \
  -H "X-User-ID: your-user-id"
```

## Troubleshooting

### Prophet Installation Issues
- Use `prophet[cmdstanpy]` not standard `prophet`
- Ensure build tools are installed in Dockerfile

### CORS Errors
- Verify frontend URL is in CORS allow_origins
- Check that headers are not blocked

### Supabase Connection
- Verify URL ends with `.supabase.co`
- Ensure RLS policies are not blocking access

### LLM Categorization
- Check OpenAI API key is valid
- Verify LiteLLM config is loaded

## Cost Estimation

| Service | Free Tier | Estimated Cost |
|---------|-----------|----------------|
| Supabase | 500MB DB, 50MB file storage | $0 |
| Railway | 500 hours compute | $0-10/mo |
| Vercel | 100GB bandwidth | $0-20/mo |
| OpenAI | $5 free credits | ~$10-20/mo at scale |
| Twilio | $1.50 SMS (India) | Pay-as-go |
| Resend | 100 emails/mo free | $0-20/mo |

## Security Checklist

- [ ] Supabase RLS policies enabled
- [ ] API keys in environment variables
- [ ] CORS origins restricted to deployed URLs
- [ ] Rate limiting on API endpoints
- [ ] No secrets in git history
- [ ] HTTPS enforced (Vercel/Railway default)
