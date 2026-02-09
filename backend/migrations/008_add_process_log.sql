-- Migration: Add process_log field to parsing_runs table
-- Created: 2025-12-29
-- Description: Adds JSON field to store detailed parsing process information

-- Add process_log column to parsing_runs table
DO $$
BEGIN
    -- Add process_log column if it doesn't exist
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'parsing_runs' AND column_name = 'process_log'
    ) THEN
        ALTER TABLE parsing_runs ADD COLUMN process_log JSONB;
        
        -- Add comment to describe the field
        COMMENT ON COLUMN parsing_runs.process_log IS 'JSON object containing detailed parsing process information: statistics by source, domain counts, execution time, errors, captcha info, etc.';
    END IF;
END $$;

