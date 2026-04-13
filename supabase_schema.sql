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

-- Chat messages for the AI assistant
CREATE TABLE IF NOT EXISTS chat_messages (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  role          TEXT NOT NULL,
  content       TEXT NOT NULL DEFAULT '',
  tool_calls    JSONB,
  tool_call_id  TEXT,
  context       JSONB,
  created_at    TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS chat_messages_created_at_idx ON chat_messages (created_at DESC);

-- Deep research enrichment columns
ALTER TABLE leads ADD COLUMN IF NOT EXISTS contact_name       TEXT;
ALTER TABLE leads ADD COLUMN IF NOT EXISTS contact_title      TEXT;
ALTER TABLE leads ADD COLUMN IF NOT EXISTS additional_phones  JSONB DEFAULT '[]';
ALTER TABLE leads ADD COLUMN IF NOT EXISTS additional_emails  JSONB DEFAULT '[]';
ALTER TABLE leads ADD COLUMN IF NOT EXISTS social_links       JSONB DEFAULT '{}';
ALTER TABLE leads ADD COLUMN IF NOT EXISTS business_hours     TEXT;
ALTER TABLE leads ADD COLUMN IF NOT EXISTS rating             NUMERIC(2,1);
ALTER TABLE leads ADD COLUMN IF NOT EXISTS review_count       INTEGER;
ALTER TABLE leads ADD COLUMN IF NOT EXISTS years_in_business  INTEGER;
ALTER TABLE leads ADD COLUMN IF NOT EXISTS bbb_accredited     BOOLEAN;
ALTER TABLE leads ADD COLUMN IF NOT EXISTS yelp_categories    JSONB DEFAULT '[]';
ALTER TABLE leads ADD COLUMN IF NOT EXISTS address            TEXT;

-- Search queue for background processing
CREATE TABLE IF NOT EXISTS search_queue (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  location      TEXT NOT NULL,
  categories    JSONB NOT NULL,
  status        TEXT NOT NULL DEFAULT 'pending',
  progress      JSONB DEFAULT '{}',
  result        JSONB,
  error         TEXT,
  created_at    TIMESTAMPTZ DEFAULT now(),
  started_at    TIMESTAMPTZ,
  finished_at   TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_search_queue_status  ON search_queue(status);
CREATE INDEX IF NOT EXISTS idx_search_queue_created ON search_queue(created_at DESC);

-- Email automation columns
ALTER TABLE leads ADD COLUMN IF NOT EXISTS replied    BOOLEAN DEFAULT false;
ALTER TABLE leads ADD COLUMN IF NOT EXISTS replied_at TIMESTAMPTZ;
ALTER TABLE leads ADD COLUMN IF NOT EXISTS opted_out  BOOLEAN DEFAULT false;

ALTER TABLE email_outreach ADD COLUMN IF NOT EXISTS opened_at  TIMESTAMPTZ;
ALTER TABLE email_outreach ADD COLUMN IF NOT EXISTS clicked_at TIMESTAMPTZ;

-- Outreach automation config (single-row settings table)
CREATE TABLE IF NOT EXISTS outreach_config (
  id                     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  max_per_hour           INTEGER NOT NULL DEFAULT 50,
  max_per_day            INTEGER NOT NULL DEFAULT 200,
  followup_1_days        INTEGER NOT NULL DEFAULT 3,
  followup_2_days        INTEGER NOT NULL DEFAULT 5,
  followup_3_days        INTEGER NOT NULL DEFAULT 7,
  smart_schedule_enabled BOOLEAN NOT NULL DEFAULT false,
  min_score_auto         INTEGER NOT NULL DEFAULT 7,
  created_at             TIMESTAMPTZ DEFAULT now(),
  updated_at             TIMESTAMPTZ DEFAULT now()
);

-- Seed default config row if empty
INSERT INTO outreach_config (id)
SELECT gen_random_uuid()
WHERE NOT EXISTS (SELECT 1 FROM outreach_config);

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
