-- Migration: Add compression for checko_data field
-- Changes checko_data from TEXT to BYTEA and compresses existing data
-- Date: 2025-01-XX
--
-- IMPORTANT: Run temp/compress_existing_checko_data.py BEFORE applying this migration
-- to compress existing TEXT data into checko_data_compressed column

BEGIN;

-- Step 1: Add temporary column for compressed data
ALTER TABLE moderator_suppliers 
ADD COLUMN checko_data_compressed BYTEA;

-- Step 2: Compress existing checko_data and move to temporary column
-- This is done by Python script: temp/compress_existing_checko_data.py
-- The script compresses TEXT data and stores it in checko_data_compressed

-- Step 3: Drop old TEXT column
ALTER TABLE moderator_suppliers 
DROP COLUMN checko_data;

-- Step 4: Rename compressed column to checko_data
ALTER TABLE moderator_suppliers 
RENAME COLUMN checko_data_compressed TO checko_data;

-- Step 5: Add comment to document compression
COMMENT ON COLUMN moderator_suppliers.checko_data IS 'Compressed Checko data (gzip) stored as BYTEA';

COMMIT;

