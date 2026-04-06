-- Run this in your Supabase SQL editor to set up the database

CREATE TABLE IF NOT EXISTS leads (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  business_name TEXT NOT NULL,
  city          TEXT NOT NULL,
  state         TEXT NOT NULL,
  phone         TEXT,
  email         TEXT,
  website_url   TEXT,
  score         INTEGER NOT NULL DEFAULT 0,
  score_reason  TEXT,
  status        TEXT NOT NULL DEFAULT 'New',
  category      TEXT,
  source        TEXT,
  raw_data      JSONB,
  ai_analysis   JSONB,
  outreach_status TEXT NOT NULL DEFAULT 'idle',
  last_emailed_at TIMESTAMPTZ,
  follow_up_count INTEGER NOT NULL DEFAULT 0,
  created_at    TIMESTAMPTZ DEFAULT now(),
  updated_at    TIMESTAMPTZ DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS leads_phone_unique
  ON leads (phone) WHERE phone IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS leads_name_city
  ON leads (lower(business_name), lower(city));

CREATE INDEX IF NOT EXISTS leads_score_idx ON leads (score DESC);
CREATE INDEX IF NOT EXISTS leads_status_idx ON leads (status);
CREATE INDEX IF NOT EXISTS leads_category_idx ON leads (category);
CREATE INDEX IF NOT EXISTS leads_created_at_idx ON leads (created_at DESC);

CREATE TABLE IF NOT EXISTS search_runs (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  location      TEXT NOT NULL,
  categories    TEXT[],
  total_found   INTEGER,
  new_leads     INTEGER,
  dupes_skipped INTEGER,
  started_at    TIMESTAMPTZ DEFAULT now(),
  finished_at   TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS search_schedules (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name             TEXT NOT NULL,
  location         TEXT NOT NULL,
  categories       TEXT[] NOT NULL,
  cron_expression  TEXT NOT NULL,
  enabled          BOOLEAN NOT NULL DEFAULT true,
  created_at       TIMESTAMPTZ DEFAULT now(),
  last_run_at      TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS email_outreach (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  lead_id        UUID NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
  sequence_step  INTEGER NOT NULL DEFAULT 0,
  subject        TEXT NOT NULL,
  body           TEXT NOT NULL,
  sent_at        TIMESTAMPTZ,
  resend_id      TEXT,
  status         TEXT NOT NULL DEFAULT 'pending',
  error_message  TEXT,
  created_at     TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS email_outreach_lead_id_idx ON email_outreach (lead_id);
CREATE INDEX IF NOT EXISTS email_outreach_status_idx  ON email_outreach (status);

-- Migration: add new columns to existing leads table
-- (safe to run even if columns already exist)
ALTER TABLE leads ADD COLUMN IF NOT EXISTS ai_analysis      JSONB;
ALTER TABLE leads ADD COLUMN IF NOT EXISTS outreach_status  TEXT NOT NULL DEFAULT 'idle';
ALTER TABLE leads ADD COLUMN IF NOT EXISTS last_emailed_at  TIMESTAMPTZ;
ALTER TABLE leads ADD COLUMN IF NOT EXISTS follow_up_count  INTEGER NOT NULL DEFAULT 0;

-- Auto-update updated_at on leads
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE TRIGGER leads_updated_at
  BEFORE UPDATE ON leads
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();
