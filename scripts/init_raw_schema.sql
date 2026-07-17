CREATE SCHEMA IF NOT EXISTS raw;

CREATE TABLE IF NOT EXISTS raw.ct_studies (
    nct_id        TEXT PRIMARY KEY,
    payload       JSONB NOT NULL,
    fetched_at    TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS raw.fda_applications (
    application_number TEXT PRIMARY KEY,
    payload            JSONB NOT NULL,
    fetched_at         TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS raw.extraction_checkpoints (
    source TEXT PRIMARY KEY,           -- 'ctgov' | 'openfda'
    last_page_completed INT NOT NULL DEFAULT 0,
    resume_cursor TEXT,                -- opaque pagination cursor, for token-paginated sources
    last_run_started_at TIMESTAMPTZ,
    last_run_completed_at TIMESTAMPTZ,
    status TEXT                        -- 'running' | 'completed' | 'failed'
);
