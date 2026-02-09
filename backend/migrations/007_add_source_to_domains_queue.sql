-- Migration: 007_add_source_to_domains_queue.sql
-- Date: 2025-12-29
-- Description: Add source field to domains_queue table to track whether URL came from Google, Yandex, or both

-- Step 1: Add source column to domains_queue
ALTER TABLE domains_queue ADD COLUMN IF NOT EXISTS source VARCHAR(32);

-- Step 2: Update existing records to have default source 'google' (for backward compatibility)
UPDATE domains_queue SET source = 'google' WHERE source IS NULL;

-- Step 3: Make source NOT NULL after setting defaults
ALTER TABLE domains_queue ALTER COLUMN source SET NOT NULL;
ALTER TABLE domains_queue ALTER COLUMN source SET DEFAULT 'google';

-- Step 4: Add comment
COMMENT ON COLUMN domains_queue.source IS 'Source of the URL: google, yandex, or both';











