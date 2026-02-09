-- Migration: Add results_count column to parsing_runs table
-- Created: 2025-01-27
-- Description: Add results_count column if it doesn't exist to fix AttributeError

-- Add results_count column if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'parsing_runs' AND column_name = 'results_count'
    ) THEN
        ALTER TABLE parsing_runs ADD COLUMN results_count INTEGER;
    END IF;
END $$;

-- Grant permissions
GRANT ALL PRIVILEGES ON TABLE parsing_runs TO postgres;
















