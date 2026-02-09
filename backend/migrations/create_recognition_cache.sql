-- Migration: Create recognition_cache table for GROQ results caching
-- Created: 2025-01-XX

CREATE TABLE IF NOT EXISTS recognition_cache (
    id SERIAL PRIMARY KEY,
    file_hash VARCHAR(64) NOT NULL UNIQUE,
    filename VARCHAR(500),
    file_size INTEGER,
    positions_json TEXT NOT NULL,
    groq_model VARCHAR(100),
    groq_tokens_used INTEGER DEFAULT 0,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    last_accessed_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Index for fast lookup by hash
CREATE INDEX IF NOT EXISTS idx_recognition_cache_hash 
    ON recognition_cache (file_hash);

-- Index for cache expiration queries
CREATE INDEX IF NOT EXISTS idx_recognition_cache_created_at 
    ON recognition_cache (created_at);

-- Index for LRU/LFU eviction policies
CREATE INDEX IF NOT EXISTS idx_recognition_cache_last_accessed 
    ON recognition_cache (last_accessed_at);

COMMENT ON TABLE recognition_cache IS 'Cache for GROQ recognition results to avoid repeated API calls';
COMMENT ON COLUMN recognition_cache.file_hash IS 'SHA256 hash of the file content';
COMMENT ON COLUMN recognition_cache.positions_json IS 'JSON array of extracted item names';
COMMENT ON COLUMN recognition_cache.groq_model IS 'GROQ model name used for recognition';
COMMENT ON COLUMN recognition_cache.groq_tokens_used IS 'Total tokens used by GROQ API';
COMMENT ON COLUMN recognition_cache.last_accessed_at IS 'Last time this cache entry was accessed';

-- View for cache statistics
CREATE OR REPLACE VIEW recognition_cache_stats AS
SELECT 
    COUNT(*) as total_entries,
    COUNT(*) FILTER (WHERE created_at > NOW() - INTERVAL '24 hours') as entries_24h,
    SUM(groq_tokens_used) as total_tokens_saved,
    AVG(groq_tokens_used) as avg_tokens_per_request
FROM recognition_cache;
