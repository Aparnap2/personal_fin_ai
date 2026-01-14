-- Personal Finance AI Schema
-- Run in Supabase SQL Editor

-- Enable pgvector extension for embeddings
CREATE EXTENSION IF NOT EXISTS vector;

-- Users table (extends Supabase auth)
CREATE TABLE IF NOT EXISTS public.users (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email TEXT NOT NULL,
    full_name TEXT,
    currency TEXT DEFAULT 'INR',
    budget_pct REAL DEFAULT 110.0,
    alert_threshold NUMERIC DEFAULT 5000.0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Categories with embeddings for hybrid search
CREATE TABLE IF NOT EXISTS public.categories (
    id SERIAL PRIMARY KEY,
    user_id UUID REFERENCES public.users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    embedding VECTOR(1536),
    is_default BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Default categories
INSERT INTO public.categories (name, is_default) VALUES
    ('Groceries', TRUE),
    ('Dining', TRUE),
    ('Transport', TRUE),
    ('Utilities', TRUE),
    ('Shopping', TRUE),
    ('Entertainment', TRUE),
    ('Health', TRUE),
    ('Subscriptions', TRUE),
    ('Income', TRUE),
    ('Savings', TRUE),
    ('Other', TRUE)
ON CONFLICT DO NOTHING;

-- Transactions table
CREATE TABLE IF NOT EXISTS public.transactions (
    id SERIAL PRIMARY KEY,
    user_id UUID REFERENCES public.users(id) ON DELETE CASCADE,
    date TIMESTAMPTZ NOT NULL,
    description TEXT NOT NULL,
    amount NUMERIC NOT NULL,
    category TEXT,
    is_income BOOLEAN DEFAULT FALSE,
    source TEXT DEFAULT 'csv',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Budgets table
CREATE TABLE IF NOT EXISTS public.budgets (
    id SERIAL PRIMARY KEY,
    user_id UUID REFERENCES public.users(id) ON DELETE CASCADE,
    category TEXT NOT NULL,
    monthly_limit NUMERIC NOT NULL,
    month DATE NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, category, month)
);

-- Forecasts table
CREATE TABLE IF NOT EXISTS public.forecasts (
    id SERIAL PRIMARY KEY,
    user_id UUID REFERENCES public.users(id) ON DELETE CASCADE,
    category TEXT,
    forecast_date DATE NOT NULL,
    predicted_amount NUMERIC NOT NULL,
    confidence_lower NUMERIC,
    confidence_upper NUMERIC,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Alerts log
CREATE TABLE IF NOT EXISTS public.alerts (
    id SERIAL PRIMARY KEY,
    user_id UUID REFERENCES public.users(id) ON DELETE CASCADE,
    type TEXT NOT NULL, -- 'sms', 'email'
    message TEXT NOT NULL,
    sent_at TIMESTAMPTZ DEFAULT NOW()
);

-- CSV uploads tracking
CREATE TABLE IF NOT EXISTS public.uploads (
    id SERIAL PRIMARY KEY,
    user_id UUID REFERENCES public.users(id) ON DELETE CASCADE,
    filename TEXT NOT NULL,
    row_count INTEGER,
    processed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_transactions_user_date ON public.transactions(user_id, date);
CREATE INDEX IF NOT EXISTS idx_transactions_category ON public.transactions(category);
CREATE INDEX IF NOT EXISTS idx_categories_user ON public.categories(user_id);
CREATE INDEX IF NOT EXISTS idx_forecasts_user ON public.forecasts(user_id);

-- Row Level Security
ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.categories ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.transactions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.budgets ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.forecasts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.alerts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.uploads ENABLE ROW LEVEL SECURITY;

-- RLS Policies
CREATE POLICY "Users can only see own data" ON public.users
    FOR ALL USING (auth.uid() = id);

CREATE POLICY "Users can only see own categories" ON public.categories
    FOR ALL USING (auth.uid() = user_id OR is_default = TRUE);

CREATE POLICY "Users can only see own transactions" ON public.transactions
    FOR ALL USING (auth.uid() = user_id);

CREATE POLICY "Users can only see own budgets" ON public.budgets
    FOR ALL USING (auth.uid() = user_id);

CREATE POLICY "Users can only see own forecasts" ON public.forecasts
    FOR ALL USING (auth.uid() = user_id);

CREATE POLICY "Users can only see own alerts" ON public.alerts
    FOR ALL USING (auth.uid() = user_id);

CREATE POLICY "Users can only see own uploads" ON public.uploads
    FOR ALL USING (auth.uid() = user_id);

-- Functions
CREATE OR REPLACE FUNCTION public.update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Triggers for updated_at
CREATE TRIGGER update_users_updated_at
    BEFORE UPDATE ON public.users
    FOR EACH ROW EXECUTE FUNCTION public.update_updated_at();

-- Supabase function to generate embeddings (uses OpenAI API)
CREATE OR REPLACE FUNCTION public.generate_embedding(text_input TEXT)
RETURNS VECTOR(1536) AS $$
    SELECT embedding::vector(1536)
    FROM openai_embeddings('text-embedding-3-small', text_input);
$$ LANGUAGE sql SECURITY DEFINER;

-- Function to classify transaction using LLM
CREATE OR REPLACE FUNCTION public.classify_transaction(description TEXT)
RETURNS TEXT AS $$
    SELECT 'Dining'; -- Placeholder, actual LLM call via Edge Function
$$ LANGUAGE sql SECURITY DEFINER;

-- Storage bucket for CSV uploads
INSERT INTO storage.buckets (id, name, public) VALUES ('uploads', 'uploads', TRUE)
ON CONFLICT DO NOTHING;

CREATE POLICY "Users can upload files" ON storage.objects
    FOR INSERT WITH CHECK (bucket_id = 'uploads' AND auth.uid() = owner);

CREATE POLICY "Users can view own files" ON storage.objects
    FOR SELECT USING (bucket_id = 'uploads' AND auth.uid() = owner);
