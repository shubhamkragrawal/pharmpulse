CREATE SCHEMA IF NOT EXISTS ops;

-- Domain-agnostic audit log for the staging-layer missingness policy's
-- "row exclusion" strategy (spec 04_PHARMAPULSE_SPEC.md line 108): every
-- dbt run that excludes rows for data-quality reasons logs a row here
-- instead of silently dropping records.
CREATE TABLE IF NOT EXISTS ops.extraction_log (
    log_id          BIGSERIAL PRIMARY KEY,
    model_name      TEXT NOT NULL,
    exclusion_reason TEXT NOT NULL,
    excluded_count  INT NOT NULL,
    logged_at       TIMESTAMPTZ DEFAULT now()
);
