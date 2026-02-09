-- Migration 016: Create run_domains table for per-run domain status tracking
-- Used by "Текущая задача" block on /moderator dashboard

CREATE TABLE IF NOT EXISTS run_domains (
    id BIGSERIAL PRIMARY KEY,
    run_id VARCHAR(64) NOT NULL,
    domain VARCHAR(255) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'pending',
    reason TEXT,
    attempted_urls JSONB DEFAULT '[]'::jsonb,
    inn_source_url TEXT,
    email_source_url TEXT,
    supplier_id BIGINT REFERENCES moderator_suppliers(id) ON DELETE SET NULL,
    checko_ok BOOLEAN NOT NULL DEFAULT FALSE,
    global_requires_moderation BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_run_domains_run_domain UNIQUE (run_id, domain)
);

CREATE INDEX IF NOT EXISTS idx_run_domains_run_id ON run_domains (run_id);
CREATE INDEX IF NOT EXISTS idx_run_domains_status ON run_domains (status);
CREATE INDEX IF NOT EXISTS idx_run_domains_domain ON run_domains (domain);
CREATE INDEX IF NOT EXISTS idx_run_domains_supplier_id ON run_domains (supplier_id);
