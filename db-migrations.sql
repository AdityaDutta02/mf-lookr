-- db-migrations.sql — runs once at deploy time against MF Lookr's isolated Postgres schema.
--
-- Relational schema (NOT a table per AMC — see project memory project_mf_lookr_rebuild.md,
-- decision #1). "fund house -> fund -> year -> month" is expressed as columns + indexes so
-- a new fund house is just new rows, never a migration.
--
-- Source policy: full detailed monthly factsheets only, parsed deterministically by the local
-- extraction toolkit (tools/) and bulk-loaded here — the app itself never parses on the
-- initial load (see tools/README.md).

CREATE TABLE IF NOT EXISTS amcs (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  slug           TEXT NOT NULL UNIQUE,      -- 'ppfas', 'hdfc', 'axis', ...
  name           TEXT NOT NULL,             -- canonical display name, e.g. "PPFAS Mutual Fund"
  factsheet_url  TEXT,                      -- source downloads page
  archive_from   TEXT,                      -- earliest period locally parsed, "YYYY-MM"
  status         TEXT NOT NULL DEFAULT 'pending', -- 'pending' | 'loaded'
  updated_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- One row per scheme. amfi_code is the canonical identity key (resolves the old app's
-- synthetic/garbage scheme_code problem — see BULK_DELETE_REQUEST.md).
CREATE TABLE IF NOT EXISTS funds (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  amc_slug        TEXT NOT NULL REFERENCES amcs(slug),
  amfi_code       TEXT NOT NULL UNIQUE,     -- AMFI scheme code (identity key)
  scheme_name     TEXT NOT NULL,            -- canonical name, from AMFI NAV master
  isin_growth     TEXT,
  isin_reinvest   TEXT,
  category        TEXT,                     -- e.g. "Equity - Flexi Cap Fund"
  asset_class     TEXT,                     -- 'equity' | 'debt' | 'hybrid' | 'other'
  plan_type       TEXT,                     -- 'direct-growth' | 'regular-growth' | ...
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS funds_amc_idx ON funds (amc_slug);

-- One row per (fund, month) — the normalized AnalyseData contract (lib/types.ts) plus the
-- pointer to the raw source PDF kept in storage (decision #6: raw files ARE retained this
-- time, so a future parser fix re-runs against stored originals instead of re-crawling).
CREATE TABLE IF NOT EXISTS disclosures (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  amfi_code     TEXT NOT NULL REFERENCES funds(amfi_code),
  amc_slug      TEXT NOT NULL,
  year          INTEGER NOT NULL,
  month         INTEGER NOT NULL,           -- 1-12
  period        TEXT NOT NULL,              -- "YYYY-MM", denormalized for cheap filtering
  as_of_date    TEXT,                       -- portfolio date as printed, "YYYY-MM-DD"
  source_org    TEXT,
  source_url    TEXT,                       -- exact factsheet PDF URL this row was parsed from
  raw_file_key  TEXT,                       -- storage key of the retained original PDF
  data          JSONB NOT NULL,             -- full AnalyseData contract
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (amfi_code, period)
);
CREATE INDEX IF NOT EXISTS disclosures_fund_idx ON disclosures (amfi_code);
CREATE INDEX IF NOT EXISTS disclosures_amc_period_idx ON disclosures (amc_slug, period);
CREATE INDEX IF NOT EXISTS disclosures_year_month_idx ON disclosures (amfi_code, year, month);

-- Daily NAV history per fund, from AMFI's NAV download (decision #7: dual-purpose — identity
-- resolution AND NAV history storage).
CREATE TABLE IF NOT EXISTS navs (
  id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  amfi_code  TEXT NOT NULL REFERENCES funds(amfi_code),
  date       DATE NOT NULL,
  nav        NUMERIC NOT NULL,
  UNIQUE (amfi_code, date)
);
CREATE INDEX IF NOT EXISTS navs_fund_idx ON navs (amfi_code);

-- AI narrative cache, keyed the same way as disclosures. Fed the COMPUTED month-over-month
-- deltas (not a single snapshot) — the structural fix for the old app's broken AI insight.
CREATE TABLE IF NOT EXISTS ai_cache (
  id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  amfi_code  TEXT NOT NULL,
  period     TEXT NOT NULL,
  insight    JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (amfi_code, period)
);
