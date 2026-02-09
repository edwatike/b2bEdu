-- Fix domains_queue table to allow same domain for different keywords
-- Migration: 004_fix_domains_queue_primary_key.sql
-- Date: 2025-12-27
-- Description: Change primary key from domain to composite key (domain, keyword, parsing_run_id)
--               This allows the same domain to be associated with different keywords and parsing runs

-- Step 1: Add new id column as primary key
ALTER TABLE domains_queue ADD COLUMN IF NOT EXISTS id SERIAL;

-- Step 2: Create temporary table with new structure
CREATE TABLE IF NOT EXISTS domains_queue_new (
    id SERIAL PRIMARY KEY,
    domain VARCHAR(255) NOT NULL,
    keyword VARCHAR(255) NOT NULL,
    url TEXT NOT NULL,
    parsing_run_id VARCHAR(255),
    status VARCHAR(50) DEFAULT 'pending' NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Composite unique constraint: same domain can appear for different keywords/runs
    UNIQUE(domain, keyword, parsing_run_id)
);

-- Step 3: Copy data from old table to new table
-- Remove duplicates: keep only one entry per (domain, keyword, parsing_run_id)
-- Handle NULL parsing_run_id by using COALESCE
INSERT INTO domains_queue_new (domain, keyword, url, parsing_run_id, status, created_at)
SELECT DISTINCT ON (domain, keyword, COALESCE(parsing_run_id, ''))
    domain,
    keyword,
    url,
    parsing_run_id,
    status,
    created_at
FROM domains_queue
ORDER BY domain, keyword, COALESCE(parsing_run_id, ''), created_at DESC;

-- Step 4: Drop old table
DROP TABLE IF EXISTS domains_queue;

-- Step 5: Rename new table
ALTER TABLE domains_queue_new RENAME TO domains_queue;

-- Step 5.1: Rename sequence to standard name (CRITICAL FIX)
-- The sequence created by SERIAL is named domains_queue_new_id_seq
-- We need to rename it to domains_queue_id_seq to match SQLAlchemy expectations
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_sequences WHERE sequencename = 'domains_queue_new_id_seq') THEN
        ALTER SEQUENCE domains_queue_new_id_seq RENAME TO domains_queue_id_seq;
    END IF;
END $$;

-- Step 6: Recreate indexes
CREATE INDEX IF NOT EXISTS idx_domains_queue_status ON domains_queue(status);
CREATE INDEX IF NOT EXISTS idx_domains_queue_keyword ON domains_queue(keyword);
CREATE INDEX IF NOT EXISTS idx_domains_queue_parsing_run_id ON domains_queue(parsing_run_id);
CREATE INDEX IF NOT EXISTS idx_domains_queue_domain_keyword ON domains_queue(domain, keyword);

-- Step 7: Grant permissions on table
GRANT ALL PRIVILEGES ON TABLE domains_queue TO postgres;
GRANT ALL PRIVILEGES ON TABLE domains_queue TO PUBLIC;
ALTER TABLE domains_queue OWNER TO postgres;

-- Step 8: Grant permissions on sequence (CRITICAL FIX)
-- Fix permissions on both possible sequence names
DO $$
BEGIN
    -- Try domains_queue_id_seq (standard name)
    BEGIN
        GRANT ALL PRIVILEGES ON SEQUENCE domains_queue_id_seq TO postgres;
        GRANT ALL PRIVILEGES ON SEQUENCE domains_queue_id_seq TO PUBLIC;
        ALTER SEQUENCE domains_queue_id_seq OWNER TO postgres;
    EXCEPTION WHEN OTHERS THEN
        NULL; -- Sequence might not exist with this name
    END;
    
    -- Try domains_queue_new_id_seq (created by migration)
    BEGIN
        GRANT ALL PRIVILEGES ON SEQUENCE domains_queue_new_id_seq TO postgres;
        GRANT ALL PRIVILEGES ON SEQUENCE domains_queue_new_id_seq TO PUBLIC;
        ALTER SEQUENCE domains_queue_new_id_seq OWNER TO postgres;
    EXCEPTION WHEN OTHERS THEN
        NULL; -- Sequence might not exist with this name
    END;
END $$;

