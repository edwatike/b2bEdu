-- Migration: Add parsing_requests table and update parsing_runs structure
-- Created: 2025-12-26

-- Table: parsing_requests
CREATE TABLE IF NOT EXISTS parsing_requests (
    id SERIAL PRIMARY KEY,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_by INTEGER,
    raw_keys_json TEXT,
    depth INTEGER,
    source VARCHAR(32),
    comment TEXT,
    title VARCHAR(255)
);

-- Update parsing_runs table structure if needed
-- Check if parsing_runs has the old structure (with keyword column)
DO $$
BEGIN
    -- Add id column if it doesn't exist
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'parsing_runs' AND column_name = 'id'
    ) THEN
        ALTER TABLE parsing_runs ADD COLUMN id SERIAL;
        ALTER TABLE parsing_runs ADD CONSTRAINT parsing_runs_id_pk PRIMARY KEY (id);
    END IF;
    
    -- Add request_id column if it doesn't exist
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'parsing_runs' AND column_name = 'request_id'
    ) THEN
        ALTER TABLE parsing_runs ADD COLUMN request_id INTEGER;
        ALTER TABLE parsing_runs ADD CONSTRAINT parsing_runs_request_id_fk 
            FOREIGN KEY (request_id) REFERENCES parsing_requests(id) ON DELETE CASCADE;
    END IF;
    
    -- Add run_id column if it doesn't exist (for unique constraint)
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'parsing_runs' AND column_name = 'run_id'
    ) THEN
        ALTER TABLE parsing_runs ADD COLUMN run_id VARCHAR(64) UNIQUE;
    END IF;
    
    -- Add parser_task_id column if it doesn't exist
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'parsing_runs' AND column_name = 'parser_task_id'
    ) THEN
        ALTER TABLE parsing_runs ADD COLUMN parser_task_id VARCHAR(128);
    END IF;
    
    -- Add depth column if it doesn't exist
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'parsing_runs' AND column_name = 'depth'
    ) THEN
        ALTER TABLE parsing_runs ADD COLUMN depth INTEGER;
    END IF;
    
    -- Add source column if it doesn't exist
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'parsing_runs' AND column_name = 'source'
    ) THEN
        ALTER TABLE parsing_runs ADD COLUMN source VARCHAR(32);
    END IF;
    
    -- Add error_message column if it doesn't exist (rename from error if needed)
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'parsing_runs' AND column_name = 'error_message'
    ) THEN
        -- Check if error column exists and rename it
        IF EXISTS (
            SELECT 1 FROM information_schema.columns 
            WHERE table_name = 'parsing_runs' AND column_name = 'error'
        ) THEN
            ALTER TABLE parsing_runs RENAME COLUMN error TO error_message;
        ELSE
            ALTER TABLE parsing_runs ADD COLUMN error_message TEXT;
        END IF;
    END IF;
    
    -- Remove keyword column if it exists (moved to parsing_requests)
    IF EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'parsing_runs' AND column_name = 'keyword'
    ) THEN
        -- Note: We don't drop it immediately to preserve data
        -- It will be removed in a future migration after data migration
        -- ALTER TABLE parsing_runs DROP COLUMN keyword;
    END IF;
    
    -- Remove results_count column if it exists (not in new model)
    -- IF EXISTS (
    --     SELECT 1 FROM information_schema.columns 
    --     WHERE table_name = 'parsing_runs' AND column_name = 'results_count'
    -- ) THEN
    --     ALTER TABLE parsing_runs DROP COLUMN results_count;
    -- END IF;
END $$;

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_parsing_runs_status ON parsing_runs(status);
CREATE INDEX IF NOT EXISTS idx_parsing_runs_run_id ON parsing_runs(run_id);
CREATE INDEX IF NOT EXISTS idx_parsing_runs_request_id ON parsing_runs(request_id);



















