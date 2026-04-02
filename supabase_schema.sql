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
